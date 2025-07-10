import os
import json
import ast
import io

import pandas as pd
from tqdm import tqdm

# 1) 경로 설정
SRC_CSV   = "/home/work/BOAZ_ADV/학술지_train_data_result(재원).csv"
DST_JSONL = "/home/work/BOAZ_ADV/학술지_LLaMa3.2_Fine-tuning_Dataset.jsonl"

# 2) CSV 인코딩 자동 탐색
def read_csv_flexible(path, encodings=("utf-8-sig", "cp949", "euc-kr", "utf-8")):
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    # 전부 안될 시 -> 최종에는 바이너리로 읽어 오류 문자 대체
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode(encodings[-1], errors="replace")
    return pd.read_csv(io.StringIO(text))

# 3) 문자열로 된 리스트 파싱 (JSON 또는 Python literal)
def safe_list_load(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(s)
        except Exception:
            return []

# 4) LLaMA-3 Instruction 포맷 생성
def build_llama3_instruction(question: str, ctx_list, cot_and_answer: str):
    # 질문 앞에 'Q. ' 접두
    q_text = f"Q. {question.strip()}"
    # 문맥 Bullet들(앞에 • 붙여서 개별 문맥 표시)
    bullets = "\n".join(f"• {c.strip()}" for c in ctx_list if c)
    # 조립
    return (
        "<s>[INST] "
        f"{q_text}\n\nContext:\n{bullets}"
        " [/INST] "
        f"{cot_and_answer.strip()}"
        " </s>"
    )

def main():
    # 5) CSV 로드
    df = read_csv_flexible(SRC_CSV)

    # 6) 컬럼 정리: strip + BOM 제거
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]

    # 7) 한글→영문 매핑 (필요하다면)
    mapping = {
        "파일명":   "file",
        "질문":     "question",
        "관련 문서": "context",
        "답변":     "answer",
    }
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

    # 8) 필수 컬럼 체크
    for col in ("question", "context", "answer"):
        if col not in df.columns:
            raise ValueError(f"CSV에 '{col}' 컬럼이 없습니다.")

    # 9) JSONL으로 변환
    os.makedirs(os.path.dirname(DST_JSONL), exist_ok=True)
    with open(DST_JSONL, "w", encoding="utf-8") as fout:
        for _, row in tqdm(df.iterrows(), total=len(df)):
            q   = str(row["question"])
            ctx = safe_list_load(str(row["context"]))
            cot = str(row["answer"])  # 이미 CoT 형식으로 ##Reason…<ANSWER>:… 를 포함

            llama_text = build_llama3_instruction(q, ctx, cot)
            fout.write(json.dumps({"text": llama_text}, ensure_ascii=False) + "\n")

    print(f"Saved LLaMA-3 JSONL dataset to {DST_JSONL}")

if __name__ == "__main__":
    main()
