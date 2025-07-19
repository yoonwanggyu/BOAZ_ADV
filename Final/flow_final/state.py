from typing import Annotated, List, TypedDict, Dict
from langchain_core.messages import BaseMessage

# 챗봇 상태 정의
class ChatbotState(TypedDict):
    question: Annotated[str, "사용자 원본 질문"]
    flow_type: Annotated[str, "데이터베이스 조회 흐름"]
    patient_info: Annotated[str, "순차 처리를 위한 환자 정보"]
    decision_slack: Annotated[str, "슬랙 전송 여부 결정"]
    tools_query: Annotated[List[str], "각 DB에 전달할 쿼리 리스트"]
    final_answer: Annotated[str, "최종 답변"]
    slack_response: Annotated[str, "슬랙 전송 결과"]
    messages: List[BaseMessage]
    current_query: Annotated[str, "현재 VectorDB 검색에 사용되는 쿼리"]
    query_variants: Annotated[List[str], "생성된 쿼리 변형 목록"]
    vector_documents: Annotated[str, "VectorDB 검색 결과 텍스트"]
    llm_evaluation: Annotated[Dict, "LLM 평가 결과"]
    loop_cnt: Annotated[int, "재시도 루프 카운트"]
    optimization_completed: Annotated[bool, "쿼리 최적화 완료 여부"]
    should_retry_optimization: Annotated[bool, "최적화 재시도 필요 여부"]
