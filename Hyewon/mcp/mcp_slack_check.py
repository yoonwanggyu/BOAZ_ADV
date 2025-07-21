# 1) 규칙 기반 Slack 감지에 사용할 키워드 리스트
SEND_COMMANDS = ["보내줘", "전송해줘"]

def determine_slack_usage(query: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Strict rule-based Slack detection:
    패턴: "(수신자)에게 (메시지 내용) 보내줘/전송해줘"
    반환값: (use_slack, recipient, message)
    """
    pattern = re.compile(
        r"(.+?)에게\s*(.+?)\s*(?:Slack으로\s*)?(보내줘|전송해줘)"
    )
    m = pattern.search(query)
    if m:
        return True, m.group(1).strip(), m.group(2).strip()
    return False, None, None

# 2) LLM Function-Calling을 위한 함수 정의
slack_sender_function = {
    "name": "slack_sender",
    "description": "Send the final answer to a specific person on Slack when requested by the user.",
    "parameters": {
        "type": "object",
        "properties": {
            "question":        {"type": "string", "description": "Cleaned medical question without Slack instructions."},
            "slack_recipient": {"type": "string", "description": "Slack recipient name to receive the answer."}
        },
        "required": ["question", "slack_recipient"]
    }
}

# 3) Fallback으로 LLM을 호출할 때 쓸 시스템 프롬프트
DECISION_SYSTEM_PROMPT = """
You are a decision-making assistant for Slack dispatch.
If the user asks to send a question to a specific person via Slack (e.g., '~에게 보내줘'),
return a function call to slack_sender with arguments {question, slack_recipient}.
Otherwise, return a JSON object: {"question": ..., "slack_recipient": null, "tools": []}.
Do not output any explanatory text.
"""
# ─────────────────────────────────────────────────────────────────────

# ── decision_tools 노드 전체 구현 ────────────────────────────────────
async def decision_tools(state: ChatbotState):
    user_query = state["question"]
    selected_tools = []

    # 1) Strict rule-based 체크
    use_slack, recipient, slack_msg = determine_slack_usage(user_query)

    # 2) Fallback: '에게' or 전송 키워드는 있지만 1단계에서 걸리지 않으면 LLM에 확인
    if not use_slack and ("에게" in user_query or any(cmd in user_query for cmd in SEND_COMMANDS)):
        response = model_client.chat.completions.create(
            model=config.config["model"]["name"],
            messages=[
                {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                {"role": "user",   "content": user_query}
            ],
            functions=[slack_sender_function],
            function_call="auto"
        )
        msg_llm = response.choices[0].message
        if msg_llm.get("function_call"):
            args = json.loads(msg_llm.function_call.arguments)
            recipient = args["slack_recipient"]
            slack_msg = args["question"]
            use_slack = True

    # 3) Slack 사용이 결정되면 Slack 툴 추가 및 질문 클린업
    if use_slack:
        selected_tools.append("slack_sender")
        state["slack_recipient"] = recipient
        state["slack_message"]   = slack_msg

        # 질문에서 Slack 지시문(“OO에게”, “보내줘” 등) 제거
        clean_q = re.sub(rf"{re.escape(recipient)}에게", "", user_query)
        clean_q = re.sub(r"(보내줘|전송해줘)", "", clean_q)
        state["question"] = clean_q.strip()
    else:
        state["question"] = user_query
        state["slack_recipient"] = None
        state["slack_message"]   = None

    # 4) 기존 VectorDB/Neo4j 도구 선택 로직 (원본 로직 그대로 복사)
    #    - use_dummy_tools 여부에 따른 키워드 기반
    #    - MCP 자동 선택(LLM function_call) 등
    #    예시 자리입니다. 실제 코드를 그대로 여기에 넣으세요.
    if state["question"].strip():
        if config.config["use_dummy_tools"]:
            # ... 더미 도구 선택 로직 ...
            pass
        else:
            input_msgs = [
                {"role": "system", "content": "Decide which tools to use to answer the user's question."},
                {"role": "user",   "content": state["question"]}
            ]
            resp = model_client.chat.completions.create(
                model=config.config["model"]["name"],
                messages=input_msgs,
                tools=tools,
                function_call="auto"
            )
            for call in resp.choices[0].message.tool_calls:
                name = call.function.name
                if name not in selected_tools:
                    selected_tools.append(name)

    # 5) 도구가 없거나 Slack만 있으면 기본 VectorDB 추가
    if not selected_tools or selected_tools == ["slack_sender"]:
        selected_tools.append("VectorDB_retriever")

    # 최종 상태 업데이트
    state["tools"] = selected_tools
    return state
# ─────────────────────────────────────────────────────────────────────
