from state import *

# from mcp_client import MCPTool

# tools_dict = {
#     "VectorDB_retriever": MCPTool("localhost", 8005, "VectorDB_Retriever"),
#     "run_contextual_rag": MCPTool("localhost", 8006, "Neo4j_Retriever"),
# }

# --------
tool_router_schema = {
    "name": "route_question",
    "description": "사용자 질문의 의도를 파악하여 가장 적절한 데이터 조회 경로와 각 DB에 필요한 쿼리를 결정합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "flow_type": {
                "type": "string",
                "enum": ["sequential", "parallel", "neo4j_only", "vector_db_only"],
                "description": "질문에 가장 적합한 데이터 처리 흐름"
            },
            "neo4j_query": {
                "type": "string",
                "description": """Neo4j 환자 DB에서 구조화된 환자별 임상 정보를 조회하기 위한 자연어 쿼리입니다.
                사용자 질문에 '환자', '환자기록', '수술이력', '진단명' 등 명확한 환자 데이터 관련 용어가 포함될 때 사용하세요.
                flow_type이 'neo4j_only', 'parallel', 'sequential'일 경우에만 생성됩니다."""
            },
            "vector_db_query": {
                "type": "string",
                "description": """Vector DB에서 일반적인 의학/임상 지식을 검색하기 위한 자연어 쿼리입니다.
                '전신마취', '케타민', '수술 부작용' 등 특정 환자와 무관한 의학 개념, 절차, 가이드라인에 대한 질문일 때 사용하세요.
                flow_type이 'vector_db_only' 또는 'parallel'일 경우에만 생성됩니다. 'sequential' 흐름에서는 이 필드를 사용하지 않습니다."""
            }
        },
        "required": ["flow_type"]
    }
}
# --------
def route_after_router(state: ChatbotState) -> str:
    """라우터의 결정에 따라 다음 노드로 분기하기 위해 flow_type을 반환"""
    flow_type = state['flow_type']
    print(f"--- Routing Decision: {flow_type} ---")
    # 이 함수는 flow_type 문자열 자체를 반환하고,
    # add_conditional_edges의 딕셔너리가 이 값을 키로 사용해 실제 목적지 노드를 찾습니다.
    return flow_type

# --- [수정] Neo4j 노드 이후의 조건부 분기 함수 ---
def route_after_neo4j(state: ChatbotState) -> str:
    """Neo4j 검색 후, 흐름에 따라 다음 행동을 결정하는 키워드를 반환"""
    flow_type = state['flow_type']
    if flow_type == 'sequential':
        return "generate_vector_query"  # sequential -> VectorDB 쿼리 생성
    elif flow_type == 'parallel':
        return "start_vector_db_flow"   # parallel -> VectorDB 흐름 시작
    else: # neo4j_only
        return "go_to_merge"            # neo4j_only -> 바로 최종 답변으로
MAX_RETRY = 3  # 원하는 재시도 횟수로 수정 가능
# --- [수정] LLM 평가 이후의 조건부 분기 함수 ---
def route_after_evaluation(state: ChatbotState) -> str:
    """LLM 평가 결과에 따라 다음 행동을 결정하는 키워드를 반환"""
    evaluation = state.get("llm_evaluation", {})
    loop_cnt = state.get("loop_cnt", 0)
    should_retry = evaluation.get("overall", 0) < evaluation.get("recommended_threshold", 0.6) and loop_cnt < MAX_RETRY
    
    if should_retry:
        print(f"--- Routing: Quality insufficient (Score: {evaluation.get('overall', 0):.3f}). Retrying... ---")
        return "retry_rewrite"
    else:
        print(f"--- Routing: Quality sufficient or max retries reached. Generating answer... ---")
        return "generate_answer"


