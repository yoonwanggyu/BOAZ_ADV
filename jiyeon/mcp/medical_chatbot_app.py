import streamlit as st
import asyncio
from mcp_langgraph import single_question # 이 부분은 실제 프로젝트에 맞게 수정해야 할 수 있습니다.
from io import StringIO
import requests # 이 import는 현재 코드에서 사용되지 않으므로 제거해도 됩니다.

# --- 페이지 설정 ---
st.set_page_config(
    page_title="땡큐소아마취 챗봇",
    page_icon="🩺",
    layout="centered"
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
        font-size: 1.1rem !important;
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

    # 헤더 (부제 수정)
    st.markdown("<h1 class='main-title'>🩺 땡큐소아마취 챗봇</h1>", unsafe_allow_html=True)
    st.markdown("<p class='main-subtitle'>임상 질문부터 환자 데이터 기반 관리까지, 소아마취의 모든 것을 도와드립니다.</p>", unsafe_allow_html=True)

    st.write("") 
    st.write("") 

    # 주요 기능 소개
    st.subheader("✨ 주요 기능")
    st.write("")

    # 2x2 그리드로 레이아웃 변경
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        # 1. AI 기반 임상 질문 답변
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🤖</div>
            <h3>RAG 기반 임상 질문</h3>
            <p>소아마취와 관련된 모든 임상적 질문에 대해 최신 문서를 참고하여 빠르고 정확한 답변을 제공합니다.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # 2. 환자 데이터 기반 관리 (사용자 요청 사항)
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🗂️</div>
            <h3>환자 데이터 기반 관리</h3>
            <p>환자 ID로 <strong>수술 정보, 임상 차트</strong>를 실시간 조회하고, 이를 바탕으로 맞춤형 질문에 답변하여 효율적인 <strong>환자 관리</strong>를 지원합니다.</p>
        </div>
        """, unsafe_allow_html=True)

    st.write("") # 줄 간격 추가

    col3, col4 = st.columns(2, gap="medium")

    with col3:
        # 3. Slack 메시지 연동
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💬</div>
            <h3>Slack 메시지 연동</h3>
            <p>중요하거나 공유하고 싶은 검색 결과를 동료에게 즉시 Slack 메시지로 전송하여 효율적인 협업이 가능합니다.</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        # 4. 대화 내용 저장
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💾</div>
            <h3>대화 내용 저장</h3>
            <p>챗봇과의 중요한 대화 내용을 언제든지 텍스트 파일로 다운로드하여 기록하고 관리할 수 있습니다.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()

    # Call to Action
    st.markdown("<h3 class='start-chat-title'>👇 챗봇을 시작해주세요 </h3>", unsafe_allow_html=True)
    st.button("챗봇 시작하기", on_click=go_to_chatbot)

    # 챗봇 시작하기 버튼 아래에 이미지 추가
    st.image("image.png", use_container_width=True)

    # 푸터
    st.markdown("<div class='footer'>© 2025 Thank You Pediatric Anesthesia. All Rights Reserved.</div>", unsafe_allow_html=True)

else: # "chatbot" 페이지
    # --- 챗봇 페이지 ---
    # 챗봇 페이지 타이틀
    st.markdown("<h2 style='color: #222;'>🩺 땡큐소아마취 챗봇</h2>", unsafe_allow_html=True)

    # 안내 문구를 3개의 가로 박스로 예쁘게 배치 (가로폭 넓힘, 높이 동일하게)
    col1, col2, col3 = st.columns(3) # 동일한 비율로 설정
    box_style = "background:{bg}; border-radius:12px; padding:14px; text-align:center; box-shadow:0 2px 8px #0001; height:120px; display:flex; flex-direction:column; justify-content:center; align-items:center; font-size:0.9rem;"
    icon_box_style = "width:100%; display:flex; justify-content:center; align-items:center; height:36px; margin-bottom:0.5em;"

    with col1:
        st.markdown(
            f"""
            <div style='{box_style.format(bg="#fef9e7")}'>
                <div style='{icon_box_style}'><span style='font-size:1.5rem;'>🆔</span></div>
                <div><b>환자 이름 혹은 특정 수술 이력</b>을 포함하여 질문해 보세요.</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown(
            f"""
            <div style='{box_style.format(bg="#eafaf1")}'>
                <div style='{icon_box_style}'><span style='font-size:1.5rem;'>📋</span></div>
                <div>환자의 <b>임상 차트와 수술 정보</b>를 실시간으로 조회하여 답변을 생성합니다.</div>
            </div>
            """, unsafe_allow_html=True)

    with col3:
        st.markdown(
            f"""
            <div style='{box_style.format(bg="#fef9e7")}'>
                <div style='{icon_box_style}'><img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style="height:1.5rem;"></div>
                <div>원하는 동료에게 <b>Slack</b>으로 답변을 자동 전송해드립니다.</div>
            </div>
            """, unsafe_allow_html=True)
    st.divider()

    # --- ✨✨✨ 새로운 세션 관리 로직 ✨✨✨ ---
    if "sessions" not in st.session_state:
        # 세션 리스트 초기화 (첫 번째 세션은 비어있는 리스트)
        st.session_state.sessions = [[]]
    if "current_session_index" not in st.session_state:
        # 현재 보고 있는 세션의 인덱스
        st.session_state.current_session_index = 0

    def switch_session(session_index):
        """세션을 전환하는 함수"""
        st.session_state.current_session_index = session_index

    # --- 사이드바 ---
    with st.sidebar:
        # 코끼리 이모티콘을 맨 위가 아니라 '메인으로 돌아가기' 버튼 바로 위에 배치
        st.markdown('<div style="text-align:center; font-size:2.5rem; margin-bottom:0.5em;">🐘</div>', unsafe_allow_html=True)
        if st.button("⬅️ 메인으로 돌아가기"):
            go_to_main()
        st.markdown("---")

        # 새 채팅 시작 버튼
        if st.button("🆕 새 채팅 시작"):
            st.session_state.sessions.append([])
            switch_session(len(st.session_state.sessions) - 1)

        st.markdown("---")
        st.markdown("#### 💬 채팅 세션 기록")

        if not any(st.session_state.sessions): # 모든 세션이 비어있는 경우
             st.markdown("_아직 저장된 세션이 없습니다._")
        else:
            # 각 세션으로 전환하는 버튼 생성
            for i, session in enumerate(st.session_state.sessions):
                if session: # 세션에 메시지가 있는 경우
                    # 첫 번째 사용자 메시지를 버튼 레이블로 사용
                    first_q = next((msg['content'] for msg in session if msg['role'] == 'user'), "세션")
                    st.button(f"📜 {first_q[:20]}...", key=f"session_{i}", on_click=switch_session, args=(i,))
                else: # 비어있는 새 채팅 세션
                    st.button(f"🆕 새 채팅 {i+1}", key=f"session_{i}", on_click=switch_session, args=(i,))

    # --- 현재 선택된 세션의 대화 내용 카톡 스타일로 표시 (사용자: 오른쪽, 챗봇: 왼쪽) ---
    current_messages = st.session_state.sessions[st.session_state.current_session_index]

    for message in current_messages:
        if message["role"] == "user":
            st.markdown(
                f"""
                <div style='display:flex; justify-content:flex-end; margin-bottom:8px;'>
                    <div style='background:#fff; color:#222; border-radius:16px 16px 4px 16px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                        {message["content"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div style='display:flex; justify-content:flex-start; margin-bottom:8px;'>
                    <div style='background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                        {message["content"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # --- 사용입력 및 챗봇 응답 (카톡 스타일, 로딩 말풍선: 왼쪽) ---
    prompt = None
    if st.session_state.get("pending_prompt"):
        prompt = st.session_state["pending_prompt"]
        st.session_state["pending_prompt"] = None
    else:
        prompt = st.chat_input("환자 ID 또는 질문을 입력하세요...")

    if prompt:
        # 사용자 말풍선(오른쪽)
        st.markdown(
            f"""
            <div style='display:flex; justify-content:flex-end; margin-bottom:8px;'>
                <div style='background:#fff; color:#222; border-radius:16px 16px 4px 16px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                    {prompt}
                </div>
            </div>
            """, unsafe_allow_html=True)
        # 챗봇 로딩 말풍선(왼쪽)
        loading_box = st.empty()
        loading_box.markdown(
            """
            <div style='display:flex; justify-content:flex-start; margin-bottom:8px;'>
                <div style='background:#b3d8f6; color:#aaa; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001; font-style:italic;'>
                    ...
                </div>
            </div>
            """, unsafe_allow_html=True)
        # 현재 세션에 사용자 메시지 추가
        st.session_state.sessions[st.session_state.current_session_index].append({"role": "user", "content": prompt})
        # 챗봇 답변 생성
        with st.spinner("답변을 생성하는 중..."):
            result = asyncio.run(single_question(prompt))
        # 로딩 말풍선 자리에 챗봇 답변(왼쪽) 표시
        loading_box.markdown(
            f"""
            <div style='display:flex; justify-content:flex-start; margin-bottom:8px;'>
                <div style='background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                    {result}
                </div>
            </div>
            """, unsafe_allow_html=True)
        # 현재 세션에 챗봇 답변 추가
        st.session_state.sessions[st.session_state.current_session_index].append({"role": "assistant", "content": result})
        st.rerun()

    # --- 현재 세션 대화 내용 다운로드 ---
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

    # --- 사이드바 맨 아래에 Slack 연결 버튼 ---
    st.sidebar.markdown(
        '''
        <a href="https://app.slack.com/client/T093ELJBE2Z" target="_blank"
           style="display:inline-block; background:#611f69; color:#fff; font-weight:700; padding:0.7em 2em; border-radius:8px; text-decoration:none; font-size:1.1rem; box-shadow:0 2px 8px #0002; margin-top:2em;">
            <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style="height:1.3em; vertical-align:middle; margin-right:0.5em;">
            Slack으로 이동
        </a>
        ''', unsafe_allow_html=True
    )
# --- ✨✨✨ 여기까지 수정되었습니다 ✨✨✨ ---