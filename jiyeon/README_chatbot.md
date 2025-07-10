# 의료 AI 챗봇 웹 애플리케이션

Neo4j + Pinecone + MCP 기반 의료 상담 챗봇의 웹 인터페이스입니다.

## 🚀 주요 기능

- **실시간 챗봇 인터페이스**: 아름다운 웹 UI로 의료 상담
- **환자 정보 조회**: Neo4j에서 환자 데이터 및 관계 조회
- **의료 지식 검색**: Pinecone에서 관련 의료 문서 검색
- **Slack 연동**: 상담 결과를 Slack으로 전송
- **시뮬레이션 모드**: 시스템 미연결 시에도 테스트 가능
- **대화 기록 관리**: 세션 기반 대화 기록 저장

## 📋 시스템 요구사항

- Python 3.8+
- Neo4j 데이터베이스 (선택사항)
- Pinecone 계정 (선택사항)
- OpenAI API 키 (선택사항)
- Slack Webhook URL (선택사항)

## 🛠️ 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements_flask.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# Neo4j 설정
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Pinecone 설정
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=medical-knowledge

# OpenAI 설정
OPENAI_API_KEY=your_openai_api_key

# Slack 설정
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

### 3. Neo4j + Pinecone MCP 시스템 파일 확인

`neo4j_pinecone_mcp.py` 파일이 같은 디렉토리에 있어야 합니다.

## 🚀 실행 방법

### 1. 기본 실행

```bash
python app.py
```

### 2. 브라우저에서 접속

```
http://localhost:5000
```

## 🎯 사용 방법

### 웹 인터페이스 기능

1. **시스템 상태 확인**: 우상단에 시스템 상태가 표시됩니다
   - 🟢 온라인: 모든 시스템이 정상 작동
   - 🟡 시뮬레이션: 실제 DB 없이 테스트 모드
   - 🔴 오프라인: 시스템 연결 실패

2. **예시 질문**: 상단의 예시 질문을 클릭하여 빠르게 테스트

3. **실시간 채팅**: 하단 입력창에서 질문 입력

### 예시 질문

```
# 환자 정보 조회
P001 환자의 당뇨병 치료에 대해 알려줘
이영희 환자의 고혈압 관리 방법

# 관계 정보 조회
P001 환자의 관계 정보를 조회해줘
김철수 환자가 어떤 의사와 연결되어 있나요?

# Slack 전송
이영희 환자의 고혈압 관리 방법을 slack으로 보내줘
P001 환자 정보를 팀에 공유해줘

# 의료 지식 검색
당뇨병 2형의 치료 방법
고혈압 환자의 생활 관리
```

## 🔧 API 엔드포인트

### POST /chat
챗봇과 대화

**요청:**
```json
{
    "message": "P001 환자의 당뇨병 치료에 대해 알려줘"
}
```

**응답:**
```json
{
    "success": true,
    "message": "환자 정보와 의료 상담 결과...",
    "timestamp": "2024-01-01T12:00:00"
}
```

### GET /status
시스템 상태 확인

**응답:**
```json
{
    "system_available": true,
    "assistant_initialized": true,
    "mcp_server_initialized": true,
    "timestamp": "2024-01-01T12:00:00"
}
```

### GET /history
대화 기록 조회

### POST /clear
대화 기록 삭제

### GET /tools
MCP 도구 목록 조회

## 🎨 UI 특징

- **반응형 디자인**: 모바일/태블릿/데스크톱 지원
- **실시간 타이핑 표시**: AI가 답변 생성 중임을 표시
- **시스템 상태 표시**: 실시간 시스템 연결 상태 확인
- **예시 질문**: 클릭 한 번으로 빠른 테스트
- **대화 기록**: 세션 기반 대화 기록 유지

## 🔍 문제 해결

### 1. 시스템이 시뮬레이션 모드로 실행되는 경우

- Neo4j 데이터베이스가 실행 중인지 확인
- Pinecone API 키가 올바른지 확인
- OpenAI API 키가 설정되었는지 확인
- `neo4j_pinecone_mcp.py` 파일이 존재하는지 확인

### 2. 웹 페이지가 로드되지 않는 경우

- Flask 서버가 실행 중인지 확인
- 포트 5000이 사용 가능한지 확인
- 방화벽 설정 확인

### 3. 챗봇 응답이 느린 경우

- 네트워크 연결 상태 확인
- OpenAI API 응답 시간 확인
- Neo4j/Pinecone 연결 상태 확인

## 📁 파일 구조

```
jiyeon/
├── app.py                    # Flask 웹 애플리케이션
├── templates/
│   └── index.html           # 웹 인터페이스 템플릿
├── neo4j_pinecone_mcp.py    # MCP 시스템 (별도 생성 필요)
├── requirements_flask.txt   # Flask 의존성
└── README_chatbot.md        # 이 파일
```

## 🔄 개발 모드

개발 중에는 Flask의 디버그 모드가 활성화되어 있습니다:

```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

이를 통해 코드 변경 시 자동으로 서버가 재시작됩니다.

## 🚀 배포

### 로컬 배포
```bash
python app.py
```

### 프로덕션 배포
```bash
# 디버그 모드 비활성화
app.run(debug=False, host='0.0.0.0', port=5000)

# 또는 Gunicorn 사용
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📞 지원

문제가 발생하거나 추가 기능이 필요한 경우:

1. 시스템 상태를 확인하세요 (`/status` 엔드포인트)
2. 로그를 확인하세요 (콘솔 출력)
3. 환경 변수가 올바르게 설정되었는지 확인하세요

---

**의료 AI 어시스턴트** - Neo4j + Pinecone + MCP 기반 의료 상담 시스템 