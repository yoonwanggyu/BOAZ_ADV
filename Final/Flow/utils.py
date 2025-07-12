


# --------
tool_router_schema = {
    "name": "route_question",
    "description": "사용자 질문의 의도를 파악하여 가장 적절한 데이터 조회 경로와 각 DB에 필요한 쿼리를 결정합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "flow_type": {
                "type": "string",
                "enum": ["sequential", "parallel", "neo4j_only", "vector_db_only"],
                "description": "질문에 가장 적합한 데이터 처리 흐름"
            },
            "neo4j_query": {
                "type": "string",
                "description": """Neo4j 환자 DB에서 구조화된 환자별 임상 정보를 조회하기 위한 자연어 쿼리입니다.
                사용자 질문에 '환자', '환자기록', '수술이력', '진단명' 등 명확한 환자 데이터 관련 용어가 포함될 때 사용하세요.
                flow_type이 'neo4j_only', 'parallel', 'sequential'일 경우에만 생성됩니다."""
            },
            "vector_db_query": {
                "type": "string",
                "description": """Vector DB에서 일반적인 의학/임상 지식을 검색하기 위한 자연어 쿼리입니다.
                '전신마취', '케타민', '수술 부작용' 등 특정 환자와 무관한 의학 개념, 절차, 가이드라인에 대한 질문일 때 사용하세요.
                flow_type이 'vector_db_only' 또는 'parallel'일 경우에만 생성됩니다. 'sequential' 흐름에서는 이 필드를 사용하지 않습니다."""
            }
        },
        "required": ["flow_type"]
    }
}

# --------
def determine_slack_usage(query: str) -> str:
    SEND_COMMANDS = ["보내줘", "전송해줘", "전달해줘"]
    return 'Yes' if any(cmd in query for cmd in SEND_COMMANDS) or "에게" in query else 'No'


