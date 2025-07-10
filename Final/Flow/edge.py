from nodes import *
from langgraph.graph import StateGraph, START, END

builder = StateGraph(ChatbotState)
MAX_RETRY = 4

# 노드 추가
builder.add_node("router_agent", router_agent)
builder.add_node("decision_slack", decision_slack)
builder.add_node("neo4j_db", neo4j_db)
builder.add_node("gpt_query_rewriter_node", gpt_query_rewriter_node)
builder.add_node("ensemble_search", ensemble_search_node)
builder.add_node("llm_evaluation", llm_evaluation_node)
builder.add_node("merge_outputs", merge_outputs)

# 엣지 연결
builder.add_edge(START, "router_agent")
builder.add_edge(START, "decision_slack")
builder.add_edge(START, "gpt_query_rewriter")

def should_continue(state: ChatbotState):
    """
    라우터의 결정에 따라 다음 노드로 분기합니다.
    """
    flow_type = state['flow_type']
    return flow_type

def after_neo4j(state: ChatbotState):
    """
    Neo4j 검색 후, 순차 흐름일 경우 VectorDB 쿼리 생성 노드로, 그 외에는 최종 응답 노드로 분기합니다.
    """
    if state['flow_type'] == 'sequential':
        return "generate_vector_query"
    else:
        return "merge_and_respond"

# 라우터 에이전트 이후의 조건부 분기
builder.add_conditional_edges(
    "router_agent",
    should_continue,
    {
        "sequential": "neo4j_db",
        "parallel": "neo4j_db", # 병렬도 일단 Neo4j부터 시작
        "neo4j_only": "neo4j_db",
        "vector_db_only": "vector_db",
    }
)


builder.add_edge("gpt_query_rewriter", "ensemble_search")
builder.add_edge("ensemble_search", "llm_evaluation")

async def _llm_based_route(state: ChatbotState):
    """평가 결과에 따른 라우팅 결정 함수"""
    evaluation = state.get("llm_evaluation", {})
    loop_cnt = state.get("loop_cnt", 0)
    
    # 평가 정보 로깅
    overall_score = evaluation.get("overall", 0)
    threshold = evaluation.get("recommended_threshold", 0.6)
    print(f"라우팅 평가: 점수 {overall_score:.3f} vs 임계값 {threshold:.3f}")
    print(f"현재 시도 횟수: {loop_cnt}/{MAX_RETRY}")
    
    try:
        should_retry = await llm_evaluator.should_retry_search(evaluation, loop_cnt, MAX_RETRY)
        result = "retry_rewrite" if should_retry else "generate_answer"
        
        if should_retry:
            print(f"품질 부족으로 재시도: {result}")
            print(f"피드백: {evaluation.get('feedback', '피드백 없음')}")
        else:
            print(f"품질 충족 또는 최대 시도 도달: {result}")
        
        return result
        
    except Exception as e:
        print(f"라우팅 결정 중 오류: {e}")
        # 오류 시 답변 생성으로 진행
        return "generate_answer"

builder.add_conditional_edges(
    "llm_evaluation",
    _llm_based_route,
    {
        "retry_rewrite": "gpt_query_rewriter",
        "generate_answer": "merge_outputs",
    },
)

sg.add_edge("merge_outputs", END)