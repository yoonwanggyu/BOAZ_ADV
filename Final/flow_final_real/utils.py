from state import *

max_attempts = 3

# 라우터 에이전트용 함수 스키마
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


# 라우터의 결정에 따라 다음 노드로 분기하기 위해 flow_type을 반환
def route_after_router(state: ChatbotState) -> str:
    flow_type = state['flow_type']
    print(f"--- 라우팅 결정: {flow_type} ---")
    return flow_type


# Neo4j 노드 이후의 조건부 분기 함수
def route_after_neo4j(state: ChatbotState) -> str:
    """Neo4j 검색 후, 흐름에 따라 다음 행동을 결정하는 키워드를 반환"""
    flow_type = state['flow_type']
    if flow_type == 'sequential':
        return "generate_vector_query"  # sequential -> VectorDB 쿼리 생성
    elif flow_type == 'parallel':
        return "start_vector_db_flow"   # parallel -> VectorDB 흐름 시작
    else: # neo4j_only
        return "go_to_merge"            # neo4j_only -> 바로 최종 답변으로

# 적응형 쿼리 최적화 이후의 조건부 분기 함수 (항상 검색 후 평가에서 완료 판단)
def route_after_adaptive_optimization(state: ChatbotState) -> str:
    loop_cnt = state.get("loop_cnt", 0)
    print(f"--- 라우팅: 쿼리 생성 완료 (시도 {loop_cnt}). 벡터 검색을 진행합니다... ---")
    return "continue_optimization"


# LLM 평가 이후의 조건부 분기 함수
def route_after_evaluation(state: ChatbotState) -> str:
    """LLM 평가 결과에 따라 다음 행동을 결정하는 키워드를 반환"""
    evaluation = state.get("llm_evaluation", {})
    loop_cnt = state.get("loop_cnt", 0)
    should_retry = evaluation.get("overall", 0) < evaluation.get("recommended_threshold", 0.7) and loop_cnt < max_attempts
    
    if should_retry:
        print(f"--- 라우팅: 품질이 부족합니다 (점수: {evaluation.get('overall', 0):.3f}). 재시도 중... ---")
        return "retry_rewrite"
    else:
        print(f"--- 라우팅: 품질이 충분하거나 최대 재시도 횟수에 도달했습니다. 답변 생성 중... ---")
        return "generate_answer"


