from flask import Flask, render_template, request, jsonify, session
import asyncio
import json
import os
from datetime import datetime
import logging

# Neo4j + Pinecone MCP 시스템 import
try:
    from neo4j_pinecone_mcp import MedicalAssistant, MedicalMCPServer
    SYSTEM_AVAILABLE = True
except ImportError:
    SYSTEM_AVAILABLE = False
    print("⚠️ Neo4j + Pinecone MCP 시스템을 import할 수 없습니다.")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'medical_chatbot_secret_key_2024'

# 전역 변수로 어시스턴트 인스턴스 관리
assistant = None
mcp_server = None

def initialize_system():
    """시스템 초기화"""
    global assistant, mcp_server
    
    if not SYSTEM_AVAILABLE:
        return False
    
    try:
        # 환경 변수 설정 (실제 사용시 .env 파일에서 로드)
        os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
        os.environ.setdefault("NEO4J_USER", "neo4j")
        os.environ.setdefault("NEO4J_PASSWORD", "password")
        os.environ.setdefault("PINECONE_API_KEY", "your_pinecone_api_key")
        os.environ.setdefault("PINECONE_ENVIRONMENT", "your_pinecone_environment")
        os.environ.setdefault("PINECONE_INDEX_NAME", "medical-knowledge")
        os.environ.setdefault("OPENAI_API_KEY", "your_openai_api_key")
        os.environ.setdefault("SLACK_WEBHOOK_URL", "your_slack_webhook_url")
        
        # 어시스턴트 초기화
        assistant = MedicalAssistant()
        mcp_server = MedicalMCPServer()
        
        logger.info("의료 챗봇 시스템 초기화 완료")
        return True
        
    except Exception as e:
        logger.error(f"시스템 초기화 실패: {e}")
        return False

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html', system_available=SYSTEM_AVAILABLE)

@app.route('/chat', methods=['POST'])
def chat():
    """챗봇 대화 처리"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({
                'success': False,
                'message': '메시지를 입력해주세요.',
                'timestamp': datetime.now().isoformat()
            })
        
        # 세션에 대화 기록 저장
        if 'chat_history' not in session:
            session['chat_history'] = []
        
        # 사용자 메시지 저장
        session['chat_history'].append({
            'role': 'user',
            'message': user_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # 시스템이 사용 가능한 경우
        if SYSTEM_AVAILABLE and assistant:
            try:
                # 비동기 처리
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                bot_response = loop.run_until_complete(
                    assistant.process_user_query(user_message)
                )
                loop.close()
                
                # 봇 응답 저장
                session['chat_history'].append({
                    'role': 'assistant',
                    'message': bot_response,
                    'timestamp': datetime.now().isoformat()
                })
                
                return jsonify({
                    'success': True,
                    'message': bot_response,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"어시스턴트 처리 오류: {e}")
                error_response = f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}"
                
                session['chat_history'].append({
                    'role': 'assistant',
                    'message': error_response,
                    'timestamp': datetime.now().isoformat()
                })
                
                return jsonify({
                    'success': False,
                    'message': error_response,
                    'timestamp': datetime.now().isoformat()
                })
        
        else:
            # 시스템이 사용 불가능한 경우 시뮬레이션 응답
            simulation_response = simulate_response(user_message)
            
            session['chat_history'].append({
                'role': 'assistant',
                'message': simulation_response,
                'timestamp': datetime.now().isoformat()
            })
            
            return jsonify({
                'success': True,
                'message': simulation_response,
                'timestamp': datetime.now().isoformat()
            })
    
    except Exception as e:
        logger.error(f"챗봇 처리 오류: {e}")
        return jsonify({
            'success': False,
            'message': '서버 오류가 발생했습니다.',
            'timestamp': datetime.now().isoformat()
        })

def simulate_response(user_message):
    """시스템이 사용 불가능할 때 시뮬레이션 응답"""
    user_message_lower = user_message.lower()
    
    if 'p001' in user_message_lower or '김철수' in user_message_lower:
        return """환자 정보:
- 이름: 김철수
- 나이: 45세
- 성별: 남성
- 진단: 당뇨병 2형
- 현재 복용 약물: 메트포르민, 글리메피리드

의료 정보 (시뮬레이션):
1. 당뇨병 2형은 인슐린 저항성과 인슐린 분비 장애로 인한 만성 대사 질환입니다.
   (출처: diabetes_guide.md, 관련성: 0.95)

2. 메트포르민은 당뇨병 2형의 일차 치료제로 사용되며, 간에서 포도당 생성을 억제합니다.
   (출처: medication_guide.md, 관련성: 0.88)

3. 정기적인 혈당 모니터링과 생활습관 개선이 중요합니다.
   (출처: lifestyle_guide.md, 관련성: 0.82)

추가 질문이나 Slack 전송 요청이 있으시면 말씀해 주세요."""

    elif 'p002' in user_message_lower or '이영희' in user_message_lower:
        return """환자 정보:
- 이름: 이영희
- 나이: 32세
- 성별: 여성
- 진단: 고혈압
- 현재 복용 약물: 리시노프릴

의료 정보 (시뮬레이션):
1. 고혈압은 수축기 혈압 140mmHg 이상 또는 이완기 혈압 90mmHg 이상을 의미합니다.
   (출처: hypertension_guide.md, 관련성: 0.92)

2. 리시노프릴은 ACE 억제제로 혈관 확장을 통해 혈압을 낮춥니다.
   (출처: medication_guide.md, 관련성: 0.89)

3. 염분 섭취 제한과 규칙적인 운동이 혈압 관리에 도움이 됩니다.
   (출처: lifestyle_guide.md, 관련성: 0.85)

추가 질문이나 Slack 전송 요청이 있으시면 말씀해 주세요."""

    elif 'slack' in user_message_lower or '보내줘' in user_message_lower:
        return """✅ Slack으로 메시지를 전송했습니다.

🏥 의료 상담 결과

환자 정보와 의료 상담 결과를 Slack 채널로 전송했습니다.
팀원들이 확인할 수 있도록 알림이 발송되었습니다."""

    else:
        return """안녕하세요! 의료 AI 어시스턴트입니다.

사용 가능한 기능:
1. 환자 정보 조회: "P001 환자 정보", "김철수 환자" 등
2. 의료 상담: "당뇨병 치료", "고혈압 관리" 등
3. Slack 전송: "slack으로 보내줘" 등

예시 질문:
- "P001 환자의 당뇨병 치료에 대해 알려줘"
- "이영희 환자의 고혈압 관리 방법을 slack으로 보내줘"

무엇을 도와드릴까요?"""

@app.route('/history')
def get_chat_history():
    """대화 기록 조회"""
    chat_history = session.get('chat_history', [])
    return jsonify({
        'success': True,
        'history': chat_history
    })

@app.route('/clear')
def clear_chat_history():
    """대화 기록 삭제"""
    session['chat_history'] = []
    return jsonify({
        'success': True,
        'message': '대화 기록이 삭제되었습니다.'
    })

@app.route('/status')
def system_status():
    """시스템 상태 확인"""
    return jsonify({
        'system_available': SYSTEM_AVAILABLE,
        'assistant_initialized': assistant is not None,
        'mcp_server_initialized': mcp_server is not None,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/tools')
def list_tools():
    """MCP 도구 목록 조회"""
    if mcp_server and hasattr(mcp_server, 'server'):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tools = loop.run_until_complete(mcp_server.server.list_tools())
            loop.close()
            
            tool_list = []
            for tool in tools:
                tool_list.append({
                    'name': tool.name,
                    'description': tool.description
                })
            
            return jsonify({
                'success': True,
                'tools': tool_list
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })
    else:
        return jsonify({
            'success': False,
            'error': 'MCP 서버가 초기화되지 않았습니다.'
        })

if __name__ == '__main__':
    # 시스템 초기화
    if initialize_system():
        print("✅ 의료 챗봇 시스템이 성공적으로 초기화되었습니다.")
    else:
        print("⚠️ 시스템 초기화에 실패했습니다. 시뮬레이션 모드로 실행됩니다.")
    
    # Flask 앱 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 