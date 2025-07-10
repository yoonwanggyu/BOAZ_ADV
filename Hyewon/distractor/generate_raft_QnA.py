# 이미 처리한 질문 skip (completed_keys 확인)
# distractor 부족하거나 ranking 길이 불일치시 skip
# 에러 발생해도 다음 질문으로 continue
# 50개마다 저장 (중간에 끊겨도 진행 가능)

# import os
# import json
# import ast
# import random
# import csv
# from tqdm import tqdm
# from dotenv import load_dotenv
# from openai import OpenAI
# from Raft_prompt import distractor_prompt, ranking_prompt
# from ranking_utils import parse_distractor_response, sample_rankings, compute_borda_plausibility

# # 1) 환경 설정
# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 본인 API KEY 설정

# # 2) 사용자 설정
# P_MIX_GOLDEN   = 0.6    # Noise sample에 Golden 컨텍스트를 섞을 확률 (실험시 조정)
# K_DISTRACTORS  = 5      # 생성할 distractor 수 (실험시 조정)
# M_RANK_SAMPLES = 10     # 순위 샘플링 횟수 (실험시 조정)
# INPUT_CSV      = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\QAData\학술지_train_missing.csv"
# OUTPUT_CSV     = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\QAData\missing_output.csv"

# def open_csv_with_fallback(path, encodings=("utf-8-sig", "cp949", "utf-8")):
#     """
#     여러 인코딩을 순차적으로 시도해 가장 먼저 성공하는 것으로 파일 열기
#     """
#     for enc in encodings:
#         try:
#             return open(path, encoding=enc)
#         except UnicodeDecodeError:
#             continue
#     # 모두 실패하면 마지막 인코딩으로 강제 오픈
#     return open(path, encoding=encodings[-1])

# def generate_reference_distractors(question: str, k: int) -> list:
#     """
#     질문만으로 사실관계가 틀린 distractor k개를 생성하여
#     [{'distractor': 문장}, …] 형태로 반환
#     """
#     prompt = distractor_prompt.format(
#         question=question,
#         correct_refs="",
#         k=k
#     )
#     resp = client.chat.completions.create(
#         model="gpt-4.1-mini",
#         messages=[
#             {"role":"system", "content":"Output only the JSON list of objects. Do not include any additional text."},
#             {"role":"user",   "content":prompt}
#         ],
#         temperature=0.2
#     )

#     raw = resp.choices[0].message.content
#     texts = parse_distractor_response(raw)

#     # 중복 제거 후 최대 k개까지 객체로 포맷팅
#     seen, items = set(), []
#     for t in texts:
#         if t not in seen:
#             seen.add(t)
#             items.append({"distractor": t})
#         if len(items) >= k:
#             break

#     return items

# def main():
#     os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
#     rows = []

#     # ✅ 이미 존재하는 CSV가 있으면 이어서 진행
#     existing_rows = []
#     if os.path.exists(OUTPUT_CSV):
#         with open(OUTPUT_CSV, 'r', encoding='utf-8-sig') as f:
#             reader = csv.reader(f)
#             next(reader)  # header skip
#             existing_rows = list(reader)
#             print(f"🔄 기존 CSV에서 {len(existing_rows)}개 행을 불러왔습니다.")

#     # 기존 행은 rows에 추가
#     rows.extend(existing_rows)

#     # 이미 완료한 질문 파악 (파일명 + 질문 기준)
#     completed_keys = set()
#     for r in existing_rows:
#         completed_keys.add((r[0], r[1]))  # (파일명, 질문)

#     # 3) 기존 골든 QA CSV 로드
#     with open_csv_with_fallback(INPUT_CSV) as f:
#         reader = csv.DictReader(f)

#         total_count = 0
#         for row in tqdm(reader):
#             fname    = row["파일명"]
#             question = row["질문"]
#             raw_ctx  = row["관련 문서"].strip()

#             total_count += 1

#             # 이미 처리한 질문이면 스킵
#             if (fname, question) in completed_keys:
#                 continue

#             # 4) golden context 파싱 (JSON 또는 파이썬 리터럴)
#             try:
#                 golden = json.loads(raw_ctx)
#             except json.JSONDecodeError:
#                 try:
#                     golden = ast.literal_eval(raw_ctx)
#                 except Exception:
#                     golden = []
#             if not isinstance(golden, list):
#                 golden = [golden]

#             answer = row["답변"]

#             try:
#                 # 5) distractor 생성
#                 items = generate_reference_distractors(question, K_DISTRACTORS)

#                 if items is None or len(items) < K_DISTRACTORS:
#                     print(f"❗ Distractor 부족 (파일명={fname}, 질문={question}) → 스킵")
#                     continue

#                 distracts = [it["distractor"] for it in items]
#                 rankings  = sample_rankings(client, question, distracts, M=M_RANK_SAMPLES)

#                 if any(len(r) != K_DISTRACTORS for r in rankings):
#                     print(f"❗ Ranking 개수 불일치 (파일명={fname}, 질문={question}) → 스킵")
#                     continue

#                 scores = compute_borda_plausibility(rankings)

#                 validity = [
#                     {"distractor": d, "score": s}
#                     for d, s in sorted(zip(distracts, scores), key=lambda x: x[1], reverse=True)
#                 ]

#                 if random.random() < P_MIX_GOLDEN:
#                     mix_flag = "O"
#                     top_noise = [v["distractor"] for v in validity[:K_DISTRACTORS-1]]
#                     final_ctx = golden + top_noise
#                 else:
#                     mix_flag = "X"
#                     final_ctx = [v["distractor"] for v in validity[:K_DISTRACTORS]]

#                 random.shuffle(final_ctx)

#                 # ✅ 새 행 추가
#                 rows.append([
#                     fname,
#                     question,
#                     json.dumps(final_ctx, ensure_ascii=False),
#                     answer,
#                     mix_flag,
#                     json.dumps(validity, ensure_ascii=False)
#                 ])

#                 # ✅ 50개마다 저장
#                 if len(rows) % 50 == 0 or total_count == len(rows):
#                     with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
#                         writer = csv.writer(f)
#                         writer.writerow(["파일명", "질문", "관련 문서", "답변", "Golden 포함", "Plausibility"])
#                         writer.writerows(rows)
#                     print(f"💾 {len(rows)}개 행 저장 완료")

#             except Exception as e:
#                 print(f"❗ 에러 발생 (파일명={fname}, 질문={question}): {e}")
#                 continue  # 다음 질문으로 넘어감

#     # 마지막으로 전체 저장
#     with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
#         writer = csv.writer(f)
#         writer.writerow(["파일명", "질문", "관련 문서", "답변", "Golden 포함", "Plausibility"])
#         writer.writerows(rows)

#     print(f"✅ 최종 학술지 QA Set saved to {OUTPUT_CSV}")

# if __name__ == "__main__":
#     main()









import os
import json
import ast
import random
import csv
import time
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from Raft_prompt import distractor_prompt, ranking_prompt
from ranking_utils import parse_distractor_response, sample_rankings, compute_borda_plausibility

# 1) 환경 설정
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 본인 API KEY 설정

# 2) 사용자 설정
P_MIX_GOLDEN   = 0.8  # Noise sample에 Golden 컨텍스트를 섞을 확률 (실험시 조정)
K_DISTRACTORS  = 10   # 생성할 distractor 수 (실험시 조정)
M_RANK_SAMPLES = 10   # 순위 샘플링 횟수 (실험시 조정)
INPUT_CSV      = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\QAData\학술지_train_data(csv).csv"
OUTPUT_CSV     = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\QAData\학술지_Raft_train_data_p_0.8.csv"

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

def generate_reference_distractors(question: str, golden_context: list, k: int) -> list:
    """
    질문과 golden 컨텍스트를 이용해 사실관계가 틀린 distractor k개를 생성하여
    [{'distractor': 문장}, …] 형태로 반환
    """
    # golden_context를 문자열로 변환
    correct_refs = "\n".join([f"- {ctx}" for ctx in golden_context]) if golden_context else ""
    
    # 고유한 디스트랙터를 저장할 집합과 결과 리스트
    seen = set()
    items = []
    
    # 최대 5회까지 시도하며 K개를 채울 때까지 반복
    max_attempts = 5
    for attempt in range(max_attempts):
        # 아직 필요한 디스트랙터 수 계산
        needed = k - len(items)
        if needed <= 0:
            break
            
        # 여유있게 더 많은 디스트랙터 요청 (중복 가능성 고려)
        request_k = needed * 2  # 필요한 개수의 2배 요청
        
        prompt = distractor_prompt.format(
            question=question,
            correct_refs=correct_refs,
            k=request_k
        )
        
        try:
            # 온도를 보수적으로 조정 (0.2에서 최대 0.3까지만)
            current_temp = min(0.2 + (attempt * 0.025), 0.3)
            
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role":"system", "content":"Output only the JSON list of objects. Do not include any additional text."},
                    {"role":"user",   "content":prompt}
                ],
                temperature=current_temp
            )

            raw = resp.choices[0].message.content
            texts = parse_distractor_response(raw)
            
            # 중복 제거하며 필요한 만큼 추가
            for t in texts:
                if t not in seen and t.strip():  # 빈 문자열이 아닌지 확인
                    seen.add(t)
                    items.append({"distractor": t})
                    if len(items) >= k:
                        break
                        
            print(f"시도 {attempt+1}: {len(texts)}개 생성, 현재 {len(items)}/{k}개 확보")
            
            # 이미 충분히 많은 디스트랙터를 생성했으면 중단
            if len(items) >= k:
                break
                
        except Exception as e:
            print(f"디스트랙터 생성 중 오류 (시도 {attempt+1}/{max_attempts}): {e}")
            # 오류 발생 시 잠시 대기 후 재시도
            time.sleep(2)
    
    # 모든 시도 후에도 K개를 채우지 못했다면 경고만 출력하고 가능한 만큼만 반환
    if len(items) < k:
        print(f"경고: 요청한 {k}개 중 {len(items)}개만 생성할 수 있었습니다.")
    
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
            items     = generate_reference_distractors(question, golden, K_DISTRACTORS)
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
                # golden 포함하되, 총 개수가 K_DISTRACTORS가 되도록 조정
                golden_count = len(golden)
                noise_count = max(0, K_DISTRACTORS - golden_count)  # 음수가 되지 않도록 방지
                top_noise = [v["distractor"] for v in validity[:noise_count]]
                final_ctx = golden + top_noise
            else:
                mix_flag = "X"
                # 가능한 모든 노이즈 사용 (K_DISTRACTORS개까지)
                final_ctx = [v["distractor"] for v in validity[:min(len(validity), K_DISTRACTORS)]]

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
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["파일명", "질문", "관련 문서", "답변", "Golden 포함", "Plausibility"])
        writer.writerows(rows)

    print(f"✅ 최종 학술지 QA Set saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()