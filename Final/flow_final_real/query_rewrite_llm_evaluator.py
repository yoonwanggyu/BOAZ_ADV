from typing import Annotated, List, TypedDict, Dict, Optional
from langchain_openai import ChatOpenAI
from state import ChatbotState
import json
import re
import pandas as pd

# NIH(National Institutes of Health) 에서 제공하는 소아마취 동의어 목록을 파싱하여 사전 생성
xls_path = "/mnt/c/Users/USER/BOAZ_ADV/jiyeon/final/flow_final/Pediatric_Terminology.xls"

# NIH 동의어 목록을 파싱하여 사전 생성
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

# 소아마취 동의어 사전 생성
pediatric_terms = build_term_dict_from_xls(xls_path)

# 쿼리 한글 -> 영어 번역
async def ko2en(text, model = "gpt-4o-mini"):
    llm = ChatOpenAI(model = model, temperature=0.1) # temperature=0.1로 하여 너무 경직된 번역 대신 문장 구조의 자연스러움 보장
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
# 1차 - 원본 쿼리 사용(한글 일시 번역만), 2차 - 원본 기반 가벼운 최적화(용어 표준화, 동의어 추가), 3차 - 원본 의도 보존하면서 검색 전략 변경(확장/축소/재구성)
class AdaptiveQueryOptimizer:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.1, max_attempts: int = 3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.attempt_count = 0
        self.max_attempts = max_attempts
        self.satisfaction_threshold = 0.7  # 만족 임계값
        self.original_question: str = ""
        self.original_question_en: str = ""
        
        # 이전 시도 추적을 위한 변수들
        self.previous_queries: List[str] = []
        self.query_evaluations: List[Dict] = []
        
        # 최고 성능 추적
        self.best_score = 0.0
        self.best_query_info = {
            "query": "",
            "evaluation": {},
            "attempt": 0,
            "documents": ""  # 최고 성능 쿼리의 검색 결과 추가
        }
        
        # 기준 만족 추적
        self.is_satisfied = False
    
    async def get_search_query(self, question: str, evaluation_result: Optional[Dict] = None, state: Optional[ChatbotState] = None) -> str:
        # 첫 번째 시도인 경우 초기화
        if self.attempt_count == 0:
            self.original_question = question
            self.original_question_en = await ko2en(question) if not question.isascii() else question
            self.is_satisfied = False

        # 이전 평가 결과가 만족스러운 경우 조기 종료
        if evaluation_result and self.attempt_count > 0:
            overall_score = evaluation_result.get("overall", 0)
            if overall_score >= self.satisfaction_threshold:
                print(f"평가 조건 충족 (점수: {overall_score:.3f} >= {self.satisfaction_threshold})")
                self.is_satisfied = True
                # 이전 쿼리 반환 (만족스러운 결과를 얻은 쿼리)
                return self.previous_queries[-1] if self.previous_queries else self.original_question_en

        # 최대 시도 횟수 도달 확인
        if self.attempt_count >= self.max_attempts:
            print(f"최대 시도 횟수 도달 ({self.max_attempts}회)")
            return self.previous_queries[-1] if self.previous_queries else self.original_question_en

        self.attempt_count += 1
        if state is not None:
            state["loop_cnt"] = self.attempt_count

        print(f"쿼리 최적화 시도 {self.attempt_count}/{self.max_attempts}")

        if self.attempt_count == 1:
            query = self.original_question_en
            print("1차 전략: 한글→영어 직접 번역 (의학 용어 기본 매핑)")
            print(f"실행: 소아마취 전문 번역가 프롬프트 적용")
        elif self.attempt_count == 2:
            query = await self._light_optimization(evaluation_result)
            print("2차 전략: 의학 용어 표준화 + NIH 동의어 사전 활용")
            print(f"실행: 소아마취 동의어 통합, 의학 표준 용어로 치환")
        else:
            query = await self._strategic_reformulation(evaluation_result)
            print("3차 전략: 검색 표현 방식 재구성 (키워드 순서/구조 변경)")
            print(f"실행: 문장→키워드, 동의어 활용, 단어 순서 최적화")

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
    
    # 새 질문 시작 시 리셋
    def reset(self):
        self.attempt_count = 0
        self.original_question = None
        self.original_question_en = None
        self.previous_queries = []
        self.query_evaluations = []
        self.is_satisfied = False
        self.best_score = 0.0
        self.best_query_info = {
            "query": "",
            "evaluation": {},
            "attempt": 0,
            "documents": ""
        }
    
    # 현재 최적화 상태 반환
    def get_optimization_status(self) -> Dict:
        return {
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "is_satisfied": self.is_satisfied,
            "satisfaction_threshold": self.satisfaction_threshold,
            "best_score": self.best_score,
            "best_attempt": self.best_query_info["attempt"]
        }
    
    # 쿼리 평가 결과 업데이트 및 최고 성능 추적
    def update_evaluation(self, query: str, evaluation: Dict, documents: str = ""):
        # 현재 시도 정보 저장
        current_evaluation = {
            "query": query,
            "evaluation": evaluation,
            "attempt": self.attempt_count,
            "documents": documents
        }
        self.query_evaluations.append(current_evaluation)
        
        # 만족도 체크
        overall_score = evaluation.get("overall", 0)
        if overall_score >= self.satisfaction_threshold:
            self.is_satisfied = True
            print(f"목표 점수 달성: {overall_score:.3f} >= {self.satisfaction_threshold}")
        
        # 최고 성능 쿼리 업데이트
        current_score = evaluation.get("overall", 0)
        best_score = self.best_score
        
        if current_score > best_score:
            self.best_score = current_score
            self.best_query_info = current_evaluation
            print(f"신규 최고 성능: {current_score:.3f} (시도 {self.attempt_count})")
            print(f"개선: 이전 최고 {best_score:.3f} → 현재 {current_score:.3f} (+{current_score-best_score:.3f})")
            print(f"상태: 현재 쿼리를 최적 후보로 업데이트")

    # 최종적으로 사용할 쿼리, 평가 결과, 검색 결과 반환
    def get_final_query_and_evaluation(self) -> tuple[str, Dict, str]:
        # 만족스러운 결과가 있으면 해당 쿼리 사용
        if self.is_satisfied and self.query_evaluations:
            satisfied_info = self.query_evaluations[-1]  # 마지막 만족스러운 결과
            satisfied_query = satisfied_info["query"]
            satisfied_eval = satisfied_info["evaluation"]
            satisfied_docs = satisfied_info["documents"]
            print(f"목표 달성 쿼리 최종 선택")
            print(f"점수: {satisfied_eval.get('overall', 0):.3f} >= 임계값 {self.satisfaction_threshold}")
            print(f"시도: {satisfied_info['attempt']}차에서 조기 성공")
            print(f"전략: 추가 최적화 생략, 현재 쿼리로 확정")
            return satisfied_query, satisfied_eval, satisfied_docs
        
        # 그렇지 않으면 최고 성능 쿼리 사용
        best_query = self.best_query_info["query"] if self.best_query_info["query"] else (self.original_question_en if self.original_question_en else "")
        best_eval = self.best_query_info["evaluation"]
        best_docs = self.best_query_info["documents"]
        best_attempt = self.best_query_info["attempt"]
        
        print(f"최고 성능 쿼리 최종 선택")
        print(f"최고점수: {best_eval.get('overall', 0):.3f} (시도 {best_attempt})")
        print(f"전략: 목표 미달성, 전체 시도 중 최우수 성능 쿼리 채택")
        print(f"결과: {len(self.query_evaluations)}회 시도 완료 후 베스트 선택")
        
        # 모든 시도의 점수 요약 출력
        if len(self.query_evaluations) > 1:
            print("전체 시도 성능 비교:")
            for i, eval_info in enumerate(self.query_evaluations, 1):
                score = eval_info["evaluation"].get("overall", 0)
                is_best = "최고" if eval_info["attempt"] == best_attempt else "  "
                strategy = ["원본번역", "용어최적화", "구조재구성"][i-1] if i <= 3 else f"{i}차"
                print(f"   {is_best} {i}차 ({strategy}): {score:.3f}")
        
        return best_query, best_eval, best_docs

# LLM 기반 쿼리 및 Retrieval 평가
class LLMEvaluator:
    def __init__(self, model_name="gpt-4o-mini", temperature=0.1):
        self.judge = ChatOpenAI(model = model_name , temperature = temperature, max_completion_tokens = 1024) 

    # 검색 결과 평가
    async def evaluate_search_results(self, query, docs):
        if not docs: return None
        previews = [d[:200].replace("\n", " ") + "…" for d in docs[:3]]
        prompt = f"""
            You are a precise evaluator for a medical information retrieval system.
            Task: Evaluate how well the retrieved medical literature address the user's medical question.
            
            Evaluation metrics (0-1) with detailed scoring:
            
            1. relevance – Degree of topical overlap between question and medical literature
               - 0.9-1.0: Direct, complete topical match
               - 0.7-0.8: Strong relevance, most concepts match
               - 0.5-0.6: Moderate relevance, some key concepts match
               - 0.3-0.4: Weak relevance, minimal concept overlap
               - 0.1-0.2: Very weak relevance, distant connection
               - 0.0: No topical relevance
            
            2. faithfulness – Factual consistency: Does the evidence really support the answer?
               - 0.9-1.0: Completely accurate, well-supported facts
               - 0.7-0.8: Mostly accurate, reliable information
               - 0.5-0.6: Generally accurate with minor issues
               - 0.3-0.4: Some inaccuracies but mostly factual
               - 0.1-0.2: Significant inaccuracies, questionable facts
               - 0.0: Clearly incorrect or misleading information
            
            3. completeness – Does the evidence cover all key aspects of the question?
               - 0.9-1.0: Comprehensive coverage of all aspects
               - 0.7-0.8: Covers most important aspects
               - 0.5-0.6: Covers some key aspects, partial information
               - 0.3-0.4: Limited coverage, few aspects addressed
               - 0.1-0.2: Minimal coverage, very incomplete
               - 0.0: No meaningful coverage of the question
            
            Return JSON: {{"relevance": 0.0, "faithfulness": 0.0, "completeness": 0.0, "overall": 0.0, "feedback": ""}}
            overall = 0.2 * relevance + 0.5 * faithfulness + 0.3 * completeness
            
            User Question: "{query}"
            Medical Literature Preview:
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
                    raise ValueError(f"필요한 키 누락: {missing_keys}")
            else:
                print(f"JSON 파싱 실패 - 원본 응답: {raw}")
                raise ValueError("JSON 파싱 실패")

            if "overall" not in data:
                data["overall"] = round(0.2*data["relevance"] + 0.5*data["faithfulness"] + 0.3*data["completeness"], 3)
            
            # 의료 도메인 특화 임계값
            data["recommended_threshold"] = 0.7  # 높은 신뢰성 요구
            print(f"최종 평가 결과: overall={data['overall']}")  # 디버깅용 출력
            return data

        # 평가 실패 시 None 반환하여 상위에서 처리    
        except Exception as e: 
            
            print(f"평가 실패: {e}")
            return None

    # 평가 결과에 따른 재시도 필요성 판단
    async def should_retry_search(self, evaluation_result: Dict, current_attempt: int, max_attempts: int = 3) -> bool:
        """
        평가 결과를 바탕으로 재시도가 필요한지 판단
        Args:
            evaluation_result: LLM 평가 결과
            current_attempt: 현재 시도 횟수
            max_attempts: 최대 시도 횟수
        Returns:
            bool: 재시도 필요 여부
        """
        if not evaluation_result:
            print(" 평가 시스템 오류 감지")
            print(f"상황: LLM 평가 결과 누락 또는 파싱 실패")
            print(f"대응: 기본 재시도 정책 적용 ({current_attempt}/{max_attempts})")
            return current_attempt < max_attempts
        
        overall_score = evaluation_result.get("overall", 0)
        threshold = evaluation_result.get("recommended_threshold", 0.7)
        
        should_retry = overall_score < threshold and current_attempt < max_attempts
        
        if should_retry:
            print(f"추가 최적화 실행")
            print(f"현재점수: {overall_score:.3f} < 목표 {threshold}")
            print(f"진행상황: {current_attempt}/{max_attempts}회 시도")
            print(f"전략: 다음 단계 최적화 기법 적용 예정")
        else:
            reason = "목표 점수 달성" if overall_score >= threshold else "최대 시도 완료"
            print(f"최적화 과정 종료")
            print(f"종료사유: {reason}")
            print(f"최종점수: {overall_score:.3f}")
            print(f"상태: 최고 성능 쿼리 선택 단계로 진행")
        
        return should_retry

