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
    
    if not distractors:
        print("경고: 디스트랙터가 없습니다.")
        return []

    rankings = []
    k = len(distractors)
    print(f"디스트랙터 개수: {k}")

    # 외부에서 정의된 ranking_prompt 템플릿 사용
    for attempt in range(M):
        prompt = ranking_prompt.format(
            question=question,
            k=k, # distractor 개수 
            distractors=json.dumps(distractors, ensure_ascii=False)
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Output only the JSON array. Do not include any additional text or explanation."},
                    {"role": "user",   "content": prompt}
                ],
                temperature=0.2 # temperature 파라미터 조절 필요
            )
            raw = resp.choices[0].message.content
            print(f"랭킹 응답 {attempt+1}: {raw}")

            arr = json.loads(raw)
            if isinstance(arr, list) and all(isinstance(i, int) for i in arr):
                # 인덱스 범위 체크 및 교정
                valid_arr = [i for i in arr if 0 <= i < k]
                
                # 모든 인덱스가 유효하고 필요한 개수만큼 있으면 추가
                if len(valid_arr) == k and len(set(valid_arr)) == k:
                    rankings.append(valid_arr)
                    print(f"유효한 랭킹 추가: {valid_arr}")
                else:
                    print(f"유효하지 않은 랭킹 무시: {arr}")
        except Exception as e:
            print(f"랭킹 샘플링 오류: {e}")
            continue

    print(f"최종 랭킹 개수: {len(rankings)}")
    return rankings


def compute_borda_plausibility(rankings: List[List[int]], alpha: float = 1e-4) -> List[float]:
    # 순위 데이터 없으면 빈 리스트 반환
    if not rankings:
        print("경고: 랭킹 데이터가 없습니다.")
        return []

    k = len(rankings[0]) # 후보 수
    scores = [0] * k # plausibility 점수 저장할 리스트 초기화
    
    print(f"랭킹 데이터: {rankings}")
    print(f"점수 배열 크기: {k}")

    for i, ranking in enumerate(rankings):
        for position, idx in enumerate(ranking):
            # 인덱스 범위 검증
            if 0 <= idx < k:
                scores[idx] += (k - position)
            else:
                print(f"경고: 랭킹 {i}에서 인덱스 {idx}가 범위를 벗어남 (유효 범위: 0-{k-1})")
    
    print(f"계산된 점수: {scores}")

    # 정규화
    lo, hi = min(scores) if scores else (0, 0), max(scores) if scores else (0, 0)
    if hi == lo:
        return [1.0] * k

    return [(s - lo) / (hi - lo) for s in scores]