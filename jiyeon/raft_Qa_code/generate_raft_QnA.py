import os
import json
import ast
import random
import csv
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from Raft_prompt import distractor_prompt, ranking_prompt
from ranking_utils import parse_distractor_response, sample_rankings, compute_borda_plausibility

# 1) 환경 설정
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 본인 API KEY 설정

# 2) 사용자 설정
P_MIX_GOLDEN   = 0.4    # Noise sample에 Golden 컨텍스트를 섞을 확률 (실험시 조정)
K_DISTRACTORS  = 5      # 생성할 distractor 수 (실험시 조정)
M_RANK_SAMPLES = 10     # 순위 샘플링 횟수 (실험시 조정)
INPUT_CSV      = r"C:\Users\user\Desktop\BOAZ\23기 분석 ADV\소아마취 챗봇 프로젝트\RAFT_QA_Generation\학술지 QA 데이터 생성\학술지_all_final.csv"
OUTPUT_CSV     = r"C:\Users\user\Desktop\BOAZ\23기 분석 ADV\소아마취 챗봇 프로젝트\RAFT_QA_Generation\학술지 QA 데이터 생성\학술지_QA.csv"

def open_csv_with_fallback(path, encodings=("utf-8-sig", "cp949", "utf-8")):
    """
    여러 인코딩을 순차적으로 시도해 가장 먼저 성공하는 것으로 파일 열기
    """
    for enc in encodings:
        try:
            return open(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    # 모두 실패하면 마지막 인코딩으로 강제 오픈
    return open(path, encoding=encodings[-1])

def generate_reference_distractors(question: str, k: int) -> list:
    """
    질문만으로 사실관계가 틀린 distractor k개를 생성하여
    [{'distractor': 문장}, …] 형태로 반환
    """
    prompt = distractor_prompt.format(
        question=question,
        correct_refs="",
        k=k
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system", "content":"Output only the JSON list of objects. Do not include any additional text."},
            {"role":"user",   "content":prompt}
        ],
        temperature=0.2
    )

    raw = resp.choices[0].message.content
    texts = parse_distractor_response(raw)

    # 중복 제거 후 최대 k개까지 객체로 포맷팅
    seen, items = set(), []
    for t in texts:
        if t not in seen:
            seen.add(t)
            items.append({"distractor": t})
        if len(items) >= k:
            break

    return items

def main():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    rows = []

    # 3) 기존 골든 QA CSV 로드
    with open_csv_with_fallback(INPUT_CSV) as f:
        reader = csv.DictReader(f)

        for row in tqdm(reader):
            fname    = row["파일명"]
            question = row["질문"]
            raw_ctx  = row["관련 문서"].strip()

            # 4) golden context 파싱 (JSON 또는 파이썬 리터럴)
            try:
                golden = json.loads(raw_ctx)
            except json.JSONDecodeError:
                try:
                    golden = ast.literal_eval(raw_ctx)
                except Exception:
                    golden = []
            if not isinstance(golden, list):
                golden = [golden]

            answer = row["답변"]

            # 5) distractor 생성 → 순위 반복 샘플링 → plausibility 점수 계산
            items     = generate_reference_distractors(question, K_DISTRACTORS)
            distracts = [it["distractor"] for it in items]
            rankings  = sample_rankings(client, question, distracts, M=M_RANK_SAMPLES)
            scores    = compute_borda_plausibility(rankings)

            # distractor와 점수를 묶어서 내림차순 정렬
            validity = [
                {"distractor": d, "score": s}
                for d, s in sorted(zip(distracts, scores), key=lambda x: x[1], reverse=True)
            ]

            # 6) p에 따라 golden 섞기 or noise-only
            if random.random() < P_MIX_GOLDEN:
                mix_flag = "O"
                # golden + 상위 (K_DISTRACTORS-1)개 노이즈
                top_noise = [v["distractor"] for v in validity[:K_DISTRACTORS-1]]
                final_ctx = golden + top_noise
            else:
                mix_flag = "X"
                # 상위 K_DISTRACTORS개 노이즈
                final_ctx = [v["distractor"] for v in validity[:K_DISTRACTORS]]

            # 6.1) 매 행마다 관련 문서 순서 셔플
            random.shuffle(final_ctx)

            # 7) CSV 행 구성
            rows.append([
                fname,
                question,
                json.dumps(final_ctx, ensure_ascii=False),
                answer,
                mix_flag,
                json.dumps(validity, ensure_ascii=False)
            ])

    # 8) 결과 저장
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["파일명", "질문", "관련 문서", "답변", "Golden 포함", "Plausibility"])
        writer.writerows(rows)

    print(f"✅ 최종 학술지 QA Set saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
