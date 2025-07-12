from nodes import *
from langgraph.graph import StateGraph, START, END
from state import *

def create_chatbot_graph():
    """채팅봇 그래프를 생성하고 반환합니다."""
    from langgraph.checkpoint.memory import MemorySaver
    
    workflow = StateGraph(ChatbotState)
    memory = MemorySaver()

    # 1. 모든 노드 정의 - 충돌하는 이름들 변경
    workflow.add_node("router_agent", router_agent)
    workflow.add_node("slack_decision_node", decision_slack)           # decision_slack → slack_decision_node
    workflow.add_node("neo4j_db", neo4j_db)
    workflow.add_node("generate_vector_query", generate_vector_query_node)
    # --- VectorDB 검색/평가 루프 노드들 ---
    workflow.add_node("gpt_query_rewriter", gpt_query_rewriter_node)
    workflow.add_node("vector_retrieval", vector_retrieval_node)
    workflow.add_node("llm_evaluation_node", llm_evaluation_node)      # llm_evaluation → llm_evaluation_node
    # --- 최종 노드 ---
    workflow.add_node("merge_and_respond", merge_and_respond_node)

    # 2. 시작점(START) 엣지 연결
    workflow.add_edge(START, "router_agent")
    workflow.add_edge(START, "slack_decision_node")  # 변경된 이름 사용

    # 3. 라우터 이후의 조건부 분기 설정
    workflow.add_conditional_edges(
        "router_agent",
        route_after_router,
        {
            "neo4j_only": "neo4j_db",
            "vector_db_only": "gpt_query_rewriter",
            "parallel": "neo4j_db",
            "sequential": "neo4j_db",
        }
    )

    # 4. Neo4j 노드 이후의 조건부 분기 설정
    workflow.add_conditional_edges(
        "neo4j_db",
        route_after_neo4j,
        {
            "merge_and_respond": "merge_and_respond",
            "generate_vector_query": "generate_vector_query",
            "gpt_query_rewriter": "gpt_query_rewriter"
        }
    )

    # 5. 순차(Sequential) 흐름의 나머지 엣지 연결
    workflow.add_edge("generate_vector_query", "gpt_query_rewriter")

    # 6. VectorDB 검색/평가 루프의 엣지 연결
    workflow.add_edge("gpt_query_rewriter", "vector_retrieval")
    workflow.add_edge("vector_retrieval", "llm_evaluation_node")  # 변경된 이름 사용

    # 7. LLM 평가 이후의 조건부 분기 (재시도 루프)
    workflow.add_conditional_edges(
        "llm_evaluation_node",  # 변경된 이름 사용
        route_after_evaluation,
        {
            "retry_rewrite": "gpt_query_rewriter",
            "generate_answer": "merge_and_respond",
        }
    )

    # 8. 모든 흐름의 종착점 설정
    workflow.add_edge("slack_decision_node", "merge_and_respond")  # 변경된 이름 사용

    # 9. 최종 노드와 종료점(END) 연결
    workflow.add_edge("merge_and_respond", END)

    # 10. 그래프 컴파일
    graph = workflow.compile(checkpointer=memory)
    print("모든 노드가 올바르게 연결된 최종 그래프 컴파일 완료!")
    
    return graph