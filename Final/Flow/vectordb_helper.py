from typing import List, Dict
from pinecone_server import *
from query_rewrite_llm_evaluator import *
from mcp_client import *

tools_dict = setup_mcp_client_sync()
gpt_rewriter = GPTQueryRewriter()
llm_evaluator = LLMEvaluator()

# 한글 쿼리를 영어로 선번역 후 동의어 사전을 활용하여 혼합 방식 확장
async def expand_medical_terms(query: str) -> str:
    # 1. 한글이 포함된 경우 영어로 먼저 번역
    if not query.isascii():
        translated_query = await ko2en(query)
        print(f"영어 번역: {translated_query}")
    else:
        translated_query = query
    
    # 2. 번역된 영어 쿼리에서 동의어 사전 매칭하여 혼합 방식 확장
    expanded = translated_query
    translated_lower = translated_query.lower()
    
    for preferred_term, synonyms in PEDIATRIC_TERMS.items():
        # 선호 용어나 동의어가 번역된 쿼리에 포함되어 있는지 확인
        if preferred_term in translated_lower or any(syn in translated_lower for syn in synonyms):
            # 혼합 방식: 가장 관련성 높은 동의어 2-3개만 선택
            relevant_synonyms = select_relevant_synonyms(synonyms, translated_query)
            if relevant_synonyms:
                synonym_phrase = " OR ".join(relevant_synonyms)
                expanded += f" ({synonym_phrase})"
            break  # 첫 번째 매칭만 사용하여 중복 방지
    
    return expanded


def select_relevant_synonyms(synonyms: List[str], original_query: str) -> List[str]:
    """
    동의어 리스트에서 가장 관련성 높은 2-3개 선택 (길이 기준 제거)
    """
    filtered_synonyms = []
    original_lower = original_query.lower()
    
    for syn in synonyms:
        syn_lower = syn.lower()
        # 제외 조건들
        if (len(syn) < 3 or  # 너무 짧은 용어
            len(syn) > 20 or  # 너무 긴 용어
            syn_lower in original_lower or  # 이미 원래 쿼리에 포함된 용어
            syn_lower in ['child', 'children', 'pediatric', 'paediatric']):  # 너무 일반적인 용어
            continue
        filtered_synonyms.append(syn)
    
    # 최대 3개까지만 선택 (순서 유지)
    return filtered_synonyms[:3]

async def multi_strategy_query_expansion(original: str) -> List[str]:
    """
    하이브리드 전략으로 쿼리를 확장 (GPT 재작성 + 동의어 사전 활용)
    """
    strategies = []
    
    # 1. 원본 쿼리 (한글이면 영어로 번역)
    if not original.isascii():
        translated_original = await ko2en(original)
        strategies.append(translated_original)
        print(f"원본 번역: {translated_original}")
    else:
        strategies.append(original)
    
    try:
        # 2. GPT 재작성 (의미적 이해 기반 쿼리 최적화)
        gpt_rewritten = await gpt_rewriter.rewrite(original, "initial")
        strategies.append(gpt_rewritten)
        print(f"GPT 재작성: {gpt_rewritten}")
    except Exception as e:
        print(f"GPT 재작성 실패: {e}")
    
    # 3. 동의어 사전 기반 확장
    medical_expanded = await expand_medical_terms(original)
    strategies.append(medical_expanded)
    print(f"의료 용어 확장: {medical_expanded}")
    
    # 4. 고급 중복 제거 (의미적 유사성 고려)
    unique_strategies = []
    for strategy in strategies:
        if strategy and strategy.strip():
            is_duplicate = False
            for existing in unique_strategies:
                if (strategy.lower() == existing.lower() or 
                    strategy.lower() in existing.lower() or 
                    existing.lower() in strategy.lower()):
                    if len(strategy) > len(existing):
                        unique_strategies.remove(existing)
                        unique_strategies.append(strategy)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_strategies.append(strategy)
    
    print(f"최종 전략 수: {len(unique_strategies)}")
    return unique_strategies

# 중복 문서 제거 및 랭킹
def remove_duplicates_and_rank(docs: List) -> List:
    seen = set()
    unique_docs = []
    
    for doc in docs:
        content_hash = hash(doc.page_content[:200])
        if content_hash not in seen:
            seen.add(content_hash)
            unique_docs.append(doc)
    
    return unique_docs

# LLMEvaluator를 사용하여 실제 검색 품질 기반으로 최고의 쿼리를 선택
async def select_best_query_with_llm_evaluator(query_variants: List[str], original_question: str) -> tuple[str, Dict]:
    """
    LLMEvaluator를 사용하여 실제 검색 품질 기반으로 최고의 쿼리를 선택합니다.
    (MCP의 VectorDB_retriever 도구를 호출하도록 수정됨)
    """
    if not query_variants:
        return original_question, {}
    
    # MCP 도구 가져오기
    vectordb_tool = tools_dict.get("VectorDB_retriever")
    if not vectordb_tool:
        print("!!! CRITICAL ERROR: VectorDB_retriever tool not found in tools_dict.")
        return original_question, {"feedback": "VectorDB_retriever tool not found"}

    if len(query_variants) == 1:
        # --- 수정된 부분: MCP 도구 호출 ---
        response_tuple = await vectordb_tool.ainvoke({"query": query_variants[0]})
        docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
        docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
        # ---------------------------------
        evaluation = await llm_evaluator.evaluate_search_results(query_variants[0], docs_text)
        return query_variants[0], evaluation

    print(f"{len(query_variants)}개 쿼리 변형에 대해 검색 품질 평가 시작")
    
    best_query = query_variants[0]
    best_score = 0
    best_evaluation = {}
    evaluations = []
    
    for i, query in enumerate(query_variants):
        try:
            print(f"쿼리 {i+1}/{len(query_variants)}: {query}")
            
            # --- 수정된 부분: MCP 도구 호출 ---
            response_tuple = await vectordb_tool.ainvoke({"query": query})
            docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
            docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
            # ---------------------------------

            evaluation = await llm_evaluator.evaluate_search_results(query, docs_text)
            overall_score = evaluation.get("overall", 0)
            print(f"평가 점수: {overall_score:.3f}")
            print(f"세부점수 - 관련성:{evaluation.get('relevance', 0):.2f} "
                  f"일치도:{evaluation.get('faithfulness', 0):.2f} "
                  f"완성도:{evaluation.get('completeness', 0):.2f}")
            
            if overall_score > best_score:
                best_score = overall_score
                best_query = query
                best_evaluation = evaluation
                print(f"현재 최고 쿼리 업데이트!")
        except Exception as e:
            print(f"쿼리 평가 중 오류: {e}")
            default_eval = {
                "relevance": 0.3,
                "faithfulness": 0.3, 
                "completeness": 0.3,
                "overall": 0.3,
                "feedback": f"평가 오류: {str(e)[:50]}",
                "recommended_threshold": 0.6
            }
            evaluations.append((query, default_eval))
    
    print(f"최종 선택된 쿼리: {best_query}")
    print(f"최고 점수: {best_score:.3f}")
    print(f"선택 근거: {best_evaluation.get('feedback', '평가 완료')}")
    
    print("\n전체 쿼리 평가 결과:")
    for query, eval_result in evaluations:
        score = eval_result.get("overall", 0)
        print(f"  {score:.3f} | {query}")
    
    return best_query, best_evaluation


async def select_multiple_best_queries_with_evaluation(query_variants: List[str], original_question: str, top_k: int = 2) -> List[tuple[str, Dict]]:
    """
    LLMEvaluator 기반으로 상위 K개의 쿼리와 평가 결과를 반환합니다.
    (MCP의 VectorDB_retriever 도구를 호출하도록 수정됨)
    """
    vectordb_tool = tools_dict.get("VectorDB_retriever")
    if not vectordb_tool:
        print("!!! CRITICAL ERROR: VectorDB_retriever tool not found in tools_dict.")
        return [(original_question, {"feedback": "VectorDB_retriever tool not found"})]

    if not query_variants or len(query_variants) <= top_k:
        results = []
        for query in query_variants or [original_question]:
            try:
                # --- 수정된 부분: MCP 도구 호출 ---
                response_tuple = await vectordb_tool.ainvoke({"query": query})
                docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
                docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
                # ---------------------------------
                evaluation = await llm_evaluator.evaluate_search_results(query, docs_text)
                results.append((query, evaluation))
            except Exception as e:
                default_eval = {"overall": 0.3, "feedback": f"오류: {e}"}
                results.append((query, default_eval)) # default_evaluator -> default_eval 변수명 오류 수정
        return results
    
    print(f"상위 {top_k}개 쿼리 선택을 위한 전체 평가 시작")
    
    scored_queries = []
    for query in query_variants:
        try:
            # --- 수정된 부분: MCP 도구 호출 ---
            response_tuple = await vectordb_tool.ainvoke({"query": query})
            docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
            docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
            # ---------------------------------
            
            evaluation = await llm_evaluator.evaluate_search_results(query, docs_text)
            overall_score = evaluation.get("overall", 0)
            scored_queries.append((query, evaluation, overall_score))
        except Exception as e:
            default_eval = {
                "overall": 0.3, 
                "feedback": f"평가 오류: {str(e)[:50]}",
                "relevance": 0.3, "faithfulness": 0.3, "completeness": 0.3
            }
            scored_queries.append((query, default_eval, 0.3))
    
    scored_queries.sort(key=lambda x: x[2], reverse=True)
    selected = [(query, evaluation) for query, evaluation, score in scored_queries[:top_k]]
    
    print(f"상위 {top_k}개 쿼리 선택 완료:")
    for i, (query, evaluation) in enumerate(selected):
        print(f"  {i+1}. {evaluation.get('overall', 0):.3f} | {query}")
    
    return selected