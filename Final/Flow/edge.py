from nodes import *
from langgraph.graph import StateGraph, START, END
from state import *
from langgraph.checkpoint.memory import MemorySaver

def create_chatbot_graph():
    """채팅봇 그래프를 생성하고 반환합니다."""
    
    workflow = StateGraph(ChatbotState)
    memory = MemorySaver()

    # 1. 모든 노드 정의
    workflow.add_node("router_agent", router_agent)
    workflow.add_node("decision_slack_node", decision_slack)
    workflow.add_node("neo4j_db", neo4j_db)
    workflow.add_node("generate_vector_query", generate_vector_query_node)
    workflow.add_node("gpt_query_rewriter", gpt_query_rewriter_node)
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
            "vector_db_only": "gpt_query_rewriter", # VectorDB가 필요하면 바로 쿼리 재작성 루프로 진입
            "parallel": "neo4j_db",                 
            "sequential": "neo4j_db",
        }
    )

    # 4. Neo4j 노드 이후의 조건부 분기 설정
    # workflow.add_conditional_edges(
    #     "neo4j_db",
    #     route_after_neo4j,
    #     {
    #         "merge_and_respond": "merge_and_respond", 
    #         "generate_vector_query": "generate_vector_query",
    #         "gpt_query_rewriter": "gpt_query_rewriter"
    #     }
    # )
    workflow.add_conditional_edges(
        "neo4j_db",
        route_after_neo4j,
        {
            "go_to_merge": "merge_and_respond",            # 'go_to_merge' 키워드는 merge_and_respond 노드로
            "generate_vector_query": "generate_vector_query",
            "start_vector_db_flow": "gpt_query_rewriter"   # 'start_vector_db_flow' 키워드는 gpt_query_rewriter 노드로
        }
    )


    # 5. 순차(Sequential) 흐름의 나머지 엣지 연결
    workflow.add_edge("generate_vector_query", "gpt_query_rewriter")

    # 6. VectorDB 검색/평가 루프의 엣지 연결
    workflow.add_edge("gpt_query_rewriter", "vector_retrieval")
    workflow.add_edge("vector_retrieval", "llm_evaluation_node")

    # 7. LLM 평가 이후의 조건부 분기 (재시도 루프)
    workflow.add_conditional_edges(
        "llm_evaluation_node",
        route_after_evaluation,
        {
            "retry_rewrite": "gpt_query_rewriter",
            "generate_answer": "merge_and_respond", # 'generate_answer' 키워드는 merge_and_respond 노드로
        }
    )

    # 8. 모든 흐름의 종착점 설정
    # ▼▼▼▼▼ 문제의 원인이었던 이 엣지를 삭제합니다 ▼▼▼▼▼
    # workflow.add_edge("decision_slack", "merge_and_respond")
    # decision_slack의 결과는 state에 저장되어 merge_and_respond 노드가 실행될 때 사용되므로, 직접 연결할 필요가 없습니다.

    # 9. 최종 노드와 종료점(END) 연결
    workflow.add_edge("merge_and_respond", END)

    # 10. 그래프 컴파일
    graph = workflow.compile(checkpointer=memory)
    print("모든 문제가 해결된 최종 그래프 컴파일 완료!")
    return graph