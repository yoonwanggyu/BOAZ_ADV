from langchain_core.messages import AIMessage, HumanMessage
from mcp_client import *
from utils import *
from agent import *
from prompt import *
from state import *
from dotenv import load_dotenv
from query_rewrite_llm_evaluator import *
import os
import re
import json

load_dotenv()

# MCP 클라이언트 도구 설정
tools_dict = setup_mcp_client_sync()

# 전역 인스턴스 생성
adaptive_optimizer = AdaptiveQueryOptimizer(max_attempts=3)  # 최대 3회 시도
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

# 슬랙 사용 여부 판단 노드(간단한 규칙 기반으로 슬랙 사용 여부를 1차 판단하는 헬퍼 함수)
def determine_slack_usage(query: str) -> str:
    SEND_COMMANDS = ["보내줘", "전송해줘", "전달해줘"]
    return 'Yes' if any(cmd in query for cmd in SEND_COMMANDS) or "에게" in query else 'No'

# 슬랙 메시지 전송 최종 결정 노드(사용자 질문을 바탕으로 슬랙 메시지 전송이 필요한지 최종 결정하는 노드)
async def decision_slack(state: ChatbotState):
    print("\n--- [Node] Decision Slack ---")
    user_query = state["question"]
    
    # 규칙 기반으로 1차 판단
    use_slack = determine_slack_usage(user_query)
    
    # 최종 결정을 response 변수에 저장(기본값은 규칙 기반 판단 결과)
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
    print(f"Neo4j 결과: {result}")
    if state['flow_type'] == 'sequential':
        return ChatbotState(patient_info=result)
    return ChatbotState(patient_info=result)

# 벡터 DB 쿼리 생성 노드
async def generate_vector_query_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Generate VectorDB Query (Sequential) ---")
    prompt = VECTOR_QUERY_GEN_PROMPT.format(question=state['question'], patient_info=state['patient_info'])
    response = await model.ainvoke(prompt)
    generated_query = response.content
    print(f"생성된 벡터DB 검색용 쿼리: {generated_query}")
    state['tools_query'][1] = generated_query
    return ChatbotState(tools_query=state['tools_query'])

# 적응형 쿼리 재작성 노드 
async def adaptive_query_rewriter_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Adaptive Query Rewriter ---")
    
    question = state["tools_query"][1]
    prev_eval = state.get("llm_evaluation", {})
    
    if prev_eval:
        print(f"이전 평가 결과: {prev_eval.get('overall', 0):.3f}/1.0")
        print(f"상세: 관련성 {prev_eval.get('relevance', 0):.2f}, 신뢰성 {prev_eval.get('faithfulness', 0):.2f}, 완성도 {prev_eval.get('completeness', 0):.2f}")
    else:
        print("최초 시도: 이전 평가 결과 없음")
    
    # 조건부 쿼리 생성(평가 결과에 따라 조기 종료 가능)
    query = await adaptive_optimizer.get_search_query(
        question,
        evaluation_result=prev_eval,
        state=state
    )
    state["current_query"] = query
    
    # 만족스러운 결과를 얻었거나 최대 시도에 도달했는지 확인
    optimization_status = adaptive_optimizer.get_optimization_status()
    print(f"최적화 현황:")
    print(f"진행: {optimization_status['attempt_count']}/{optimization_status['max_attempts']}회")
    print(f"목표점수: {optimization_status['satisfaction_threshold']}")
    print(f"현재최고: {optimization_status['best_score']:.3f} (시도 {optimization_status['best_attempt']})")
    print(f"만족여부: {'달성' if optimization_status['is_satisfied'] else '진행중'}")
    
    # 상태 정보 저장(최종 완료 판단은 llm_evaluation_node에서)
    state["loop_cnt"] = adaptive_optimizer.attempt_count
    
    print(f"다음 단계: 벡터 검색 및 평가 진행")
    print(f"생성된 쿼리: {query}")
    
    return state

# VectorDB에서 문서를 검색하는 노드
async def vector_retrieval_node(state: ChatbotState) -> ChatbotState:
    print(f"\n--- [Node] VectorDB Retriever ---")
    current_query = state.get("current_query")
    optimization_completed = state.get("optimization_completed", False)
    
    print(f"현재 쿼리: {current_query}")
    print(f"최적화 완료 상태: {optimization_completed}")

    try:
        # 도구 딕셔너리에서 VectorDB 리트리버 도구를 가져옴
        vectordb_tool = tools_dict.get("VectorDB_retriever")
        if not vectordb_tool:
            raise ValueError("VectorDB_retriever 도구를 찾을 수 없습니다.")

        # MCP 도구를 비동기적으로 호출
        # MCP 도구의 결과는 (content, artifact) 튜플 형태일 수 있으므로 첫 번째 요소(content)를 사용
        response_tuple = await vectordb_tool.ainvoke({"query": current_query})
        result_text = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
        print(f"VectorDB 검색 결과 길이: {len(result_text)} 문자")
        
        # 최적화가 완료된 경우 추가 정보 출력
        if optimization_completed:
            print("쿼리 최적화가 완료된 상태의 최종 검색 결과")
        
    except Exception as e:
        print(f"VectorDB 검색 중 오류 발생: {e}")
        result_text = f"VectorDB 검색에 실패했습니다: {e}"

    return ChatbotState(vector_documents=result_text)

# 검색 결과 품질 평가 노드
async def llm_evaluation_node(state: ChatbotState) -> ChatbotState:
    loop_cnt = state.get('loop_cnt', 0)
    print(f"\n--- [Node] LLM Evaluation (시도 {loop_cnt}) ---")
    
    # 검색 결과와 쿼리 가져오기
    current_query = state.get("current_query", "")
    vector_documents = state.get("vector_documents", "")
    
    if not vector_documents:
        print("검색 결과가 없습니다.")
        state["llm_evaluation"] = {"overall": 0, "feedback": "검색 결과 없음"}
        return state
    
    # 문서 리스트로 변환
    docs_list = [d.strip() for d in vector_documents.split("\n\n") if d.strip()]
    
    # LLM 평가 수행
    evaluation = await llm_evaluator.evaluate_search_results(current_query, docs_list)
    if not evaluation:
        evaluation = {"overall": 0, "feedback": "평가 실패"}
    
    # 평가 결과를 AdaptiveQueryOptimizer에 업데이트
    adaptive_optimizer.update_evaluation(current_query, evaluation, vector_documents)
    
    # 평가 결과 출력
    overall_score = evaluation.get("overall", 0)
    print(f"LLM 평가 완료:")
    print(f"종합점수: {overall_score:.3f}/1.0")
    print(f"세부점수: 관련성 {evaluation.get('relevance', 0):.2f}, 신뢰성 {evaluation.get('faithfulness', 0):.2f}, 완성도 {evaluation.get('completeness', 0):.2f}")
    
    # 재시도 필요성 판단
    should_retry = await llm_evaluator.should_retry_search(
        evaluation, 
        adaptive_optimizer.attempt_count, 
        adaptive_optimizer.max_attempts
    )
    
    # 최적화 완료 여부 재확인 (평가 점수 포함)
    optimization_status = adaptive_optimizer.get_optimization_status()
    optimization_completed = (
        optimization_status["is_satisfied"] or 
        adaptive_optimizer.attempt_count >= adaptive_optimizer.max_attempts or
        overall_score >= adaptive_optimizer.satisfaction_threshold
    )
    
    # 최적화가 완료된 경우 최고 성능 쿼리로 최종 설정
    if optimization_completed:
        final_query, final_evaluation, final_documents = adaptive_optimizer.get_final_query_and_evaluation()
        state["current_query"] = final_query
        state["llm_evaluation"] = final_evaluation
        state["vector_documents"] = final_documents  # 최고 성능 쿼리의 검색 결과로 업데이트
        print(f"최종 확정:")
        print(f"선택쿼리: {final_query[:80]}...")
        print(f"확정점수: {final_evaluation.get('overall', 0):.3f}")
        print(f"선택문서: {len(final_documents)} 문자")
    else:
        state["llm_evaluation"] = evaluation
    
    # 상태 업데이트
    state["should_retry_optimization"] = should_retry and not optimization_completed
    state["optimization_completed"] = optimization_completed
    
    next_action = "추가 최적화 시도" if should_retry and not optimization_completed else "답변 생성"
    print(f"다음 단계: {next_action}")
    print(f"최적화 상태: {'완료' if optimization_completed else '진행중'}")
    print(f"재시도 여부: {'예' if should_retry and not optimization_completed else '아니오'}")
    
    return state

# 최종 답변을 생성하고, 동적으로 사용자 ID를 찾아 @멘션하여 슬랙으로 전송하는 노드
async def merge_and_respond_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Merge and Respond ---")
    question = state.get("question", "")
    final_answer = ""
    slack_response_text = ""

    try:
        # 1.평가 점수 확인 및 조건부 답변 생성
        evaluation = state.get("llm_evaluation", {})
        evaluation_score = evaluation.get("overall", 0)
        flow_type = state.get("flow_type", "")
        
        print(f"Evaluation Score: {evaluation_score}")
        print(f"Flow Type: {flow_type}")
        
        # Neo4j와 VectorDB 정보 미리 가져오기
        neo4j_info = state.get("patient_info", "")
        vectordb_info = state.get("vector_documents", "")
        
        # Neo4j only 플로우는 평가 없이 바로 정상 답변 생성
        if flow_type == "neo4j_only":
            print("--- Neo4j Only 플로우: 평가 건너뛰고 정상 답변 생성 ---")
            prompt = LLM_SYSTEM_PROMPTY.format(
                Neo4j=neo4j_info,
                VectorDB=vectordb_info,
                question=question
            )
            response = await model.ainvoke(prompt)
            final_answer = response.content
            print(f"Neo4j 전용 응답 생성: {final_answer[:100]}...")
        elif evaluation_score < 0.7:
            # 0.7 미만인 경우 피드백 기반 응답 생성
            print("--- 피드백 기반 답변 사용(Score < 0.7) ---")
            feedback_text = evaluation.get("reasoning", "검색 결과의 품질이 낮습니다.")
            
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
            print("--- 정상적 답변 생성 과정(Score >= 0.7) ---")
            prompt = LLM_SYSTEM_PROMPTY.format(
                Neo4j=neo4j_info,
                VectorDB=vectordb_info,
                question=question
            )
            response = await model.ainvoke(prompt)
            final_answer = response.content
            print(f"표준 응답 생성: {final_answer[:100]}...")

        # 답변에 사용된 검색 결과 부분 추출(한글 프롬프트)
        if (neo4j_info and neo4j_info.strip()) or (vectordb_info and vectordb_info.strip()):
            print("\n--- 답변에 사용된 검색 결과 추출 중 ---")
            
            source_extraction_prompt = f"""다음은 생성된 답변과 검색 결과입니다.

            생성된 답변:
            {final_answer}

            검색 결과:
            Neo4j 환자 정보:
            {neo4j_info if neo4j_info else "없음"}

            VectorDB 의학 문헌:
            {vectordb_info if vectordb_info else "없음"}

            임무: 위 답변을 생성하는데 실제로 사용된 검색 결과 중 가장 관련 있는 부분을 원문 그대로 추출해주세요.

            출력 형식:
            - Neo4j에서 사용된 부분:
            [실제 사용된 환자 정보 부분을 원문 그대로 인용]

            - VectorDB에서 사용된 부분:  
            [실제 사용된 의학 문헌 부분을 원문 그대로 인용]

            ===================================

            만약 특정 소스가 사용되지 않았다면 "사용되지 않음"이라고 표시하세요.
            반드시 원문을 그대로 인용하고, 요약하거나 변형하지 마세요.
            
            주의사항:
            - 줄바꿈 이스케이프 시퀀스, <div> 등의 HTML 태그는 제거하고 순수 텍스트만 추출하세요."""

            source_response = await model.ainvoke(source_extraction_prompt)

        # 2. 슬랙 전송 결정 여부에 따라 @멘션 로직 실행
        recipient_name = None
        text_to_send = ""
        
        if state.get('decision_slack', 'no').lower() == 'yes':
            print("--- @mention과 함께 슬랙 전송(Dynamic User Lookup) ---")

            # .env 파일에서 공용 채널 ID 가져오기
            target_channel_id = os.getenv("SLACK_CHANNEL")
            if not target_channel_id:
                raise ValueError("SLACK_CHANNEL 환경 변수가 .env 파일에 설정되지 않았습니다.")

            # 정교한 정규 표현식으로 수신인 이름 추출
            match = re.search(r"(\S+)\s*(?:에게|님에게|한테)", question)
            if match:
                recipient_name = match.group(1).strip()
            
            if not recipient_name:
                raise ValueError("질문에서 수신인 이름을 찾을 수 없습니다. (예: 'OOO에게')")
            print(f"Recipient Name Extracted: {recipient_name}")

            # 사용자 ID를 안전하게 조회하고 올바르게 파싱
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

            # @멘션을 포함한 최종 메시지 텍스트 생성
            user_name = state.get("user_name", "사용자")
            source_content = source_response.content if source_response else "검색 결과 추출을 건너뛰었습니다."
            text_to_send = f"{user_name}님이 전달하는 메세지입니다.\n<@{user_id_to_mention}> 님의 업무 보조를 위해 전송된 정보입니다.\n\n- {final_answer}\n\n [정답 근거] \n\n{source_content}"

            # slack_post_message 도구를 안전하게 호출
            slack_tool = tools_dict.get("slack_post_message")
            if not slack_tool:
                raise ValueError("slack_post_message 도구를 찾을 수 없습니다.")
            
            tool_input = {"channel_id": target_channel_id, "text": text_to_send}
            
            raw_slack_response = await slack_tool.ainvoke(tool_input)
            slack_response_text = str(raw_slack_response[0]) if isinstance(raw_slack_response, tuple) else str(raw_slack_response)
            
            print(f"Slack Direct Call Response: {slack_response_text}")

    except Exception as e:
        error_message = f"슬랙 전송 또는 답변 생성 중 오류 발생: {e}"
        print(f"{error_message}")
        slack_response_text = error_message
        if not final_answer:
            final_answer = "답변을 생성하는 중 오류가 발생했습니다."

    # 3. 최종 상태 반환
    slack_response = ""
    if recipient_name and text_to_send:
        slack_response = f"{user_name}님이 전달하는 메세지입니다." + recipient_name + text_to_send[text_to_send.index("님의 업무 보조"):]
    
    return ChatbotState(
        final_answer=final_answer,
        slack_response=slack_response,
        messages=[HumanMessage(content=question), AIMessage(content=final_answer)]
    )

# 상태 초기화 노드(한 사이클 종료 후 ChatbotState의 모든 필드를 기본값으로 초기화)
async def reset_state_node(state: ChatbotState) -> ChatbotState:
    print("\n--- [Node] Reset State ---")
    adaptive_optimizer.reset()  # 전역 optimizer 상태도 초기화
    return ChatbotState(
        question="",
        flow_type="",
        patient_info="",
        decision_slack="",
        tools_query=["", ""],
        final_answer="",
        slack_response="",
        messages=state["messages"],  # 이전 messages 유지
        current_query="",
        query_variants=[],
        vector_documents="",
        llm_evaluation={},
        loop_cnt=0,
        optimization_completed=False,
        should_retry_optimization=False
    )

