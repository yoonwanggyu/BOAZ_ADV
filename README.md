![header](https://capsule-render.vercel.app/api?type=Waving&color=auto&height=300&fontAlignY=50&fontAlign=50&section=header&text=땡큐소아마취&fontSize=50)
<div align=center>

LangGraph 기반 파이프라인과 MCP(Model Context Protocol) 인프라 위에 구축된 **소아마취 도메인 특화 AI 챗봇**입니다.  
Pinecone DB(의료 지식)와 Neo4j DB(환자·수술 기록)를 양방향으로 조회하고, Slack 워크스페이스와 실시간으로 연동되어 병원 내 의료진이 **정보를 즉시 공유**할 수 있습니다.
</div>

## 🏥 Clinical Collaboration

This project was developed **in partnership with the Bio-Medical Informatics (BMI) Lab, 
Seoul National University Hospital(서울대학교병원 의생명정보학 연구실)**

> Special thanks to the lab members for providing domain expertise, sample datasets, and continuous feedback throughout development.

## 🗓️ Timeline
2025.02 ~ 2025.08


## 👪 Team
<p align="center">
  <img src="pictures/9FCCE7B8-6EC3-406D-8927-5A748828A52B.jpeg" alt="LangGraph flowchart" width="600"/>
</p>

**이재원** ([Jaewon1634](https://github.com/Jaewon1634)) · **백지연** ([wlsisl](https://github.com/wlsisl)) · **백다은** ([nuebaek](https://github.com/nuebaek)) · **박혜원** ([nowhye](https://github.com/nowhye)) · **윤왕규** ([yoonwanggyu](https://github.com/yoonwanggyu)) 
> 📝 This project was carried out by the 23rd cohort of the **BOAZ**.


## 📚 Project Structure

```plaintext
📂 (작업 중인 폴더)            # ◀︎ Git 레포 루트 디렉토리
├── main.py                  # LangGraph 실행 진입점 (백엔드 플로우 테스트용)
├── app.py                   # Streamlit 기반 챗봇 UI 실행 파일
├── .env                     # 비밀 키, API 토큰 등 환경 설정 (gitignore에 포함)
├── requirements.txt         # 프로젝트 실행에 필요한 패키지 목록
├── README.md                # 프로젝트 소개 문서
│
├── pictures/                # 프로젝트 설명용 이미지
│   ├── 0008D232-...jpeg
│   └── 9FCCE7B8-...jpeg
│
├── src/                     # 주요 파이썬 소스 코드 디렉토리 (패키지화 가능)
│   │
│   ├── agent.py             # LangGraph에서 사용할 LLM Agent 정의
│   ├── mcp_client.py        # MCP(Multi-Component Protocol) 클라이언트 정의
│   ├── prompt.py            # 프롬프트 템플릿 및 역할별 시스템 메시지 정의
│   │
│   ├── else/                # 기타 자원 및 파일 보관 디렉토리
│   │   ├── Pediatric_Terminology.xls  # 소아 마취 용어 및 분류 파일
│   │   └── image.png                  # Streamlit용 이미지
│   │
│   ├── evaluator/          # 평가 노드 로직 (LLM-as-a-Judge)
│   │   └── query_rewrite_llm_evaluator.py   # 쿼리 재작성 평가를 위한 LLM 평가자
│   │
│   ├── langgraph/          # LangGraph 파이프라인 구성 모듈
│   │   ├── edge.py         # 노드 간 흐름 제어 (조건 분기 등)
│   │   ├── nodes.py        # LangGraph에서 실행되는 주요 기능 노드들
│   │   └── state.py        # 그래프 전반에서 공유되는 상태(State) 정의
│   │
│   └── server/             # MCP 서버 모듈
│       ├── embedder.py         # 벡터 검색용 텍스트 임베딩 생성기
│       ├── neo4j_server.py     # 환자 그래프 데이터 검색기 (Neo4j)
│       └── pinecone_server.py  # 지식 기반 문서 검색기 (Pinecone)
```
## 🗺️ LangGraph Execution Flow
<p align="center">
  <img src="pictures/0008D232-381E-4FAB-99F0-900B1D7CBC42.jpeg" alt="LangGraph flowchart" width="600"/>
</p>


<details>
<summary>Node-by-node details (click to expand)</summary>

1. **router_agent**  
   └─ Classifies intent →  
   &nbsp;&nbsp;&nbsp;&nbsp;• `vector_db_only` → ③  
   &nbsp;&nbsp;&nbsp;&nbsp;• `sequential` → ②  

2. **neo4j_db**  
   └─ Queries patient / surgery / drug graph → joins at ⑦  

3. **generate_vector_query**  
4. **gpt_query_rewriter**  
5. **vector_retrieval**  
6. **llm_evaluation_node**  
   └─ Steps ③–⑥: Pinecone doc search & evaluation  

7. **merge_and_respond**  
   └─ Merges graph + vector answers  

8. **decision_slack_node**  
   └─ Manages Slack thread & interactions  

9. **__end__**  
   └─ Returns final reply  

</details>

## 🤝 Project Structure

이 프로젝트에 기여하고 싶다면, 리포지토리를 포크하고 풀 리퀘스트를 생성하세요.   
버그 또는 기능 요청에 대한 이슈를 열어도 좋습니다.

## 📜 License

이 프로젝트는 MIT 라이선스에 따라 라이선스가 부여됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.
```

이제 이 `README.md` 파일을 프로젝트에 반영할 수 있습니다. 😊
