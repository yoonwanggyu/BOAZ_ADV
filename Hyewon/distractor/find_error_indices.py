import pandas as pd
import ast
import json
from Raft_prompt import distractor_prompt  # 기존 코드 유지 가능성 대비
from ranking_utils import parse_distractor_response  # 필요하면 사용

# 파일 경로
CSV_PATH = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\QAData\학술지_train_QA(혜원).csv"

# 데이터 불러오기
df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

error_indices = []

for idx, row in df.iterrows():
    try:
        question = row["질문"]
        context_raw = row["관련 문서"]
        answer = row["답변"]

        # context 파싱 (문자열 → 리스트)
        try:
            context_list = json.loads(context_raw)
        except json.JSONDecodeError:
            context_list = ast.literal_eval(context_raw)
        if not isinstance(context_list, list):
            context_list = [context_list]

        # 테스트: 질문 + context + 답변 프롬프트 생성
        prompt = f"<|user|> 질문: {question}\n\nContext:\n"
        for doc in context_list:
            prompt += f"- {doc}\n"
        prompt += "<|assistant|>"

        # answer 존재 여부도 체크
        if pd.isna(answer) or answer.strip() == "":
            raise ValueError("답변이 비어 있음")

    except Exception as e:
        print(f"❗ 에러 인덱스 {idx} (질문: {question}) → {e}")
        error_indices.append(idx)

print("✅ 에러 인덱스 목록:", error_indices)
