from typing import Annotated, List, TypedDict, Dict
from langchain_core.messages import BaseMessage

class ChatbotState(TypedDict):
    # --- 기존 mcp_langgraph_hw.ipynb의 State ---
    question: Annotated[str, "사용자 원본 질문 (mcp_langgraph_hw)"]
    flow_type: Annotated[str, "데이터베이스 조회 흐름 (mcp_langgraph_hw)"]
    patient_info: Annotated[str, "순차 처리를 위한 환자 정보 (mcp_langgraph_hw)"]
    decision_slack: Annotated[str, "슬랙 전송 여부 결정 (mcp_langgraph_hw)"]
    tools_query: Annotated[List[str], "각 DB에 전달할 쿼리 리스트 (mcp_langgraph_hw)"]
    final_answer: Annotated[str, "최종 답변 (mcp_langgraph_hw)"]
    slack_response: Annotated[str, "슬랙 전송 결과 (mcp_langgraph_hw)"]
    messages: List[BaseMessage]

    # --- VectorDB_Retrieval.ipynb에서 추가된 State ---
    current_query: Annotated[str, "현재 VectorDB 검색에 사용되는 쿼리 (VectorDB_Retrieval)"]
    query_variants: Annotated[List[str], "생성된 쿼리 변형 목록 (VectorDB_Retrieval)"]
    vector_documents: Annotated[str, "VectorDB 검색 결과 텍스트 (VectorDB_Retrieval)"]
    llm_evaluation: Annotated[Dict, "LLM 평가 결과 (VectorDB_Retrieval)"]
    loop_cnt: Annotated[int, "재시도 루프 카운트 (VectorDB_Retrieval)"]