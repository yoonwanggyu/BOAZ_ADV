from langchain_core.messages import AIMessage, HumanMessage
import os
from mcp_client import *
from utils import *
from agent import *
from prompt import *
from vectordb_helper import *
from prompt import *
from state import *

# --- [기존] 라우터, 슬랙 결정, Neo4j DB 검색 노드 ---
async def router_agent(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Router Agent ---")
    question = state["question"]
    model_with_tools = model.with_structured_output(tool_router_schema) # tool_router_schema는 아래 셀에서 정의
    response = await model_with_tools.ainvoke([HumanMessage(content=ROUTER_PROMPT), HumanMessage(content=question)])
    print(f"Flow Type: {response.get('flow_type')}")
    return ChatbotState(
        flow_type=response.get("flow_type"),
        tools_query=[response.get("neo4j_query", ""), response.get("vector_db_query", "")]
    )

# --- [추가] 슬랙 사용 여부 판단 노드 ---
def determine_slack_usage(query: str) -> str:
    """간단한 규칙 기반으로 슬랙 사용 여부를 1차 판단하는 헬퍼 함수"""
    SEND_COMMANDS = ["보내줘", "전송해줘", "전달해줘"]
    return 'Yes' if any(cmd in query for cmd in SEND_COMMANDS) or "에게" in query else 'No'

async def decision_slack(state: ChatbotState):
    """사용자 질문을 바탕으로 슬랙 메시지 전송이 필요한지 최종 결정하는 노드"""
    print("\n--- [Node] Decision Slack ---")
    user_query = state["question"]
    
    # 규칙 기반으로 1차 판단
    use_slack = determine_slack_usage(user_query)
    
    # 최종 결정을 response 변수에 저장 (기본값은 규칙 기반 판단 결과)
    response = use_slack
    
    print(f"Slack Decision: {response}")
    return ChatbotState(decision_slack=response)

async def neo4j_db(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Neo4j DB Retriever ---")
    query = state['tools_query'][0]
    if not query: return ChatbotState(neo4j_documents=["Neo4j 쿼리가 제공되지 않았습니다."])
    try:
        neo4j_tool = tools_dict.get("neo4j_retriever")
        raw_result, _ = await neo4j_tool.ainvoke({"query": query})
        result = raw_result
    except Exception as e:
        result = [f"Neo4j 도구 실행 중 오류: {e}"]
    print(f"Neo4j Result: {result}")
    if state['flow_type'] == 'sequential':
        return ChatbotState(neo4j_documents=result, patient_info=str(result))
    return ChatbotState(neo4j_documents=result)

async def generate_vector_query_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Generate VectorDB Query (Sequential) ---")
    prompt = VECTOR_QUERY_GEN_PROMPT.format(question=state['question'], patient_info=state['patient_info'])
    response = await model.ainvoke(prompt)
    generated_query = response.content
    print(f"Generated VectorDB Query: {generated_query}")
    state['tools_query'][1] = generated_query
    return ChatbotState(tools_query=state['tools_query'])

# --- [신규] VectorDB 검색 및 평가 루프 관련 노드 ---
async def gpt_query_rewriter_node(state: ChatbotState) -> ChatbotState:
    """쿼리 재작성 및 최고 쿼리 선택 노드 (헬퍼 함수 명시적 호출)"""
    print(f"\n--- [Node] Query Rewriter (Attempt {state.get('loop_cnt', 0) + 1}) ---")
    loop_cnt = state.get("loop_cnt", 0)
    original_question = state["question"]
    
    # 첫 시도일 경우에만 쿼리 변형 생성 및 최고 쿼리 평가/선택
    if loop_cnt == 0:
        # 1. 여러 전략으로 쿼리 변형 목록 생성 (헬퍼 함수 호출)
        query_variants = await multi_strategy_query_expansion(original_question)
        
        # 2. 생성된 모든 쿼리 변형을 평가하여 최고의 쿼리 하나를 선택 (헬퍼 함수 호출)
        best_query, best_evaluation = await select_best_query_with_llm_evaluator(
            query_variants, 
            original_question
        )
        # 첫 평가 결과를 저장하여 다음 노드(라우팅)에서 사용
        state['llm_evaluation'] = best_evaluation
        state['query_variants'] = query_variants

    # 두 번째 시도부터는 다른 로직 (예: 다른 변형 사용 또는 개선된 재작성)
    else:
        query_variants = state.get("query_variants", [])
        if query_variants:
            # 이전에 생성했던 쿼리 변형 목록에서 다음 쿼리를 순환하며 선택
            best_query = query_variants[loop_cnt % len(query_variants)]
            print(f"다음 쿼리 변형 시도: {best_query}")
        else:
            # 쿼리 변형이 없으면 원본 질문 사용
            best_query = original_question

    return ChatbotState(
        current_query=best_query,
        llm_evaluation=state.get('llm_evaluation'), # 평가 결과 유지
        query_variants=state.get('query_variants'), # 변형 목록 유지
        loop_cnt=loop_cnt + 1
    )

async def vector_retrieval_node(state: ChatbotState) -> ChatbotState:
    """VectorDB에서 문서를 검색하는 노드 (MCP Tool 호출 방식)"""
    print(f"\n--- [Node] VectorDB Retriever ---")
    current_query = state.get("current_query")
    print(f"Retrieve with query: {current_query}")

    try:
        # 도구 딕셔너리에서 VectorDB 리트리버 도구를 가져옴
        vectordb_tool = tools_dict.get("VectorDB_retriever")
        if not vectordb_tool:
            raise ValueError("VectorDB_retriever 도구를 찾을 수 없습니다.")

        # MCP 도구를 비동기적으로 호출
        # mcp 도구의 결과는 (content, artifact) 튜플 형태일 수 있으므로 첫 번째 요소(content)를 사용
        response_tuple = await vectordb_tool.ainvoke({"query": current_query})
        result_text = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)

    except Exception as e:
        print(f"!!! VectorDB 검색 중 오류 발생: {e}")
        result_text = f"VectorDB 검색에 실패했습니다: {e}"

    return ChatbotState(vector_documents=result_text)

async def llm_evaluation_node(state: ChatbotState) -> ChatbotState:
    """검색 결과 품질 평가 노드"""
    # 첫 시도(loop_cnt==1)에서는 rewriter_node에서 이미 평가했으므로 건너뛸 수 있으나,
    # 재시도 루프에서는 새로 검색된 결과에 대한 평가가 필요하므로 실행합니다.
    if state.get('loop_cnt', 0) > 1:
        print(f"\n--- [Node] LLM Re-Evaluation ---")
        docs_list = [d.strip() for d in state.get("vector_documents", "").split("\n\n") if d.strip()]
        evaluation = await llm_evaluator.evaluate_search_results(state.get("current_query"), docs_list)
        print(f"Re-Evaluation Score: {evaluation.get('overall', 0):.3f}")
        return ChatbotState(llm_evaluation=evaluation)
    else:
        # 첫 번째 루프에서는 gpt_query_rewriter_node에서 계산된 평가를 그대로 사용
        print(f"\n--- [Node] LLM Evaluation (Using Initial Score) ---")
        return ChatbotState(llm_evaluation=state.get('llm_evaluation'))

# --- [수정] 최종 답변 생성 및 슬랙 전송 노드 ---
async def merge_and_respond_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Merge and Respond ---")
    
    # LLM을 이용해 상세 답변 생성
    prompt = LLM_SYSTEM_PROMPTY.format(
        Neo4j=state.get("neo4j_documents", ""),
        VectorDB=state.get("vector_documents", ""),
        question=state.get("question")
    )
    response = await model.ainvoke(prompt)
    final_answer = response.content
    print(f"Final Answer Generated: {final_answer[:100]}...")

    # 슬랙 전송 로직 (도구 직접 호출)
    slack_response_text = ""
    if state.get('decision_slack', 'no').lower() == 'yes':
        print("--- Sending to Slack (Direct Call) ---")
        try:
            target_channel_id = os.getenv("SLACK_CHANNEL")
            if not target_channel_id: raise ValueError("SLACK_CHANNEL 환경 변수 미설정")
            
            slack_tool = tools_dict.get("slack_post_message")
            if not slack_tool: raise ValueError("slack_post_message 도구 없음")

            tool_input = {"channel_id": target_channel_id, "text": final_answer}
            slack_response = await slack_tool.ainvoke(tool_input)
            slack_response_text = slack_response[0] if isinstance(slack_response, tuple) else str(slack_response)
            print(f"Slack Direct Call Response: {slack_response_text}")
        except Exception as e:
            slack_response_text = f"슬랙 전송 중 오류 발생: {e}"
            print(f"!!! {slack_response_text}")

    return ChatbotState(
        final_answer=final_answer,
        slack_response=slack_response_text,
        messages=[HumanMessage(content=state['question']), AIMessage(content=final_answer)]
    )