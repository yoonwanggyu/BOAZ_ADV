from nodes import *
from langgraph.graph import StateGraph, START, END
from state import *
from langgraph.checkpoint.memory import MemorySaver

# 채팅봇 그래프를 설정하고 반환
def create_chatbot_graph():
    workflow = StateGraph(ChatbotState)
    memory = MemorySaver()

    # 1. 모든 노드 정의
    workflow.add_node("router_agent", router_agent)
    workflow.add_node("decision_slack_node", decision_slack)
    workflow.add_node("neo4j_db", neo4j_db)
    workflow.add_node("generate_vector_query", generate_vector_query_node)
    workflow.add_node("adaptive_query_rewriter", adaptive_query_rewriter_node)
    workflow.add_node("vector_retrieval", vector_retrieval_node)
    workflow.add_node("llm_evaluation_node", llm_evaluation_node)
    workflow.add_node("merge_and_respond", merge_and_respond_node)

    # 2. 시작점(START) 엣지 연결
    # 라우터와 슬랙 결정은 병렬로 시작
    workflow.add_edge(START, "router_agent")
    workflow.add_edge(START, "decision_slack_node")

    # 3. 라우터 이후의 조건부 분기 설정
    workflow.add_conditional_edges(
        "router_agent",
        route_after_router, # route_after_router는 이제 flow_type을 그대로 반환
        {
            "neo4j_only": "neo4j_db",
            "vector_db_only": "adaptive_query_rewriter", # VectorDB가 필요하면 바로 쿼리 재작성 루프로 진입
            "parallel": "neo4j_db",                 
            "sequential": "neo4j_db",
        }
    )

    # 4. Neo4j 노드 이후의 조건부 분기 설정
    workflow.add_conditional_edges(
        "neo4j_db",
        route_after_neo4j,
        {
            "go_to_merge": "merge_and_respond",            # 'go_to_merge' 키워드는 merge_and_respond 노드로
            "generate_vector_query": "generate_vector_query",
            "start_vector_db_flow": "adaptive_query_rewriter"   # 'start_vector_db_flow' 키워드는 gpt_query_rewriter 노드로
        }
    )


    # 5. 순차(Sequential) 흐름의 나머지 엣지 연결
    workflow.add_edge("generate_vector_query", "adaptive_query_rewriter")

    # 6. VectorDB 검색/평가 루프의 엣지 연결
    workflow.add_edge("adaptive_query_rewriter", "vector_retrieval")
    workflow.add_edge("vector_retrieval", "llm_evaluation_node")

    # 7. LLM 평가 이후의 조건부 분기(재시도 루프)
    workflow.add_conditional_edges(
        "llm_evaluation_node",
        route_after_evaluation,
        {
            "retry_rewrite": "adaptive_query_rewriter",
            "generate_answer": "merge_and_respond", # 'generate_answer' 키워드는 merge_and_respond 노드로
        }
    )

    # 8. 종료 엣지
    workflow.add_edge("merge_and_respond", END)

    # 9. 그래프 컴파일
    graph = workflow.compile(checkpointer=memory)
    print("최종 그래프 컴파일 완료.")
    return graph