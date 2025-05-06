import json                                         
import re
from typing import List # 인자로 들어가는 변수들 타입 힌트 제공
from Raft_prompt import ranking_prompt # 랭킹 프롬프트

# LLM 응답에서 distractor 문장만 추출하여 문자열 리스트로 반환
def parse_distractor_response(resp_text: str) -> List[str]:
    # 1) 응답 텍스트에서 가장 바깥의 JSON 배열을 찾아냄
    match = re.search(r"(\[.*\])", resp_text, flags=re.S)
    if not match:
        # 배열 형태가 없으면 예외를 발생
        raise ValueError("No JSON array found in the response.")
    json_text = match.group(1) # 찾은 배열 부분만 잘라냄

    try:
        # 2) 잘라낸 문자열을 JSON으로 파싱
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        # 파싱에 실패하면 구체적 오류 메시지를 담아 예외를 발생시킴킴
        raise ValueError(f"JSON parsing error: {e}")

    # 최종 문장들을 담을 리스트를 초기화
    distractors = []  

    # 3) 파싱된 각 요소를 순회하며 실제 문장만 추출
    for item in data:
        if isinstance(item, dict):
            # 3-a) dict 타입이면 distractor 키가 있는지 확인
            if 'distractor' in item:
                distractors.append(item['distractor'].strip())
            else:
                # 키가 없으면 첫 번째 키 값 사용
                key = next(iter(item.keys()))
                distractors.append(str(item[key]).strip())
        elif isinstance(item, str):
            # 3-b) 문자열 타입이면 그대로 strip 후 추가
            distractors.append(item.strip())
    return distractors # 최종 문자열 리스트를 반환

# 디스트랙터 후보를 plausibility 기준으로 M번 순위 샘플링
# gpt-4.1-mini 모델 사용
def sample_rankings(client,
                    question: str,
                    distractors: List[str],
                    M: int = 10,
                    model: str = "gpt-4.1-mini") -> List[List[int]]:

    rankings = []
    k = len(distractors)

    # 외부에서 정의된 ranking_prompt 템플릿 사용
    for _ in range(M):
        prompt = ranking_prompt.format(
            question=question,
            k=k, # distractor 개수 
            distractors=json.dumps(distractors, ensure_ascii=False)
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Output only the JSON array. Do not include any additional text or explanation."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.2 # temperature 파라미터 조절 필요
        )
        raw = resp.choices[0].message.content

        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) == k and all(isinstance(i, int) for i in arr):
                rankings.append(arr)
        except Exception:
            continue

    return rankings # 응답 원문


def compute_borda_plausibility(rankings: List[List[int]], alpha: float = 1e-4) -> List[float]:
    # 순위 데이터 없으면 빈 리스트 반환
    if not rankings:
        return []

    k = len(rankings[0]) # 후보 수
    scores = [0] * k # plausibility 점수 저장할 리스트 초기화


    for ranking in rankings:
        for position, idx in enumerate(ranking):
            # 수집된 순위 리스트를 Borda count 방식으로 집계하여 0~1 범위 plausibility 점수를 계산
            # position = 0 → 가장 그럴듯한 후보, position = k-1 → 가장 덜 그럴듯한 후보
            # k=3일 때:
            # position=0 인 후보(idx)에 3-0 = 3점
            # position=1 인 후보(idx)에 3-1 = 2점
            # position=2 인 후보(idx)에 3-2 = 1점
            scores[idx] += (k - position)

    # M 등에 따라서 절대 크기 달려져서 정규화 진행해서 0~1 사이의 SCORE로 변환
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * k

    return [(s - lo) / (hi - lo) for s in scores]