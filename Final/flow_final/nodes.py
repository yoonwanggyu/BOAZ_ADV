from langchain_core.messages import AIMessage, HumanMessage
import os
import re
import json
from mcp_client import *
from utils import *
from agent import *
from prompt import *
from vectordb_helper import *
from prompt import *
from state import *
from dotenv import load_dotenv
from query_rewrite_llm_evaluator import *

load_dotenv()

# 전역 인스턴스 생성
adaptive_optimizer = AdaptiveQueryOptimizer()
llm_evaluator = LLMEvaluator()


# 라우터, 슬랙 결정, Neo4j DB 검색 노드
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

# 슬랙 사용 여부 판단 노드
def determine_slack_usage(query: str) -> str:
    """간단한 규칙 기반으로 슬랙 사용 여부를 1차 판단하는 헬퍼 함수"""
    SEND_COMMANDS = ["보내줘", "전송해줘", "전달해줘"]
    return 'Yes' if any(cmd in query for cmd in SEND_COMMANDS) or "에게" in query else 'No'

# 슬랙 메시지 전송 최종 결정 노드
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

# Neo4j DB 검색 노드
async def neo4j_db(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Neo4j DB Retriever ---")
    query = state['tools_query'][0]
    print(f"neo4j로 들어갈 쿼리 : {query}")
    if not query:
        return ChatbotState(neo4j_documents=["Neo4j 쿼리가 제공되지 않았습니다."])
    try:
        neo4j_tool = tools_dict.get("run_contextual_rag")
        raw_result = await neo4j_tool.ainvoke({"query_text": query})
        print("Neo4j MCP 반환값:", raw_result)
        result = raw_result[0] if isinstance(raw_result, (list, tuple)) else raw_result
    except Exception as e:
        result = [f"Neo4j 도구 실행 중 오류: {e}"]
    print(f"Neo4j Result: {result}")
    if state['flow_type'] == 'sequential':
        return ChatbotState(patient_info=result)
    return ChatbotState(patient_info=result)

# 벡터 DB 쿼리 생성 노드
async def generate_vector_query_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Generate VectorDB Query (Sequential) ---")
    prompt = VECTOR_QUERY_GEN_PROMPT.format(question=state['question'], patient_info=state['patient_info'])
    response = await model.ainvoke(prompt)
    generated_query = response.content
    print(f"Generated VectorDB Query: {generated_query}")
    state['tools_query'][1] = generated_query
    return ChatbotState(tools_query=state['tools_query'])

# VectorDB 검색 및 평가 루프 관련 노드
async def adaptive_query_rewriter_node(state: ChatbotState) -> ChatbotState:
    loop_cnt = state.get("loop_cnt", 0)
    prev_eval = state.get("llm_evaluation", {})
    question = state["tools_query"][1]
    query = await adaptive_optimizer.get_search_query(
        question,
        evaluation_result=prev_eval,
        state=state
    )
    state["current_query"] = query

    vectordb_tool = tools_dict.get("VectorDB_retriever")
    response = await vectordb_tool.ainvoke({"query": query})
    docs_str = response[0] if isinstance(response, (list, tuple)) else str(response)
    docs = [d.strip() for d in docs_str.split("\n\n") if d.strip()]

    evaluation = await llm_evaluator.evaluate_search_results(query, docs) or {}
    state["llm_evaluation"] = evaluation

    state["loop_cnt"] = loop_cnt + 1

    return state

# VectorDB에서 문서를 검색하는 노드 (MCP Tool 호출 방식)
async def vector_retrieval_node(state: ChatbotState) -> ChatbotState:
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
        result_text = responsple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
        print(f"VectorDB 검색 결과: {result_text}")
    except Exception as e:
        print(f"!!! VectorDB 검색 중 오류 발생: {e}")
        result_text = f"VectorDB 검색에 실패했습니다: {e}"

    return ChatbotState(vector_documents=result_text)

# 검색 결과 품질 평가 노드
async def llm_evaluation_node(state: ChatbotState) -> ChatbotState:
    # 첫 시도(loop_cnt==1)에서는 rewriter_node에서 이미 평가했으므로 건너뛸 수 있으나,
    # 재시도 루프에서는 새로 검색된 결과에 대한 평가가 필요하므로 실행
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

# 특정 이름으로 Slack 사용자 ID를 찾는지 테스트하는 함수
async def test_find_user_id(name_to_find: str):
    print(f"--- '{name_to_find}'님의 사용자 ID 조회를 시작합니다 ---")
    
    try:
        # 1. 'slack_get_users' 도구를 tools_dict에서 가져옴
        users_tool = tools_dict.get("slack_get_users")
        if not users_tool:
            raise ValueError("slack_get_users 도구를 tools_dict에서 찾을 수 없습니다.")

        # 2. 도구를 호출하여 전체 사용자 목록을 가져옵니다.
        raw_users_response = await users_tool.ainvoke({})
        users_response_str = str(raw_users_response[0]) if isinstance(raw_users_response, tuple) else str(raw_users_response)
        
        # 3. JSON 응답을 파싱하고 'members' 리스트를 추출
        response_data = json.loads(users_response_str)
        if not response_data.get("ok"):
            raise ValueError(f"슬랙 사용자 목록을 가져오는 데 실패했습니다: {response_data.get('error', 'Unknown error')}")
        
        users_list = response_data.get("members", [])
        
        # 4. 리스트를 순회하며 일치하는 사용자를 찾음   
        found_user_id = None
        for user in users_list:
            if name_to_find in user.get('real_name', '') or name_to_find in user.get('name', ''):
                found_user_id = user.get('id')
                break # 찾으면 즉시 중단

        # 5. 결과를 출력
        if found_user_id:
            print(f"\n[결과] 성공: '{name_to_find}'님의 사용자 ID는 '{found_user_id}' 입니다.")
        else:
            print(f"\n[결과] 실패: '{name_to_find}'님을 슬랙 사용자 목록에서 찾을 수 없습니다.")
            print("이름이 정확한지 또는 해당 사용자가 워크스페이스에 존재하는지 확인해주세요.")

    except Exception as e:
        print(f"\n[오류] 테스트 중 오류가 발생했습니다: {e}")

# 최종 답변을 생성하고, 동적으로 사용자 ID를 찾아 @멘션하여 슬랙으로 전송
async def merge_and_respond_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Merge and Respond ---")
    question = state.get("question", "")
    final_answer = ""
    slack_response_text = ""

    try:
        # 1. 평가 점수 확인 및 조건부 답변 생성
        evaluation = state.get("llm_evaluation", {})
        evaluation_score = evaluation.get("overall", 0)
        
        print(f"Evaluation Score: {evaluation_score}")
        
        if evaluation_score < 0.7:
            # 0.7 미만인 경우 피드백 기반 응답 생성
            print("--- Using Feedback-based Response (Score < 0.7) ---")
            feedback_text = evaluation.get("reasoning", "검색 결과의 품질이 낮습니다.")
            
            # Neo4j와 VectorDB 정보도 함께 전달하여 부분적 정보 활용
            neo4j_info = state.get("patient_info", "환자 정보를 찾을 수 없습니다.")
            vectordb_info = state.get("vector_documents", "의학 정보를 찾을 수 없습니다.")
            
            prompt = FEEDBACK_BASED_RESPONSE_PROMPT.format(
                question=question,
                neo4j_info=neo4j_info,
                vectordb_info=vectordb_info,
                feedback=feedback_text,
                score=evaluation_score
            )
            response = await model.ainvoke(prompt)
            final_answer = response.content
            print(f"Feedback-based Answer Generated: {final_answer[:100]}...")
        else:
            # 0.7 이상인 경우 기존 방식으로 답변 생성
            print("--- Using Standard Response (Score >= 0.7) ---")
            prompt = LLM_SYSTEM_PROMPTY.format(
                Neo4j=state.get("patient_info", ""),
                VectorDB=state.get("vector_documents", ""),
                question=question
            )
            response = await model.ainvoke(prompt)
            final_answer = response.content
            print(f"Standard Answer Generated: {final_answer[:100]}...")

        # 2. 슬랙 전송 결정 여부에 따라 @멘션 로직 실행
        if state.get('decision_slack', 'no').lower() == 'yes':
            print("--- Sending to Slack with @mention (Dynamic User Lookup) ---")

            # 2-1. .env 파일에서 공용 채널 ID 가져오기
            target_channel_id = os.getenv("SLACK_CHANNEL")
            if not target_channel_id:
                raise ValueError("SLACK_CHANNEL 환경 변수가 .env 파일에 설정되지 않았습니다.")

            # 2-2. 정교한 정규 표현식으로 수신인 이름 추출
            recipient_name = None
            match = re.search(r"(\S+)\s*(?:에게|님에게|한테)", question)
            if match:
                recipient_name = match.group(1).strip()
            
            if not recipient_name:
                raise ValueError("질문에서 수신인 이름을 찾을 수 없습니다. (예: 'OOO에게')")
            print(f"Recipient Name Extracted: {recipient_name}")

            # 2-3. [수정] 사용자 ID를 안전하게 조회하고 올바르게 파싱
            users_tool = tools_dict.get("slack_get_users")
            if not users_tool:
                raise ValueError("slack_get_users 도구를 찾을 수 없습니다.")
            
            raw_users_response = await users_tool.ainvoke({})
            users_response_str = str(raw_users_response[0]) if isinstance(raw_users_response, tuple) else str(raw_users_response)
            
            # JSON 문자열을 딕셔너리로 파싱
            response_data = json.loads(users_response_str)
            
            # 응답이 성공적이고 'members' 키가 있는지 확인 후, 실제 사용자 리스트를 가져옴
            if response_data.get("ok"):
                users_list = response_data.get("members", [])
            else:
                raise ValueError(f"슬랙 사용자 목록을 가져오는 데 실패했습니다: {response_data.get('error', 'Unknown error')}")

            user_id_to_mention = None
            for user in users_list:
                # user가 이제 딕셔너리이므로 .get() 메소드 정상 작동
                if recipient_name in user.get('real_name', '') or recipient_name in user.get('name', ''):
                    user_id_to_mention = user.get('id')
                    break
            
            if not user_id_to_mention:
                raise ValueError(f"'{recipient_name}'님을 슬랙 사용자로 찾을 수 없습니다.")
            print(f"User ID Found: {user_id_to_mention}")

            # 2-4. @멘션을 포함한 최종 메시지 텍스트 생성
            text_to_send = f"<@{user_id_to_mention}> 님, 요청하신 정보입니다.\n\n{final_answer}"

            # 2-5. slack_post_message 도구를 안전하게 호출
            slack_tool = tools_dict.get("slack_post_message")
            if not slack_tool:
                raise ValueError("slack_post_message 도구를 찾을 수 없습니다.")
            
            tool_input = {"channel_id": target_channel_id, "text": text_to_send}
            
            raw_slack_response = await slack_tool.ainvoke(tool_input)
            slack_response_text = str(raw_slack_response[0]) if isinstance(raw_slack_response, tuple) else str(raw_slack_response)
            
            print(f"Slack Direct Call Response: {slack_response_text}")

    except Exception as e:
        error_message = f"슬랙 전송 또는 답변 생성 중 오류 발생: {e}"
        print(f"!!! {error_message}")
        slack_response_text = error_message
        if not final_answer:
            final_answer = "답변을 생성하는 중 오류가 발생했습니다."

    # 3. 최종 상태 반환
    return ChatbotState(
        final_answer=final_answer,
        slack_response=slack_response_text,
        messages=[HumanMessage(content=question), AIMessage(content=final_answer)]
    )