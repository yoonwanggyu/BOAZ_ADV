![header](https://capsule-render.vercel.app/api?type=Waving&color=auto&height=300&fontAlignY=50&fontAlign=50&section=header&text=땡큐소아마취&fontSize=50)
<div align=center>

LangGraph 기반 파이프라인과 MCP(Model Context Protocol) 인프라 위에 구축된 **소아마취 도메인 특화 AI 챗봇**입니다.  
Pinecone DB(의료 지식)와 Neo4j DB(환자·수술 기록)를 양방향으로 조회하고, Slack 워크스페이스와 실시간으로 연동되어 병원 내 의료진이 **정보를 즉시 공유**할 수 있습니다.
</div>

## 🗓️ Timeline
2025.02 ~ 2025.08

## 👪 Team
| 이름          | GitHub 프로필                                             |
| ------------- | --------------------------------------------------------- |
| 백다은        | [nuebaek](https://github.com/nuebaek)              |
| 이재원        | [Jaewon1634](https://github.com/Jaewon1634)      |
| 윤왕규       | [yoonwanggyu](https://github.com/yoonwanggyu)                |
| 박혜원       | [nowhye](https://github.com/nowhye)               |
| 백지연       | [wlsisl](https://github.com/wlsisl)              |

## 📚 Project Structure

```plaintext
PEDI-ANESTHESIA-BOT/          # ◀︎ 레포 루트
├── KnowledgeBase/            # 의료 지식·용어 등 정적 자원
│   └── Pediatric_Terminology.xls
│
├── src/                      # 파이썬 소스 코드 (import 경로를 src 패키지로 통일)
│   │
│   ├── nodes.py                 # LangGraph 파이프라인 nodes
│   ├── edges.py                 # LangGraph 파이프라인 edges
│   ├── prompt.py                # 시스템·유저 프롬프트 템플릿
│   ├── state.py                 # LangGraph 공유 상태 정의
│   ├── agent.py                 # LLM Agent 호출 
│   ├── utils.py
│   │
│   ├── server/                   # 로컬 MCP Server
│   │   ├── pinecone_server.py     # 소아마취 의료 지식 서버
│   │   ├── vectordb_helper.py     # 소아마취 의료 지식 서버
│   │   ├── neo4j_server.py        # 환자 정보 서버
│   │   └── embedder.py            # neo4j 검색용 임베더
│   │
│   ├── clients/              # MCP 서비스 클라이언트
│   │   └── mcp_client.py          # 최종 사용 가능한 MCP 툴
│   │
│   └── evaluators/           # LLM-as-a-Judge
│       └── query_rewrite_llm_evaluator.py   # Langgraph 흐름안에서 LLM as a Judge 수행
│
├── apps/                     # UI · 인터페이스 계층
│   └── medical_chatbot_app.py     # Streamlit 실행
├── .env                      # 비밀 키·엔드포인트 (gitignore 포함)
├── .gitignore
├── README.md
└── requirements.txt
```
## 🗺️ LangGraph Execution Flow

노드별 상세 설명

1. **router_agent**  
   └─ 질문 의도를 분류해 <br>
   &nbsp;&nbsp;&nbsp;&nbsp;• `vector_db_only` 경로 → ③으로 <br>
   &nbsp;&nbsp;&nbsp;&nbsp;• `sequential` 경로 → ②로

2. **neo4j_db**  
   └─ 환자·수술·약물 그래프 쿼리 실행 → ⑦로 합류

3. **generate_vector_query**  
4. **gpt_query_rewriter**  
5. **vector_retrieval**  
6. **llm_evaluation_node**  
   └─ ③‒⑥ 단계에서 Pinecone 기반 근거 문서 검색·평가

7. **merge_and_respond**  
   └─ 그래프·벡터 결과를 통합해 초안 답변 생성

8. **decision_slack_node**  
   └─ Slack 메시지 쓰레드 관리·버튼 인터랙션 처리

9. **__end__**  
   └─ 최종 응답 반환

## 🤝 Project Structure

이 프로젝트에 기여하고 싶다면, 리포지토리를 포크하고 풀 리퀘스트를 생성하세요.   
버그 또는 기능 요청에 대한 이슈를 열어도 좋습니다.

## 📜 License

이 프로젝트는 MIT 라이선스에 따라 라이선스가 부여됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.
```

이제 이 `README.md` 파일을 프로젝트에 반영할 수 있습니다. 😊
