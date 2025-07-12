from typing import Annotated, List, TypedDict, Dict
from langgraph.graph.message import add_messages
from langchain_community.document_transformers import LongContextReorder
from langchain_core.messages import AIMessage, HumanMessage
from dotenv import load_dotenv
from openai import OpenAI
import os
from mcp_client import *
from utils import *
from agent import *
from prompt import *
from pinecone_utils import *
from prompt import *

# langgraph state 정의
class ChatbotState(TypedDict):
    question: Annotated[str, "사용자 원본 질문"]
    flow_type: Annotated[str, "데이터베이스 조회 흐름"]
    patient_info: Annotated[str, "순차 처리를 위한 환자 정보"]
    decision_slack: Annotated[str, "슬랙 전송 여부 결정"]
    tools_query: Annotated[List[str], "각 DB에 전달할 쿼리 리스트"]
    neo4j_documents: Annotated[List, "Neo4j 검색 결과"]
    vector_documents: Annotated[List, "VectorDB 검색 결과"]
    final_answer: Annotated[str, "최종 답변"]
    slack_response: Annotated[str, "슬랙 전송 결과"]
    messages: Annotated[List, add_messages]

    current_query: Annotated[str, "Current_Query"]
    query_variants: Annotated[List[str], "Query_Variants"]
    llm_evaluation: Annotated[Dict, "LLM_Evaluation"]
    loop_cnt: Annotated[int, "Loop_Count"]

# 1) 
async def router_agent(state: ChatbotState):
    """
    사용자 질문을 분석하여 처리 흐름(flow_type)과 각 DB에 필요한 쿼리를 결정합니다.
    """
    question = state["question"]
    
    model_with_tools = model.with_structured_output(tool_router_schema)
    
    response = await model_with_tools.ainvoke([
        HumanMessage(content=ROUTER_PROMPT),
        HumanMessage(content=question)])

    return ChatbotState(
        flow_type=response.get("flow_type"),
        tools_query=[response.get("neo4j_query", ""), response.get("vector_db_query", "")])

# 2)
async def decision_slack(state: ChatbotState):
    """
    사용자 질문을 바탕으로 슬랙 메시지 전송이 필요한지 결정합니다.
    """
    user_query = state["question"]
    
    use_slack = determine_slack_usage(user_query)
    response = use_slack

    if use_slack == 'No' and ("에게" in user_query or any(cmd in user_query for cmd in ["보내줘", "전송해줘", "전달해줘"])):
         llm_response = await model.ainvoke(f"{LLM_DECISION_SLACK}\n\n{user_query}")
         response = llm_response.content
    
    return ChatbotState(decision_slack=response)

# 3)
async def neo4j_db(state: ChatbotState):
    """
    Neo4j 데이터베이스에서 환자 정보를 검색합니다.
    """
    query = state['tools_query'][0]
    
    if not query:
        return ChatbotState(neo4j_documents=["Neo4j 쿼리가 제공되지 않았습니다."])

    result = []
    try:
        neo4j_tool = setup_mcp_client().get("neo4j_retriever")
        raw_result, _ = await neo4j_tool.ainvoke({"query": query})
        result = raw_result

    except Exception as e:
        result = [f"Neo4j 도구 실행 중 오류가 발생했습니다: {str(e)}"]

    if state['flow_type'] == 'sequential':
        return ChatbotState(neo4j_documents=result, patient_info=str(result))
    else:
        return ChatbotState(neo4j_documents=result)
    
# 4) 
async def gpt_query_rewriter_node(state: ChatbotState):
    """
    GPT를 이용한 쿼리 재작성 노드 (LLMEvaluator 기반 Best Query 선택)
    """

    loop_cnt = state.get("loop_cnt", 0)
    
    try:
        if loop_cnt == 0:
            # 첫 번째 시도: 다중 전략 쿼리 확장
            query_variants = await multi_strategy_query_expansion(state["question"])
            
            # LLMEvaluator 기반 best query 선택
            best_query, best_evaluation = await select_best_query_with_llm_evaluator(
                query_variants, 
                state["question"])
            
        elif loop_cnt == 1:
            # 두 번째 시도: 기존 변형 중 다른 쿼리 시도
            existing_variants = state.get("query_variants", [state["uestion"]])
            if len(existing_variants) > 1:
                # 상위 2개 쿼리 중 두 번째 선택
                selected_queries = await select_multiple_best_queries_with_evaluation(
                    existing_variants, state["question"], top_k=2
                )
                if len(selected_queries) > 1:
                    best_query, best_evaluation = selected_queries[1]  # 두 번째 최고 쿼리

                else:
                    best_query, best_evaluation = selected_queries[0]

            else:
                best_query = existing_variants[0] if existing_variants else state["question"]

                
        elif loop_cnt == 2:
            # 세 번째 시도: 다양성 기반 선택 또는 새로운 재작성
            existing_variants = state.get("query_variants", [state["question"]])
            try:
                best_query = await gpt_rewriter.rewrite(state['question'], "improvement")

            except:
                best_query = existing_variants[-1] if existing_variants else state["question"]

        else:
            # 마지막 시도: 원본 질문 사용
            best_query = state["question"]

        return ChatbotState(
            current_query=best_query,
            query_variants=await multi_strategy_query_expansion(state["question"]) if loop_cnt == 0 else state.get("query_variants", []),
            loop_cnt=loop_cnt + 1
        )
    except Exception as e:
        # 오류 시 원본 질문 사용
        return ChatbotState(
            current_query=state["question"],
            query_variants=[state["question"]],
            loop_cnt=loop_cnt + 1
        )

# 5)
async def gpt_query_rewriter_node(state: ChatbotState):
    """
    GPT를 이용한 쿼리 재작성 노드 (LLMEvaluator 기반 Best Query 선택)
    """

    loop_cnt = state.get("loop_cnt", 0)
    try:
        if loop_cnt == 0:
            query_variants = await multi_strategy_query_expansion(state["question"])
            best_query, best_evaluation = await select_best_query_with_llm_evaluator(
                query_variants, state["question"]
            )
        elif loop_cnt == 1:
            existing_variants = state.get("query_variants", [state["question"]])
            selected = await select_multiple_best_queries_with_evaluation(
                existing_variants, state["question"], top_k=2
            )
            best_query = selected[1][0] if len(selected) > 1 else selected[0][0]
        elif loop_cnt == 2:
            try:
                best_query = await gpt_rewriter.rewrite(state['question'], "improvement")
            except:
                best_query = state["query_variants"][-1]
        else:
            best_query = state["question"]
        return ChatbotState(
            current_query=best_query,
            query_variants=(query_variants if loop_cnt == 0 else state.get("query_variants", [])),
            loop_cnt=loop_cnt + 1
        )
    except Exception as e:
        return ChatbotState(
            current_query=state["question"],
            query_variants=[state["question"]],
            loop_cnt=loop_cnt+1
        )

# 6)
async def ensemble_search_node(state: ChatbotState):
    """
    Vector DB에서 문서 검색을 수행하는 노드
    """

    current_query = state.get("current_query")
    retriever = setup_mcp_client().get("VectorDB_retriever")
    docs = retriever.invoke(current_query)
    result_text = "\n".join([d.page_content for d in docs])
    return ChatbotState(vector_documents=result_text)

# 7)
async def llm_evaluation_node(state: ChatbotState):
    """
    검색 결과의 품질을 평가하는 노드
    """

    docs_list = [d for d in state.get("vector_documents", "").split("\n") if d]
    if not docs_list:
        return ChatbotState(llm_evaluation=LLMEvaluator()._default("no docs"))
    evaluation = await llm_evaluator.evaluate_search_results(state.get("current_query"), docs_list)
    for field in ["relevance","faithfulness","completeness","overall","feedback","recommended_threshold"]:
        evaluation.setdefault(field, 0.3 if field!="feedback" else "missing")
    return ChatbotState(llm_evaluation=evaluation)

# 8)
async def merge_outputs(state: ChatbotState):
    """
    검색 결과와 평가 피드백을 바탕으로 최종 답변을 생성하는 노드
    """

    question = state['question']
    eval = state.get("llm_evaluation", {})
    overall = eval.get("overall", 0)
    threshold = eval.get("recommended_threshold", 0.6)
    # 평가 점수 미달 시 일반화된 안내 메시지
    if overall < threshold:
        fallback = (
            "현재 문헌 검색으로는 질문하신 사항에 정확히 답변드리기 어렵습니다. "
            "유사한 일반 소아 KMS 치료 지침을 참고하시거나, 질문을 구체화하여 다시 문의해 주세요."
        )
        return ChatbotState(final_answer=fallback, messages=[("assistant", fallback)])
    # 충분한 자료 확보 시 LLM을 이용해 상세 답변 생성
    context = state.get("vector_documents", "")
    prompt = LLM_SYSTEM_PROMPT.format(
        VectorDB=context,
        GraphDB=state.get("neo4j_documents", ""),
        question=state.get("question")
    )
    response = model.invoke(prompt)
    answer = response.content or "죄송합니다. 답변을 생성할 수 없습니다."
    return ChatbotState(final_answer=answer, messages=[("user", question),("assistant", answer)])