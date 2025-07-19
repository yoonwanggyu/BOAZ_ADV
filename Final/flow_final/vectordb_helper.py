from typing import List, Dict
from pinecone_server import *
from query_rewrite_llm_evaluator import *
from mcp_client import *

tools_dict = setup_mcp_client_sync()
adaptive_optimizer = AdaptiveQueryOptimizer()
llm_evaluator = LLMEvaluator()

# 실제 로직은 AdaptiveQueryOptimizer와 LLMEvaluator 클래스에서 처리
async def select_best_query_with_llm_evaluator(query_variants, original_question=""):
    vectordb_tool = tools_dict.get("VectorDB_retriever")
    return await llm_evaluator.select_best_query(query_variants, vectordb_tool, original_question)

async def select_multiple_best_queries_with_evaluation(query_variants, original_question, top_k=2):
    vectordb_tool = tools_dict.get("VectorDB_retriever")
    return await llm_evaluator.select_multiple_queries(query_variants, vectordb_tool, original_question, top_k)