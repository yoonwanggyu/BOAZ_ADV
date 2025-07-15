from typing import List, Dict
import json
import re
import pandas as pd
from langchain_openai import ChatOpenAI

def build_term_dict_from_xls(xls_path = '/Users/daeunbaek/nuebaek/BOAZ/BOAZ_ADV/Final/Flow/Pediatric_Terminology.xls'):

    term_dict: Dict[str, List[str]] = {}
    try:
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
    except FileNotFoundError:
        print(f"!!! 경고: 동의어 사전 파일({xls_path})을 찾을 수 없습니다. 동의어 확장이 비활성화됩니다.")
        return {}
    except ImportError:
        print("!!! 경고: 'xlrd' 라이브러리가 필요합니다. (pip install xlrd). 동의어 확장이 비활성화됩니다.")
        return {}

PEDIATRIC_TERMS = build_term_dict_from_xls()

# --- 쿼리 한글 -> 영어 번역 유틸 ---
async def ko2en(text: str, model_name: str = "gpt-4o-mini"):
    llm = ChatOpenAI(model_name=model_name, temperature=0.0)
    resp = await llm.ainvoke(f"Translate the following pediatric-anesthesia question to English (keep medical terms and abbreviations):\n{text}")
    return resp.content.strip()

# --- GPT 쿼리 재작성기 클래스 ---
class GPTQueryRewriter:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.2):
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, max_tokens=300)

    async def rewrite(self, question, mode="initial"):
        question_en = await ko2en(question) if not question.isascii() else question
        prompt = (
            "You are a pediatric-anesthesia search expert.\n"
            "Rewrite the following question into ONE concise English search query optimised for a vector database.\n"
            f"Synonym dictionary: {json.dumps(PEDIATRIC_TERMS, ensure_ascii=False)}\n"
            "Guidelines:\n"
            "① Preserve key medical terms/abbreviations.\n"
            "② Expand synonyms with OR (e.g., neonatal OR newborn).\n"
            "③ Remove stop-words and unnecessary fillers.\n"
            "Return ONLY the search query."
        )
        if mode == "improvement": prompt += "\n(Previous results were unsatisfactory. Try a different angle.)"
        prompt += f"\n\nUser question: {question_en}\n→"
        return (await self.llm.ainvoke(prompt)).content.strip()

# --- LLM 평가기 클래스 ---
class LLMEvaluator:
    def __init__(self, model_name="gpt-4o-mini", temperature=0.0):
        self.judge = ChatOpenAI(model_name=model_name, temperature=temperature, max_tokens=500)

    async def evaluate_search_results(self, query: str, docs: List[str]) -> Dict:
        if not docs: return self._default("no documents")
        previews = [d[:200].replace("\n", " ") + "…" for d in docs[:3]]
        prompt = f"""
            You are an independent evaluator for a PubMed-based RAG system.
            Task ◂ Evaluate how well the retrieved abstracts answer the user query.
            Metrics (0-1):
            1. relevance    – topical overlap between query and abstracts.
            2. faithfulness – factual alignment: does the evidence really support the answer?
            3. completeness – does the evidence cover all key aspects of the question?
            Return **one JSON**: {{\"relevance\": 0.0, \"faithfulness\": 0.0, \"completeness\": 0.0, \"overall\": 0.0, \"feedback\": \"\"}}
            overall = 0.4*relevance + 0.35*faithfulness + 0.25*completeness
            User query: \"{query}\"
            Evidence previews:
            - {previews[0]}
            - {previews[1] if len(previews)>1 else ''}
            - {previews[2] if len(previews)>2 else ''}
            """
        try:
            raw = (await self.judge.ainvoke(prompt)).content.strip()
            data = json.loads(re.search(r"\{.*\}", raw, re.S).group())
            for k in ("relevance", "faithfulness", "completeness"): data.setdefault(k, 0.3)
            if "overall" not in data:
                data["overall"] = round(0.4*data["relevance"] + 0.35*data["faithfulness"] + 0.25*data["completeness"], 3)
            data.setdefault("recommended_threshold", 0.6)
            return data
        except Exception as e: return self._default(f"parse error: {e}")

    def _default(self, reason: str):
        return dict(relevance=0.3, faithfulness=0.3, completeness=0.3, overall=0.3, feedback=reason, recommended_threshold=0.6)

    async def should_retry_search(self, ev: Dict, turn: int, max_turn: int):
        return ev.get("overall", 0) < ev.get("recommended_threshold", 0.6) and turn < max_turn