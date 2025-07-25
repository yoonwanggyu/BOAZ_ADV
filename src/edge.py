from nodes import *
from utils import *
from state import *

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def create_chatbot_graph():
    workflow = StateGraph(ChatbotState)
    memory = MemorySaver()

    workflow.add_node("router_agent", router_agent)
    workflow.add_node("decision_slack_node", decision_slack)
    workflow.add_node("neo4j_db", neo4j_db)
    workflow.add_node("generate_vector_query", generate_vector_query_node)
    workflow.add_node("adaptive_query_rewriter", adaptive_query_rewriter_node)
    workflow.add_node("vector_retrieval", vector_retrieval_node)
    workflow.add_node("llm_evaluation_node", llm_evaluation_node)
    workflow.add_node("merge_and_respond", merge_and_respond_node)
    workflow.add_node("reset_state_node", reset_state_node)

    workflow.add_edge(START, "router_agent")
    workflow.add_edge(START, "decision_slack_node")
    workflow.add_conditional_edges(
        "router_agent",
        route_after_router, 
        {
            "neo4j_only": "neo4j_db",
            "vector_db_only": "adaptive_query_rewriter", 
            "parallel": "neo4j_db",                 
            "sequential": "neo4j_db",
        }
    )
    workflow.add_conditional_edges(
        "neo4j_db",
        route_after_neo4j,
        {
            "go_to_merge": "merge_and_respond",            
            "generate_vector_query": "generate_vector_query",
            "start_vector_db_flow": "adaptive_query_rewriter"  
        }
    )
    workflow.add_edge("generate_vector_query", "adaptive_query_rewriter")
    workflow.add_edge("adaptive_query_rewriter", "vector_retrieval")
    workflow.add_edge("vector_retrieval", "llm_evaluation_node")
    workflow.add_conditional_edges(
        "llm_evaluation_node",
        route_after_evaluation,
        {
            "retry_rewrite": "adaptive_query_rewriter",
            "generate_answer": "merge_and_respond",
        }
    )
    workflow.add_edge("merge_and_respond", "reset_state_node")
    workflow.add_edge("reset_state_node", END)

    graph = workflow.compile(checkpointer=memory)
    print("최종 그래프 컴파일 완료.")

    return graph

