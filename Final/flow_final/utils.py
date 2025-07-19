from state import *

max_retry_attempts = 3

# 라우터 에이전트용 함수 스키마
tool_router_schema = {
    "name": "route_question",
    "description": "Analyzes user question intent to determine the most appropriate data retrieval path and required queries for each database.",
    "parameters": {
        "type": "object",
        "properties": {
            "flow_type": {
                "type": "string",
                "enum": ["sequential", "parallel", "neo4j_only", "vector_db_only"],
                "description": "Data processing flow most suitable for the question"
            },
            "neo4j_query": {
                "type": "string",
                "description": """Natural language query for retrieving structured patient-specific clinical information from Neo4j patient database.
                Use when user questions contain clear patient data-related terms such as 'patient', 'patient records', 'surgical history', 'diagnosis', etc.
                Generated only when flow_type is 'neo4j_only', 'parallel', or 'sequential'."""
            },
            "vector_db_query": {
                "type": "string",
                "description": """Natural language query for searching general medical/clinical knowledge from Vector DB.
                Use for questions about medical concepts, procedures, and guidelines unrelated to specific patients, such as 'general anesthesia', 'ketamine', 'surgical complications', etc.
                Generated only when flow_type is 'vector_db_only' or 'parallel'. This field is not used in 'sequential' flow."""
            }
        },
        "required": ["flow_type"]
    }
}


# 라우터 결정 이후 조건부 분기 함수(flow_type 문자열 자체를 반환하고, add_conditional_edges의 딕셔너리가 이 값을 키로 사용해 실제 목적지 노드를 서치)
def route_after_router(state: ChatbotState) -> str:
    flow_type = state['flow_type']
    print(f"--- Routing Decision: {flow_type} ---")
    return flow_type


# Neo4j 노드 이후의 조건부 분기 함수(Neo4j 검색 후, 흐름에 따라 다음 행동을 결정하는 키워드를 반환)
def route_after_neo4j(state: ChatbotState) -> str:
    flow_type = state['flow_type']
    if flow_type == 'sequential':
        return "generate_vector_query"  # sequential -> VectorDB 쿼리 생성
    elif flow_type == 'parallel':
        return "start_vector_db_flow"   # parallel -> VectorDB 흐름 시작
    else: # neo4j_only
        return "go_to_merge"            # neo4j_only -> 바로 최종 답변 생성

# 적응형 쿼리 최적화 이후의 조건부 분기 함수 (항상 검색 후 평가에서 완료 판단)
def route_after_adaptive_optimization(state: ChatbotState) -> str:
    loop_cnt = state.get("loop_cnt", 0)
    print(f"--- Routing: 쿼리 생성 완료 (시도 {loop_cnt}). 벡터 검색을 진행합니다... ---")
    return "continue_optimization"

# LLM 평가 이후의 조건부 분기 함수(LLM 평가 결과에 따라 다음 행동을 결정하는 키워드를 반환)
def route_after_evaluation(state: ChatbotState) -> str:
    evaluation = state.get("llm_evaluation", {})
    loop_cnt = state.get("loop_cnt", 0)
    should_retry = evaluation.get("overall", 0) < evaluation.get("recommended_threshold", 0.7) and loop_cnt < max_retry_attempts
    
    if should_retry:
        print(f"--- Routing: Quality insufficient (Score: {evaluation.get('overall', 0):.3f}). Retrying... ---")
        return "retry_rewrite"
    else:
        print(f"--- Routing: Quality sufficient or max retries reached. Generating answer... ---")
        return "generate_answer"


