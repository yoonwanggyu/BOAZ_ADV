from main import *

from io import StringIO
import streamlit as st
import asyncio
import asyncio
        

thread_id = "thread-2"

# 페이지 설정
st.set_page_config(
    page_title="땡큐소아마취 챗봇",
    page_icon="🩺",
    layout="wide"
)

# 1.전역 스타일 및 폰트 설정 
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


# 2. 화면 상태 관리
if "page" not in st.session_state:
    st.session_state["page"] = "main"

def go_to_chatbot():
    st.session_state["page"] = "chatbot"

def go_to_main():
    st.session_state["page"] = "main"


# 3. 페이지 렌더링
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
    st.image("data 폴더에 있는 이미지 경로", use_container_width=True)
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
    def run_async(coro):
        try:
            # 기존 루프가 있는지 확인
            loop = asyncio.get_event_loop()
            # 기존 루프에서 실행
            return loop.run_until_complete(coro)
        except RuntimeError:
            # 루프가 없으면 새로 만들기
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            except Exception as e:
                st.error(f"비동기 실행 오류: {e}")
                return None
            finally:
                loop.close()
        except Exception as e:
            st.error(f"run_async 오류: {e}")
            return None
            

    # 요약 함수 정의 (예시: single_question 재활용)
    def summarize_history(history_text):
        summary_prompt = f"다음 대화를 한두 문장으로 요약해줘:\n{history_text}"
        return summary_prompt

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

        
        # 사용자 입력 프롬프트만 바로 챗봇에 전달
        try:
            # 1. 이전 대화 내역 합치기
            messages = st.session_state.sessions[st.session_state.current_session_index]
            history = ""
            for m in messages:
                if m["role"] == "user":
                    history += f"사용자: {m['content']}\n"
                else:
                    history += f"챗봇: {m['content']}\n"

            # 2. 시스템 지침 추가
            system_instruction = (
                "여기까지는 이전 대화 내역입니다.\n"
                "이전 대화 내역에서는 절대로 slack 메세지 전송 여부를 판단하지 마세요.\n"
                "만약 Slack(슬랙)으로 메시지를 보내야 하는지 판단할 때는, "
                "반드시 다음 나오는 사용자 질문(가장 최근 질문)에서만 판단하세요\n"                
                "다음은 최근 사용자 질문입니다. 다음 질문에서만 slack 메세지 전송 여부를 파악하세요\n"
            )

            # 3. 새 질문과 합치기
            user_prompt = st.session_state["pending_prompt"]
            full_query = history + system_instruction + f"현재 질문: {user_prompt}\n"

            # 3. LLM에 전달
            result = Runner.run_sync(full_query, "thread-2", user_name=user_name)
            st.write(f"디버깅: result = {result}")
        except Exception as e:
            st.error(f"챗봇 실행 오류: {e}")
            result = None
        
        # 결과가 None인 경우 처리
        if result is None:
            st.error("챗봇 실행 중 오류가 발생했습니다.")
            st.session_state["pending_prompt"] = None
            st.rerun()
        
        answer = result
        
        # 답변만 세션에 추가
        st.session_state.sessions[st.session_state.current_session_index].append({"role": "assistant", "content": answer})
        # 답변을 바로 화면에 출력
        st.markdown(f"""
        <div style='display:flex; justify-content:flex-start; margin-bottom:8px;'>
            <div style='background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                {answer}
            </div>
        </div>
        """, unsafe_allow_html=True)
        # slack response일 때 전송 완료 안내 메시지 추가
        if answer and "전달하는 메세지 입니다." in answer:
            st.markdown("<div style='color:#228B22; font-weight:700; margin-bottom:1em;'>챗봇이 Slack으로 전송을 완료하였습니다.</div>", unsafe_allow_html=True)
        st.session_state["pending_prompt"] = None
        st.rerun()

        # 답변만 세션에 추가
        st.session_state.sessions[st.session_state.current_session_index].append({"role": "assistant", "content": answer})
        # 답변을 바로 화면에 출력
        st.markdown(f"""
        <div style='display:flex; justify-content:flex-start; margin-bottom:8px;'>
            <div style='background:#b3d8f6; color:#222; border-radius:16px 16px 16px 4px; padding:12px 18px; max-width:70%; box-shadow:0 2px 8px #0001;'>
                {answer}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.session_state["pending_prompt"] = None
        st.rerun()
