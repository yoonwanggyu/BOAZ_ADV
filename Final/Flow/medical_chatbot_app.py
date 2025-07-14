import streamlit as st
import asyncio
from main import * # send_slack_message 추가
from io import StringIO
import requests # 이 import는 현재 코드에서 사용되지 않으므로 제거해도 됩니다.

thread_id = "thread-1"

# --- 페이지 설정 ---
st.set_page_config(
    page_title="땡큐소아마취 챗봇",
    page_icon="🩺",
    layout="wide"
)

# --- 1. 전역 스타일 및 폰트 설정 ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Nanum+Gothic:wght@400;700&display=swap" rel="stylesheet">
<style>
    * {
        font-family: 'Nanum Gothic', sans-serif !important;
    }
    body, .stApp {
        background-color: #eaf4fb !important;
    }
    /* 전체 폰트 적용 */
    html, body, [class*="st-"], button, input, textarea {
        font-family: 'Nanum Gothic', sans-serif;
    }

    /* 메인 페이지 타이틀 */
    .main-title {
        text-align: center;
        color: #4F8BF9;
        font-weight: 1000;
    }

    /* 메인 페이지 서브타이틀 */
    .main-subtitle {
        text-align: center;
        color: #555555;
        margin-bottom: 2rem;
    }
    
    /* 기능 소개 카드 스타일 */
    .feature-card {
        background: #f7faff;
        border-radius: 15px;
        padding: 24px 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
    }
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
    }
    .feature-card h3 {
        color: #4F8BF9;
        margin-bottom: 12px;
        font-size: 1.3em;
    }
    .feature-card p {
        font-size: 1em;
        color: #333;
        line-height: 1.6;
    }
    .feature-icon {
        font-size: 3em;
        margin-bottom: 1rem;
    }
            
    /* 기본 버튼 스타일 */
    .stButton>button {
        background-color: #4F8BF9;
        color: white;
        font-size: 2rem;
        font-weight: 900;
        border-radius: 8px;
        height: 3em;
        width: 100%;
        transition: all 0.2s ease-in-out;
        border: none;
        box-shadow: 0 4px 10px rgba(79, 139, 249, 0.3);
    }
    .stButton>button:hover {
        background-color: #3c7de0;
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(79, 139, 249, 0.4);
    }
    .stButton>button:active {
        background-color: #cccccc !important;
        color: #222 !important;
        transform: translateY(0);
        box-shadow: none !important;
    }

    /* 푸터 스타일 */
    .footer {
        text-align: center;
        color: #aaa;
        font-size: 0.9em;
        margin-top: 3rem;
    }

    .start-chat-title {
        text-align: center;
        color: #222;
        font-size: 1.1rem !important;
        font-weight: 700;
    }
    .stButton>button {
        background-color: #4F8BF9;
        color: white;
        font-size: 1.5rem;
        font-weight: 900;
        border-radius: 8px;
        height: 3em;
        width: 100%;
        transition: all 0.2s ease-in-out;
        border: none;
        box-shadow: 0 4px 10px rgba(79, 139, 249, 0.3);
    }

    /* 사이드바 버튼 폭 줄이기 */
    div[data-testid="stSidebar"] .stButton > button {
        width: 80% !important;
        min-width: 0 !important;
        max-width: 200px !important;
        margin-left: auto;
        margin-right: auto;
        display: block;
        height: 1.1em !important;
        padding-top: 0.1em !important;
        padding-bottom: 0.1em !important;
        line-height: 0.6 !important;
    }

    /* 사이드바 버튼 높이/패딩 강제 조정 */
    section[data-testid="stSidebar"] button {
        height: 2.2em !important;
        padding-top: 0.4em !important;
        padding-bottom: 0.4em !important;
        line-height: 2.4 !important;
        font-size: 1.1rem !important;
        min-height: unset !important;
        max-height: 2.6em !important;
    }

    /* 사이드바 세션 버튼 텍스트 한 줄 표시, 넘치면 ... 처리 (강제 적용) */
    div[data-testid="stSidebar"] .stButton > button {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 220px !important;
        min-width: 0 !important;
        padding: 0.5em 1em !important;
        height: auto !important;
        line-height: 1.3 !important;
    }

    /* 텍스트 입력 라벨 가운데 정렬 */
    div[data-testid="stTextInput"] label {
        width: 100%;
        text-align: center !important;
        display: block !important;
        justify-content: center !important;
        align-items: center !important;
    }

</style>
""", unsafe_allow_html=True)


# --- 2. 화면 상태 관리 ---
if "page" not in st.session_state:
    st.session_state["page"] = "main"

def go_to_chatbot():
    st.session_state["page"] = "chatbot"

def go_to_main():
    st.session_state["page"] = "main"


# --- 3. 페이지 렌더링 ---
if st.session_state["page"] == "main":
    # --- 메인 페이지 ---
    st.markdown("<h1 class='main-title'>🩺 땡큐소아마취 챗봇</h1>", unsafe_allow_html=True)
    st.markdown("<p class='main-subtitle'>임상 질문부터 환자 데이터 기반 관리까지, 소아마취의 모든 것을 도와드립니다.</p>", unsafe_allow_html=True)
    st.write("") 
    st.write("") 
    st.subheader("✨ 주요 기능")
    st.write("")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🤖</div>
            <h3>RAG 기반 임상 질문</h3>
            <p>소아마취와 관련된 모든 임상적 질문에 대해 최신 문서를 참고하여 빠르고 정확한 답변을 제공합니다.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🗂️</div>
            <h3>환자 데이터 기반 관리</h3>
            <p>환자 ID로 <strong>수술 정보, 임상 차트</strong>를 실시간 조회하고, 이를 바탕으로 맞춤형 질문에 답변하여 효율적인 <strong>환자 관리</strong>를 지원합니다.</p>
        </div>
        """, unsafe_allow_html=True)
    st.write("")
    col3, col4 = st.columns(2, gap="medium")
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💬</div>
            <h3>Slack 메시지 연동</h3>
            <p>중요하거나 공유하고 싶은 검색 결과를 동료에게 즉시 Slack 메시지로 전송하여 효율적인 협업이 가능합니다.</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💾</div>
            <h3>대화 내용 저장</h3>
            <p>챗봇과의 중요한 대화 내용을 언제든지 텍스트 파일로 다운로드하여 기록하고 관리할 수 있습니다.</p>
        </div>
        """, unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div style='text-align:center;'>
        <h3 class='start-chat-title'>👇 사용자 이름을 입력하고 챗봇을 시작해주세요 </h3>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div style='display:flex; justify-content:center;'><div style='width:300px;'>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1])
    with col1:
        user_name = st.text_input("", value=st.session_state.get("user_name", ""), key="user_name_inline", placeholder="이름 입력")
        st.session_state["user_name"] = user_name
    with col2:
        st.write("")  # 버튼을 아래로 내리기 위한 공간
        st.button("챗봇 시작하기", on_click=go_to_chatbot, disabled=not bool(user_name.strip()), use_container_width=True)
    st.image("image.png", use_container_width=True)
    st.markdown("<div class='footer'>© 2025 Thank You Pediatric Anesthesia. All Rights Reserved.</div>", unsafe_allow_html=True)

else: # "chatbot" 페이지
    # --- 챗봇 페이지 ---
    user_name = st.session_state.get("user_name", "사용자")
    st.markdown(f"<h4 style='color: #222; margin-bottom:1rem;'>안녕하세요 {user_name}님!👋</h4>", unsafe_allow_html=True)
    st.markdown("<h2 style='color: #222;'>🩺 땡큐소아마취 챗봇</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    box_style = "background:{bg}; border-radius:12px; padding:14px; text-align:center; box-shadow:0 2px 8px #0001; height:120px; display:flex; flex-direction:column; justify-content:center; align-items:center; font-size:0.9rem;"
    icon_box_style = "width:100%; display:flex; justify-content:center; align-items:center; height:36px; margin-bottom:0.5em;"
    with col1:
        st.markdown(f"""<div style='{box_style.format(bg="#fef9e7")}'><div style='{icon_box_style}'><span style='font-size:1.5rem;'>🆔</span></div><div><b>환자 이름 혹은 특정 수술 이력</b>을 포함하여 질문해 보세요.</div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div style='{box_style.format(bg="#eafaf1")}'><div style='{icon_box_style}'><span style='font-size:1.5rem;'>📋</span></div><div>환자의 <b>임상 차트와 수술 정보</b>를 실시간으로 조회하여 답변을 생성합니다.</div></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div style='{box_style.format(bg="#fef9e7")}'><div style='{icon_box_style}'><img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style="height:1.5rem;"></div><div>원하는 동료에게 <b>Slack</b>으로 답변을 자동 전송해드립니다.</div></div>""", unsafe_allow_html=True)
    st.divider()

    if "sessions" not in st.session_state:
        st.session_state.sessions = [[]]
    if "current_session_index" not in st.session_state:
        st.session_state.current_session_index = 0

    def switch_session(session_index):
        st.session_state.current_session_index = session_index

    with st.sidebar:
        st.markdown('<div style="text-align:center; font-size:2.5rem; margin-bottom:0.5em;">🐘</div>', unsafe_allow_html=True)
        if st.button("⬅️ 메인으로 돌아가기"):
            go_to_main()
        st.markdown("---")
        if st.button("🆕 새 채팅 시작"):
            st.session_state.sessions.append([])
            switch_session(len(st.session_state.sessions) - 1)
        st.markdown("---")
        st.markdown("#### 💬 채팅 세션 기록")
        if not any(st.session_state.sessions):
            st.markdown("_아직 저장된 세션이 없습니다._")
        else:
            for i, session in enumerate(st.session_state.sessions):
                if session:
                    first_q = next((msg['content'] for msg in session if msg['role'] == 'user'), "세션")
                    display_text = first_q[:10] + ("..." if len(first_q) > 10 else "")
                    st.button(f"📜 {display_text}", key=f"session_{i}", on_click=switch_session, args=(i,))
                else:
                    st.button(f"🆕 새 채팅 {i+1}", key=f"session_{i}", on_click=switch_session, args=(i,))
        st.markdown(
            '''
            <a href="https://app.slack.com/client/T093ELJBE2Z" target="_blank"
                style="display:inline-block; background:#611f69; color:#fff; font-weight:700; padding:0.7em 2em; border-radius:8px; text-decoration:none; font-size:1.1rem; box-shadow:0 2px 8px #0002; margin-top:2em;">
                <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style="height:1.3em; vertical-align:middle; margin-right:0.5em;">
                Slack으로 이동
            </a>
            ''', unsafe_allow_html=True
        )

    current_messages = st.session_state.sessions[st.session_state.current_session_index]
    for message in current_messages:
        if message["role"] == "user":
            st.markdown(f"""<div style='display:flex; justify-content:flex-end; margin-bottom:8px;'><div style='background:#fff; color:#222; border-radius:16px 16px 4px 16px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>{message["content"]}</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style='display:flex; justify-content:flex-start; margin-bottom:8px;'><div style='background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>{message["content"]}</div></div>""", unsafe_allow_html=True)

    input_and_loading = st.empty()

    if len(current_messages) > 0:
        st.divider()
        buffer = StringIO()
        for m in current_messages:
            role = "사용자" if m["role"] == "user" else "챗봇"
            buffer.write(f"{role}: {m['content']}\n\n")
        
        st.download_button(
            label="📄 현재 대화 내용 다운로드",
            data=buffer.getvalue(),
            file_name=f"chat_history_session_{st.session_state.current_session_index + 1}.txt",
            mime="text/plain"
        )

    # 1. 요약 함수 정의 (예시: single_question 재활용)
    def summarize_history(history_text):
        summary_prompt = f"다음 대화를 한두 문장으로 요약해줘:\n{history_text}"
        return asyncio.run(run_chatbot (summary_prompt,thread_id))

    # 중복 메시지 및 무한루프 방지용 입력 상태 관리
    if "pending_prompt" not in st.session_state:
        st.session_state["pending_prompt"] = None

    prompt = st.chat_input("환자 ID 또는 질문을 입력하세요...")

    # 입력이 들어오면 pending_prompt에 저장하고 rerun
    if prompt and st.session_state["pending_prompt"] is None:
        st.session_state["pending_prompt"] = prompt
        st.rerun()

    # pending_prompt가 있을 때만 답변 생성 및 세션 추가
    if st.session_state["pending_prompt"]:
        user_prompt = st.session_state["pending_prompt"]
        st.session_state.sessions[st.session_state.current_session_index].append({"role": "user", "content": user_prompt})

        with input_and_loading.container():
            st.markdown(f"""
            <div style='display:flex; justify-content:flex-end; margin-bottom:8px;'>
                <div style='background:#fff; color:#222; border-radius:16px 16px 4px 16px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                    {user_prompt}
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div style='display:flex; justify-content:flex-start; margin-bottom:8px;'>
                <div style='background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001; font-style:italic;'>
                    답변을 생성하는 중...
                </div>
            </div>
            """, unsafe_allow_html=True)

        # single_question 호출 및 결과 분리 (한 번만 호출)
        import asyncio
        
        # 멀티턴 대화를 위해 이전 대화 내용 추가
        current_messages = st.session_state.sessions[st.session_state.current_session_index]
        if len(current_messages) > 0:
            # 이전 대화 내용을 문자열로 구성
            conversation_history = ""
            for msg in current_messages[-4:]:  # 최근 4개 메시지만 포함 (너무 길어지지 않도록)
                role = "사용자" if msg["role"] == "user" else "챗봇"
                conversation_history += f"{role}: {msg['content']}\n"
            
            # 이전 대화가 많으면 요약 추가
            if len(current_messages) > 6:
                # 4개 이전의 대화들을 요약
                older_messages = current_messages[:-4]
                older_conversation = ""
                for msg in older_messages:
                    role = "사용자" if msg["role"] == "user" else "챗봇"
                    older_conversation += f"{role}: {msg['content']}\n"
                
                # 요약 생성
                summary = summarize_history(older_conversation)
                enhanced_prompt = f"""이전 대화 요약:
                                    {summary}

                                    최근 대화:
                                    {conversation_history}

                                    지시사항: 위의 '이전 대화'를 모두 참고하여 '현재 질문'에 대해 한국어로 자연스럽게 답변하세요. 
                                    이전 대화의 맥락을 유지하면서 현재 질문에 정확하고 유용한 답변을 제공하세요.
                                    만약 질문에 "전달해줘", "전해줘", "보내줘" 등의 표현이 있다면: 
                                    1. 현재 질문맥락을 1줄로 요약 설명한 후 답변을 제공해주세요.
                                    2. 실제 직장 동료에게 말을 전달하는 것처럼 정중하게 구성해주세요. 
                                    
                                    현재 질문: {user_prompt}"""
            else:
                # 현재 프롬프트에 이전 대화 내용 추가
                enhanced_prompt = f"""이전 대화:
                                    {conversation_history}

                                    지시사항: 위의 '이전 대화'를 모두 참고하여 '현재 질문'에 대해 한국어로 자연스럽게 답변하세요. 
                                    이전 대화의 맥락을 유지하면서 현재 질문에 정확하고 유용한 답변을 제공하세요.
                                    만약 질문에 "전달해줘", "전해줘", "보내줘" 등의 표현이 있다면: 
                                    1. 현재 질문맥락을 1줄로 요약 설명한 후 답변을 제공해주세요.
                                    2. 실제 직장 동료에게 말을 전달하는 것처럼 정중하게 구성해주세요. 
                                    
                                    현재 질문: {user_prompt}"""
        else:
            enhanced_prompt = user_prompt
        
        result = asyncio.run(run_chatbot(enhanced_prompt,thread_id))
        result_recipient = asyncio.run(run_chatbot(user_prompt,thread_id))
        answer = result["answer"]
        slack_needed = result["slack_needed"]
        recipient = result_recipient["recipient"]
        slack_message = result["message"]

        # 답변만 먼저 세션에 추가
        st.session_state.sessions[st.session_state.current_session_index].append({"role": "assistant", "content": answer})
        # Slack 전송 정보 임시 저장 (message 대신 answer 저장)
        st.session_state["last_slack_needed"] = slack_needed
        st.session_state["last_slack_recipient"] = recipient
        st.session_state["last_slack_message"] = answer  # 챗봇 답변을 저장
        st.session_state["pending_prompt"] = None
        # 슬랙 전송 필요하면 챗봇 메시지로 안내 추가
        if slack_needed and recipient:
            slack_prompt = f"이 답변을 슬랙으로 {recipient}님께 보내시겠습니까?"
            st.session_state.sessions[st.session_state.current_session_index].append({"role": "assistant", "content": slack_prompt})
        st.rerun()

    # 답변이 생성된 후, slack_needed가 True면 챗봇 메시지 바로 아래에 버튼 노출
    # 버튼은 마지막 메시지가 '이 답변을 슬랙으로 ...'일 때만 노출
    if (
        st.session_state.get("last_slack_needed")
        and st.session_state.get("last_slack_recipient")
        and st.session_state.get("last_slack_message")
    ):
        last_msg = st.session_state.sessions[st.session_state.current_session_index][-1]["content"]
        if "슬랙으로" in last_msg and "보내시겠습니까" in last_msg:
            col1, col2 = st.columns([5, 1])
            # with col1:
            #     st.markdown(
            #         f"<div style='display:flex; align-items:center; font-size:0.98rem; background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:10px 16px; max-width:70%; box-shadow:0 2px 8px #0001; margin-bottom:8px;'>"
            #         f"이 답변을 슬랙으로 <b>{st.session_state['last_slack_recipient']}님</b>께 전송할까요?"
            #         f"</div>",
            #         unsafe_allow_html=True
            #     )
            recipient = st.session_state.get("last_slack_recipient")
            # with col2:
            #     if st.button(f"{recipient}님에게 전송", key="slack_send_inline"):
            #         import asyncio
            #         user_name = st.session_state.get("user_name", "사용자")
            #         slack_message_with_prefix = f"{user_name}님이 전달하는 메시지입니다:\n\n{st.session_state['last_slack_message']}"
            #         send_result = asyncio.run(send_slack_message(
            #             st.session_state["last_slack_recipient"],
            #             slack_message_with_prefix
            #         ))
            #         st.session_state.sessions[st.session_state.current_session_index].append({"role": "assistant", "content": send_result})
            #         st.session_state["last_slack_needed"] = False
            #         st.session_state["last_slack_recipient"] = None
            #         st.session_state["last_slack_message"] = None
            #         st.rerun()