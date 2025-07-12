from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import pandas as pd, re, json, sys, subprocess
from typing import Annotated, List, TypedDict, Dict
from pinecone_server import *

retriever = create_retriever()

# --------
XLS_PATH = ("Final/Flow/Pediatric_Terminology.xls")

def build_term_dict_from_xls(xls_path: str):
    term_dict: Dict[str, List[str]] = {}
    sheets = pd.read_excel(xls_path, sheet_name=None, engine="xlrd")  # 엔진 고정
    for df in sheets.values():
        df = df.rename(columns=lambda c: c.strip())
        if {"Peds Preferred Term", "Peds Synonym"} <= set(df.columns):
            for pref, syns in zip(df["Peds Preferred Term"], df["Peds Synonym"]):
                if pd.isna(pref):
                    continue
                pref = str(pref).strip().lower()
                syn_list: List[str] = []
                if isinstance(syns, str):
                    syn_list = re.split(r"[|;,]", syns)
                elif not pd.isna(syns):
                    syn_list = [str(syns)]
                syn_list = [s.strip().lower() for s in syn_list if s.strip()]
                term_dict.setdefault(pref, []).extend(syn_list + [pref])
    return {k: sorted(set(v)) for k, v in term_dict.items()}

PEDIATRIC_TERMS = build_term_dict_from_xls(XLS_PATH)


# --------
async def ko2en(text: str, model_name: str = "gpt-4o-mini"):
    """
    한글 의료 질문을 영어로 자연스러운 전문 용어 중심 표현으로 번역
    """
    llm = ChatOpenAI(model_name=model_name, temperature=0.0, max_tokens=300)
    resp = await llm.ainvoke(f"Translate the following pediatric-anesthesia question to English "
                             f"(keep medical terms and abbreviations):\n{text}")
    return resp.content.strip()

# --------
class GPTQueryRewriter:
    """한국어,영어 입력 모두 처리 → 영어 OR 확장 벡터 검색 쿼리 반환"""
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.2):
        self.llm = ChatOpenAI(model_name=model_name,
                              temperature=temperature,
                              max_tokens=300)

    async def rewrite(self, question, mode = "initial"):
        # 입력이 한글이면 먼저 영어로 번역
        if not question.isascii():                
            question_en = await ko2en(question)
        else:
            question_en = question

        # 동의어 사전 기반 OR-확장 쿼리 생성
        prompt = (
            "You are a pediatric-anesthesia search expert.\n"
            "Rewrite the following question into ONE concise English search query "
            "optimised for a vector database.\n"
            f"Synonym dictionary: {json.dumps(PEDIATRIC_TERMS, ensure_ascii=False)}\n"
            "Guidelines:\n"
            "① Preserve key medical terms/abbreviations.\n"
            "② Expand synonyms with OR (e.g., neonatal OR newborn).\n"
            "③ Remove stop-words and unnecessary fillers.\n"
            "Return ONLY the search query."
        )
        if mode == "improvement":
            prompt += "\n(Previous results were unsatisfactory. Try a different angle.)"
        elif mode not in {"initial", "improvement"}:
            prompt += f"\n(User feedback: {mode} – please reflect it.)"

        prompt += f"\n\nUser question: {question_en}\n→"

        rewritten = (await self.llm.ainvoke(prompt)).content.strip()
        return rewritten
    
# --------
class LLMEvaluator:
    """Relevance(관련성), Faithfulness(사실 일치도), Completeness(질문 요소 충족도), 세 지표만 계산하는 LLM Judge"""
    def __init__(self, model_name="gpt-4o-mini", temperature=0.0):
        self.judge = ChatOpenAI(model_name=model_name,
                                temperature=temperature,
                                max_tokens=500)

    async def evaluate_search_results(self, query: str, docs: List[str]) -> Dict:
        if not docs:
            return self._default("no documents")

        previews = [d[:200].replace("\n", " ") + ("…" if len(d) > 200 else "")
                    for d in docs[:3]]

        prompt = f"""
            You are an independent evaluator for a PubMed-based RAG system.

            Task ◂ Evaluate how well the retrieved abstracts answer the user query.
            Metrics (0-1):
            1. relevance    – topical overlap between query and abstracts.
            2. faithfulness – factual alignment: does the evidence really support the answer?
            3. completeness – does the evidence cover all key aspects of the question?

            Return **one JSON**:

            {{
            "relevance": 0.0,
            "faithfulness": 0.0,
            "completeness": 0.0,
            "overall": 0.0,
            "feedback": ""
            }}

            overall = 0.4*relevance + 0.35*faithfulness + 0.25*completeness
            User query: \"{query}\"
            Evidence previews:
            - {previews[0]}
            - {previews[1] if len(previews)>1 else ''}
            - {previews[2] if len(previews)>2 else ''}
            """
        
        try:
            raw = (await self.judge.ainvoke(prompt)).content.strip()
            js = re.search(r"\{.*\}", raw, re.S).group()
            data = json.loads(js)
            # 필드 누락 시 기본값 보정
            for k in ("relevance", "faithfulness", "completeness"):
                data.setdefault(k, 0.3)
            # overall 미존재 시 가중합 계산
            if "overall" not in data:
                data["overall"] = round(
                    0.4*data["relevance"] +
                    0.35*data["faithfulness"] +
                    0.25*data["completeness"], 3)
            # 통과 기준(0.6)을 기본값으로 삽입
            data.setdefault("recommended_threshold", 0.6)
            return data
        except Exception as e:
            return self._default(f"parse error: {e}")

    # 모델이 어떤 지표를 빠뜨려도 0.3(보통 수준) 으로 채워 넣어 오류 방지
    def _default(self, reason: str):
        return dict(relevance=0.3, faithfulness=0.3, completeness=0.3,
                    overall=0.3, feedback=reason, recommended_threshold=0.6)

    # 종합 점수에 따른 재검색 여부 결정
    async def should_retry_search(self, ev: Dict, turn: int, max_turn: int):
        return ev.get("overall", 0) < ev.get("recommended_threshold", 0.6) \
               and turn < max_turn
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
    if not query_variants:
        return original_question, {}
    
    if len(query_variants) == 1:
        docs = retriever.invoke(query_variants[0])
        docs_text = [doc.page_content for doc in docs]
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
            docs = retriever.invoke(query)
            docs_text = [doc.page_content for doc in docs]
            evaluation = await llm_evaluator.evaluate_search_results(query, docs_text)
            evaluations.append((query, evaluation))
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
    LLMEvaluator 기반으로 상위 K개의 쿼리와 평가 결과를 반환
    """
    if not query_variants or len(query_variants) <= top_k:
        results = []
        for query in query_variants or [original_question]:
            try:
                docs = retriever.invoke(query)
                docs_text = [doc.page_content for doc in docs]
                evaluation = await llm_evaluator.evaluate_search_results(query, docs_text)
                results.append((query, evaluation))
            except Exception as e:
                default_eval = {"overall": 0.3, "feedback": f"오류: {e}"}
                results.append((query, default_eval))
        return results
    
    print(f"상위 {top_k}개 쿼리 선택을 위한 전체 평가 시작")
    
    scored_queries = []
    for query in query_variants:
        try:
            docs = retriever.invoke(query)
            docs_text = [doc.page_content for doc in docs]
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

print("헬퍼 함수들 준비 완료")