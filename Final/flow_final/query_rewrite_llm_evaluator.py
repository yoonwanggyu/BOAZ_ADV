from typing import Annotated, List, TypedDict, Dict, Optional
import json
import re
import pandas as pd
from langchain_openai import ChatOpenAI
from state import ChatbotState

xls_path = "/root/Pediatric_Terminology.xls"

def build_term_dict_from_xls(xls_path):
    term_dict = {}
    sheets = pd.read_excel(xls_path, sheet_name=None, engine="xlrd")
    for df in sheets.values():
        df = df.rename(columns=lambda c: c.strip())
        if {"Peds Preferred Term", "Peds Synonym"} <= set(df.columns):
            for pref, syns in zip(df["Peds Preferred Term"], df["Peds Synonym"]):
                if pd.isna(pref): continue
                pref = str(pref).strip().lower()
                syn_list = [s.strip().lower() for s in re.split(r"[|;,]", str(syns)) if s and s.strip()] if isinstance(syns, str) else []
                term_dict.setdefault(pref, []).extend(syn_list + [pref])
    return {k: sorted(set(v)) for k, v in term_dict.items()}

pediatric_terms = build_term_dict_from_xls(xls_path)

# 쿼리 한글 -> 영어 번역 유틸
async def ko2en(text, model = "gpt-4o-mini"):
    llm = ChatOpenAI(model = model, temperature=0.0)
    resp = await llm.ainvoke(f"""
        You are a specialized pediatric anesthesia medical translator.

        # Task: Translate Korean medical questions to English
        - Preserve all medical terms in standard English form
        - Do not change dosages, measurements, or abbreviations
        - Maintain clinical accuracy and context
        - Use terminology from medical literature and guidelines

        # Translation Guidelines:
        - 소아 → pediatric patient / child
        - 마취 → anesthesia / anesthetic
        - 수술 → surgery / surgical procedure
        - 약물 → medication / drug
        - 부작용 → side effect / adverse effect
        - Keep drug names in original form (e.g., Ketamine, Propofol)
        - Preserve medical abbreviations (e.g., mg/kg, IV, IM)

        # Korean Question:
        {text}

        # English Translation:
        """)
    return resp.content.strip()

# 쿼리 최적화 전략
# 1차 - 원본 쿼리 사용(번역만), 2차 - 원본 기반 가벼운 최적화 (용어 표준화, 동의어 추가), 3차 - 원본 의도 보존하면서 검색 전략 변경 (확장/축소/재구성)
class AdaptiveQueryOptimizer:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.1):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.attempt_count = 0
        self.original_question: str = ""
        self.original_question_en: str = ""
        self.previous_queries: List[str] = []
    
    async def get_search_query(self, question: str, evaluation_result: Optional[Dict] = None, state: Optional[ChatbotState] = None) -> str:
        if self.attempt_count == 0:
            self.original_question = question
            self.original_question_en = await ko2en(question) if not question.isascii() else question

        self.attempt_count += 1
        if state is not None:
            state["loop_cnt"] = self.attempt_count

        if self.attempt_count == 1:
            query = self.original_question_en
        elif self.attempt_count == 2:
            query = await self._light_optimization(evaluation_result)
        else:
            query = await self._strategic_reformulation(evaluation_result)

        self.previous_queries.append(query)
        return query
    
    # 2차 방식 구현
    async def _light_optimization(self, eval_result):
        prompt = f"""
        You are a pediatric anesthesia medical search expert.
        Optimize queries to improve vector DB search performance while completely preserving the original question's intent.
        
        Pediatric anesthesia medical synonym dictionary: {json.dumps(pediatric_terms, ensure_ascii=False)}
        
        Optimization Guidelines:
        1. Never change the core intent and context of the original question
        2. Standardize medical terminology (e.g., 소아 → pediatric)
        3. Naturally integrate synonyms (no OR operators)
        4. Replace with clearer and more specific medical terms
        5. Keep drug names, numbers, and abbreviations as they are
        
        Good Examples:
        - "신생아 심장수술" → "neonatal cardiac surgery procedures"
        - "소아 진통제" → "pediatric analgesic medications"
        
        Bad Examples:
        - "neonatal OR newborn cardiac surgery" (using OR operators)
        - "child infant baby surgery" (listing synonyms)
        
        Original Question: {self.original_question}
        English Translation: {self.original_question_en}
        Previous Search Issues: {eval_result.get('feedback', 'Low relevance') if eval_result else 'Low relevance'}
        
        Optimized Search Query:
        """
        return (await self.llm.ainvoke(prompt)).content.strip()
    
    # 3차 방식 구현
    async def _strategic_reformulation(self, eval_result):
        prompt = f"""
        You are a pediatric anesthesia medical search expert.
        Change only the search expression while completely preserving the original question's intent.
        
        Strict Safety Constraints:
        1. Never add medical information not present in the original
        2. Do not create new symptoms, procedures, drugs, or complications
        3. Do not make inferences or assumptions
        4. Use only information present in the original
        
        Safe Strategy Changes:
        - Change word order (dosage pediatric → pediatric dosage)
        - Use synonyms (side effects → adverse effects)
        - Change expression style (sentence → keywords)
        - Remove unnecessary words
        
        Absolutely Prohibited (false information generation):
        - Original: "프로포폴 부작용" → "프로포폴 부작용 심혈관계" (adding cardiovascular prohibited)
        - Original: "진통제 용량" → "진통제 용량 수술중" (adding intraoperative prohibited)
        - Original: "신생아 마취" → "신생아 마취 기관삽관" (adding intubation prohibited)
        
        Safe Examples:
        - Original: "프로포폴 부작용" → "propofol adverse reactions"
        - Original: "신생아 진통제 용량" → "analgesic dosing neonates"
        - Original: "소아 마취 관리" → "pediatric anesthesia management"
        
        Original Question: {self.original_question}
        English Translation: {self.original_question_en}
        Previous Search Issues: {eval_result.get('feedback', 'Previous attempts failed') if eval_result else 'Previous attempts failed'}
        
        Optimized Search Query:
        """
        return (await self.llm.ainvoke(prompt)).content.strip()
    
    def reset(self):
        """새 질문 시작 시 리셋"""
        self.attempt_count = 0
        self.original_question = None
        self.original_question_en = None
        self.previous_queries = []

# LLM 기반 쿼리 및 Retrieval 평가기
class LLMEvaluator:
    def __init__(self, model_name="gpt-4o-mini", temperature=0.0):
        self.judge = ChatOpenAI(model = model_name , temperature=temperature, max_completion_tokens=1024)

    # 검색 결과 평가
    async def evaluate_search_results(self, query, docs):
        if not docs: return None
        previews = [d[:200].replace("\n", " ") + "…" for d in docs[:3]]
        prompt = f"""
            You are an independent evaluator for a PubMed-based RAG system.
            Task ◂ Evaluate how well the retrieved abstracts answer the user's question.
            Evaluation metrics (0-1):
            1. relevance – Degree of topical overlap between question and abstracts
            2. faithfulness – Factual consistency: Does the evidence really support the answer?
            3. completeness – Does the evidence cover all key aspects of the question?
            **Return only one JSON**: {{\"relevance\": 0.0, \"faithfulness\": 0.0, \"completeness\": 0.0, \"overall\": 0.0, \"feedback\": \"\"}}
            overall = 0.3 * relevance + 0.5 * faithfulness + 0.2 * completeness
            User Question: \"{query}\"
            Evidence Preview:
            - {previews[0]}
            - {previews[1] if len(previews)>1 else ''}
            - {previews[2] if len(previews)>2 else ''}
            """
        try:
            raw = str((await self.judge.ainvoke(prompt)).content).strip()
            print(f"LLM 평가 응답: {raw[:500]}...")  # 디버깅용 출력
            
            json_match = re.search(r"\{.*\}", raw, re.S)
            if json_match:
                data = json.loads(json_match.group())
                print(f"파싱된 평가 데이터: {data}")  # 디버깅용 출력
                
                # 필수 키 누락 체크
                required_keys = ("relevance", "faithfulness", "completeness")
                missing_keys = [k for k in required_keys if k not in data]
                if missing_keys:
                    raise ValueError(f"Missing required keys: {missing_keys}")
            else:
                print(f"JSON 파싱 실패 - 원본 응답: {raw}")
                raise ValueError("JSON parsing failed")
            # 소아마취 도메인: faithfulness 우선 (의료 안전성)
            if "overall" not in data:
                data["overall"] = round(0.3*data["relevance"] + 0.5*data["faithfulness"] + 0.2*data["completeness"], 3)
            
            # 의료 도메인 특화 임계값 (연구 기반)
            data["recommended_threshold"] = 0.7  # 높은 신뢰성 요구
            print(f"최종 평가 결과: overall={data['overall']}")  # 디버깅용 출력
            return data
            
        except Exception as e: 
            # 평가 실패 시 None 반환하여 상위에서 처리
            print(f"평가 실패: {e}")
            return None

    # 평가 실패 시 재시도
    async def should_retry_search(self, ev, turn, max_turn):
        return ev.get("overall", 0) < ev.get("recommended_threshold", 0.7) and turn < max_turn

    # 실제 검색 품질 기반으로 최고의 쿼리를 선택
    async def select_best_query(self, query_variants, vectordb_tool, original_question=""):
        if not query_variants:
            return original_question, {}
        
        if not vectordb_tool:
            print("CRITICAL ERROR: VectorDB_retriever tool not found.")
            return original_question, {"feedback": "VectorDB_retriever tool not found"}

        if len(query_variants) == 1:
            response_tuple = await vectordb_tool.ainvoke({"query": query_variants[0]})
            docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
            docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
            evaluation = await self.evaluate_search_results(query_variants[0], docs_text)
            return query_variants[0], evaluation or {}
        print(f"{len(query_variants)}개 쿼리 변형에 대해 검색 품질 평가 시작")
        
        best_query = query_variants[0]
        best_score = 0
        best_evaluation = {}
        
        for i, query in enumerate(query_variants):
            try:
                print(f"쿼리 {i+1}/{len(query_variants)}: {query}")
                
                response_tuple = await vectordb_tool.ainvoke({"query": query})
                docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
                docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]

                evaluation = await self.evaluate_search_results(query, docs_text)
                if evaluation is None:
                    continue
                    
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
        
        print(f"최종 선택된 쿼리: {best_query}")
        print(f"최고 점수: {best_score:.3f}")
        print(f"선택 근거: {best_evaluation.get('feedback', '평가 완료')}")
        
        return best_query, best_evaluation

    # 상위 K개의 쿼리와 평가 결과를 반환
    async def select_multiple_queries(self, query_variants, vectordb_tool, original_question="", top_k=2):
        if not vectordb_tool:
            print("CRITICAL ERROR: VectorDB_retriever tool not found.")
            return [(original_question, {"feedback": "VectorDB_retriever tool not found"})]
        if not query_variants or len(query_variants) <= top_k:
            results = []
            for query in query_variants or [original_question]:
                try:
                    response_tuple = await vectordb_tool.ainvoke({"query": query})
                    docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
                    docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
                    evaluation = await self.evaluate_search_results(query, docs_text)
                    results.append((query, evaluation or {}))
                except Exception as e:
                    print(f"쿼리 '{query}' 평가 실패: {e}")
                    # 평가 실패한 쿼리는 제외
            return results
        
        print(f"상위 {top_k}개 쿼리 선택을 위한 전체 평가 시작")
        
        scored_queries = []
        for query in query_variants:
            try:
                response_tuple = await vectordb_tool.ainvoke({"query": query})
                docs_text_str = response_tuple[0] if isinstance(response_tuple, tuple) else str(response_tuple)
                docs_text = [doc.strip() for doc in docs_text_str.split("\n\n") if doc.strip()]
                
                evaluation = await self.evaluate_search_results(query, docs_text)
                overall_score = evaluation.get("overall", 0) if evaluation else 0
                scored_queries.append((query, evaluation or {}, overall_score))
            except Exception as e:
                print(f"쿼리 '{query}' 평가 실패: {e}")
                # 평가 실패한 쿼리는 제외 (0.3 같은 임의 점수 부여하지 않음)
        
        scored_queries.sort(key=lambda x: x[2], reverse=True)
        selected = [(query, evaluation) for query, evaluation, score in scored_queries[:top_k]]
        
        print(f"상위 {top_k}개 쿼리 선택 완료:")
        for i, (query, evaluation) in enumerate(selected):
            print(f"  {i+1}. {evaluation.get('overall', 0):.3f} | {query}")
        
        return selected