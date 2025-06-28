import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests
from datetime import datetime
import logging
import re

# Neo4j 관련 import
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️ Neo4j 라이브러리가 설치되지 않았습니다. pip install neo4j")

# Pinecone 관련 import
try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    print("⚠️ Pinecone 라이브러리가 설치되지 않았습니다. pip install pinecone-client")

# OpenAI 임베딩 관련 import
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    try:
        import openai
        OPENAI_AVAILABLE = True
    except ImportError:
        OPENAI_AVAILABLE = False
        print("⚠️ OpenAI 라이브러리가 설치되지 않았습니다.")

# MCP 관련 import
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest,
        ListToolsRequest,
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource,
        LoggingLevel
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️ MCP 라이브러리가 설치되지 않았습니다.")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PatientData:
    """환자 데이터 구조체"""
    patient_id: str
    name: str
    age: int
    gender: str
    diagnosis: str
    treatment_history: str
    current_medications: List[str]
    vital_signs: Dict[str, Any]
    relationships: List[Dict[str, Any]]  # Neo4j 관계 정보

@dataclass
class SearchResult:
    """검색 결과 구조체"""
    content: str
    source: str
    relevance_score: float
    metadata: Dict[str, Any]

class Neo4jPatientDatabase:
    """Neo4j 환자 지식그래프 연결 클래스"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.init_database()
    
    def init_database(self):
        """Neo4j 데이터베이스 초기화 및 샘플 데이터 생성"""
        try:
            with self.driver.session() as session:
                # 기존 데이터 삭제 (테스트용)
                session.run("MATCH (n) DETACH DELETE n")
                
                # 샘플 환자 노드 생성
                self.create_sample_patients(session)
                
                # 관계 생성
                self.create_relationships(session)
                
            print("✅ Neo4j 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"Neo4j 초기화 오류: {e}")
    
    def create_sample_patients(self, session):
        """샘플 환자 노드 생성"""
        patients = [
            {
                'patient_id': 'P001',
                'name': '김철수',
                'age': 45,
                'gender': '남성',
                'diagnosis': '당뇨병 2형',
                'treatment_history': '인슐린 치료 2년간',
                'current_medications': ['메트포르민', '글리메피리드'],
                'vital_signs': {'혈압': '140/90', '혈당': '180', '체중': '75kg'}
            },
            {
                'patient_id': 'P002',
                'name': '이영희',
                'age': 32,
                'gender': '여성',
                'diagnosis': '고혈압',
                'treatment_history': 'ACE 억제제 치료 1년간',
                'current_medications': ['리시노프릴'],
                'vital_signs': {'혈압': '135/85', '혈당': '95', '체중': '58kg'}
            },
            {
                'patient_id': 'P003',
                'name': '박민수',
                'age': 28,
                'gender': '남성',
                'diagnosis': '천식',
                'treatment_history': '흡입기 치료 3년간',
                'current_medications': ['살부타몰', '부데소니드'],
                'vital_signs': {'혈압': '120/80', '혈당': '90', '체중': '70kg'}
            }
        ]
        
        for patient in patients:
            session.run("""
                CREATE (p:Patient {
                    patient_id: $patient_id,
                    name: $name,
                    age: $age,
                    gender: $gender,
                    diagnosis: $diagnosis,
                    treatment_history: $treatment_history,
                    current_medications: $current_medications,
                    vital_signs: $vital_signs
                })
            """, patient)
    
    def create_relationships(self, session):
        """환자와 의료 정보 간의 관계 생성"""
        # 진단 관계
        session.run("""
            MATCH (p:Patient {patient_id: 'P001'})
            CREATE (d:Diagnosis {name: '당뇨병 2형', category: '내분비질환'})
            CREATE (p)-[:HAS_DIAGNOSIS]->(d)
        """)
        
        session.run("""
            MATCH (p:Patient {patient_id: 'P002'})
            CREATE (d:Diagnosis {name: '고혈압', category: '심혈관질환'})
            CREATE (p)-[:HAS_DIAGNOSIS]->(d)
        """)
        
        session.run("""
            MATCH (p:Patient {patient_id: 'P003'})
            CREATE (d:Diagnosis {name: '천식', category: '호흡기질환'})
            CREATE (p)-[:HAS_DIAGNOSIS]->(d)
        """)
        
        # 약물 관계
        session.run("""
            MATCH (p:Patient {patient_id: 'P001'})
            CREATE (m:Medication {name: '메트포르민', type: '혈당강하제'})
            CREATE (p)-[:TAKES_MEDICATION]->(m)
        """)
        
        session.run("""
            MATCH (p:Patient {patient_id: 'P002'})
            CREATE (m:Medication {name: '리시노프릴', type: 'ACE억제제'})
            CREATE (p)-[:TAKES_MEDICATION]->(m)
        """)
    
    def get_patient_by_id(self, patient_id: str) -> Optional[PatientData]:
        """환자 ID로 환자 정보 조회"""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (p:Patient {patient_id: $patient_id})
                    OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
                    OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
                    RETURN p, collect(d) as diagnoses, collect(m) as medications
                """, patient_id=patient_id)
                
                record = result.single()
                if record:
                    patient_node = record["p"]
                    return PatientData(
                        patient_id=patient_node["patient_id"],
                        name=patient_node["name"],
                        age=patient_node["age"],
                        gender=patient_node["gender"],
                        diagnosis=patient_node["diagnosis"],
                        treatment_history=patient_node["treatment_history"],
                        current_medications=patient_node["current_medications"],
                        vital_signs=patient_node["vital_signs"],
                        relationships={
                            "diagnoses": [dict(d) for d in record["diagnoses"]],
                            "medications": [dict(m) for m in record["medications"]]
                        }
                    )
                return None
                
        except Exception as e:
            logger.error(f"환자 정보 조회 오류: {e}")
            return None
    
    def search_patients(self, query: str) -> List[PatientData]:
        """환자 검색 (이름, 진단명 등으로)"""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (p:Patient)
                    WHERE p.name CONTAINS $query 
                    OR p.diagnosis CONTAINS $query
                    OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
                    OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
                    RETURN p, collect(d) as diagnoses, collect(m) as medications
                """, query=query)
                
                patients = []
                for record in result:
                    patient_node = record["p"]
                    patients.append(PatientData(
                        patient_id=patient_node["patient_id"],
                        name=patient_node["name"],
                        age=patient_node["age"],
                        gender=patient_node["gender"],
                        diagnosis=patient_node["diagnosis"],
                        treatment_history=patient_node["treatment_history"],
                        current_medications=patient_node["current_medications"],
                        vital_signs=patient_node["vital_signs"],
                        relationships={
                            "diagnoses": [dict(d) for d in record["diagnoses"]],
                            "medications": [dict(m) for m in record["medications"]]
                        }
                    ))
                return patients
                
        except Exception as e:
            logger.error(f"환자 검색 오류: {e}")
            return []
    
    def get_patient_relationships(self, patient_id: str) -> Dict[str, Any]:
        """환자의 관계 정보 조회"""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (p:Patient {patient_id: $patient_id})-[r]-(related)
                    RETURN type(r) as relationship_type, related
                """, patient_id=patient_id)
                
                relationships = {}
                for record in result:
                    rel_type = record["relationship_type"]
                    related_node = record["related"]
                    
                    if rel_type not in relationships:
                        relationships[rel_type] = []
                    relationships[rel_type].append(dict(related_node))
                
                return relationships
                
        except Exception as e:
            logger.error(f"관계 정보 조회 오류: {e}")
            return {}

class PineconeRAGSearch:
    """Pinecone RAG 검색 클래스"""
    
    def __init__(self, api_key: str, environment: str, index_name: str):
        pinecone.init(api_key=api_key, environment=environment)
        self.index = pinecone.Index(index_name)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def embed_text(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {e}")
            return []
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Pinecone에서 유사한 문서 검색"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embed_text(query)
            if not query_embedding:
                return []
            
            # Pinecone 검색
            search_results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            results = []
            for match in search_results.matches:
                results.append(SearchResult(
                    content=match.metadata.get('content', ''),
                    source=match.metadata.get('source', ''),
                    relevance_score=match.score,
                    metadata=match.metadata
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Pinecone 검색 오류: {e}")
            return []
    
    def add_document(self, content: str, source: str, metadata: Dict[str, Any] = None):
        """문서를 Pinecone에 추가"""
        try:
            embedding = self.embed_text(content)
            if not embedding:
                return False
            
            # 메타데이터 준비
            doc_metadata = {
                'content': content,
                'source': source,
                'timestamp': datetime.now().isoformat()
            }
            if metadata:
                doc_metadata.update(metadata)
            
            # Pinecone에 업로드
            self.index.upsert(
                vectors=[{
                    'id': f"doc_{source}_{datetime.now().timestamp()}",
                    'values': embedding,
                    'metadata': doc_metadata
                }]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"문서 추가 오류: {e}")
            return False

class SlackMessenger:
    """Slack 메시지 전송 클래스"""
    
    def __init__(self, webhook_url: str = None, channel: str = "#general"):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.channel = channel
    
    def send_message(self, message: str, patient_info: str = "") -> bool:
        """Slack으로 메시지 전송"""
        if not self.webhook_url:
            logger.warning("Slack webhook URL이 설정되지 않았습니다.")
            return False
        
        try:
            payload = {
                "channel": self.channel,
                "text": f"🏥 의료 상담 결과\n\n{message}\n\n{patient_info}",
                "username": "의료 AI 어시스턴트",
                "icon_emoji": ":hospital:"
            }
            
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Slack 메시지 전송 성공")
            return True
            
        except Exception as e:
            logger.error(f"Slack 메시지 전송 실패: {e}")
            return False

class MedicalMCPServer:
    """의료 MCP 서버 클래스"""
    
    def __init__(self):
        # Neo4j 
        self.patient_db = Neo4jPatientDatabase(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        
        # Pinecone 연결
        self.rag_search = PineconeRAGSearch(
            api_key=os.getenv("PINECONE_API_KEY"),
            environment=os.getenv("PINECONE_ENVIRONMENT"),
            index_name=os.getenv("PINECONE_INDEX_NAME", "medical-knowledge")
        )
        
        # Slack 연결
        self.slack_messenger = SlackMessenger()
        
        # MCP 서버 설정
        if MCP_AVAILABLE:
            self.server = Server("medical-assistant")
            self.register_tools()
    
    def register_tools(self):
        """MCP 도구들 등록"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                Tool(
                    name="search_patient",
                    description="Neo4j에서 환자 ID나 이름으로 환자 정보를 검색합니다.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "검색할 환자 ID 또는 이름"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="search_medical_knowledge",
                    description="Pinecone에서 의료 지식 베이스를 검색합니다.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "검색할 의료 질문"
                            },
                            "patient_context": {
                                "type": "string",
                                "description": "환자 컨텍스트 정보"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_patient_relationships",
                    description="Neo4j에서 환자의 관계 정보를 조회합니다.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "patient_id": {
                                "type": "string",
                                "description": "환자 ID"
                            }
                        },
                        "required": ["patient_id"]
                    }
                ),
                Tool(
                    name="send_slack_message",
                    description="Slack으로 메시지를 전송합니다.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "전송할 메시지"
                            },
                            "patient_info": {
                                "type": "string",
                                "description": "환자 정보"
                            }
                        },
                        "required": ["message"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            if name == "search_patient":
                query = arguments.get("query", "")
                patients = self.patient_db.search_patients(query)
                
                if patients:
                    result = "환자 정보:\n"
                    for patient in patients:
                        result += f"- ID: {patient.patient_id}, 이름: {patient.name}, 진단: {patient.diagnosis}\n"
                else:
                    result = "해당하는 환자 정보를 찾을 수 없습니다."
                
                return [TextContent(type="text", text=result)]
            
            elif name == "search_medical_knowledge":
                query = arguments.get("query", "")
                patient_context = arguments.get("patient_context", "")
                
                enhanced_query = f"{query} {patient_context}"
                results = self.rag_search.search(enhanced_query)
                
                if results:
                    result = "의료 지식 검색 결과:\n"
                    for i, search_result in enumerate(results, 1):
                        result += f"{i}. {search_result.content}\n"
                        result += f"   출처: {search_result.source} (관련성: {search_result.relevance_score:.3f})\n\n"
                else:
                    result = "관련 의료 정보를 찾을 수 없습니다."
                
                return [TextContent(type="text", text=result)]
            
            elif name == "get_patient_relationships":
                patient_id = arguments.get("patient_id", "")
                relationships = self.patient_db.get_patient_relationships(patient_id)
                
                if relationships:
                    result = f"환자 {patient_id}의 관계 정보:\n"
                    for rel_type, related_nodes in relationships.items():
                        result += f"- {rel_type}:\n"
                        for node in related_nodes:
                            result += f"  * {node}\n"
                else:
                    result = "관계 정보를 찾을 수 없습니다."
                
                return [TextContent(type="text", text=result)]
            
            elif name == "send_slack_message":
                message = arguments.get("message", "")
                patient_info = arguments.get("patient_info", "")
                
                success = self.slack_messenger.send_message(message, patient_info)
                
                if success:
                    result = "Slack 메시지가 성공적으로 전송되었습니다."
                else:
                    result = "Slack 메시지 전송에 실패했습니다."
                
                return [TextContent(type="text", text=result)]
            
            else:
                return [TextContent(type="text", text=f"알 수 없는 도구: {name}")]

class MedicalAssistant:
    """의료 어시스턴트 메인 클래스"""
    
    def __init__(self):
        self.mcp_server = MedicalMCPServer()
        self.patient_db = self.mcp_server.patient_db
        self.rag_search = self.mcp_server.rag_search
        self.slack_messenger = self.mcp_server.slack_messenger
    
    async def process_user_query(self, user_query: str) -> str:
        """사용자 질문 처리"""
        logger.info(f"사용자 질문: {user_query}")
        
        # 1. 환자 정보 추출 및 검색
        patient_info = self.extract_patient_info(user_query)
        
        # 2. 질문 재생성
        enhanced_query = self.enhance_query(user_query, patient_info)
        
        # 3. Pinecone RAG 검색 수행
        search_results = self.rag_search.search(enhanced_query)
        
        # 4. 답변 생성
        answer = self.generate_answer(user_query, patient_info, search_results)
        
        # 5. Slack 전송 요청 확인
        if "slack" in user_query.lower() or "보내줘" in user_query:
            self.slack_messenger.send_message(answer, str(patient_info))
            answer += "\n\n✅ Slack으로 메시지를 전송했습니다."
        
        return answer
    
    def extract_patient_info(self, query: str) -> Optional[PatientData]:
        """질문에서 환자 정보 추출"""
        # 환자 ID 패턴 매칭 (P001, P002 등)
        patient_id_match = re.search(r'P\d{3}', query)
        if patient_id_match:
            patient_id = patient_id_match.group()
            return self.patient_db.get_patient_by_id(patient_id)
        
        # 이름 기반 검색
        name_keywords = ['김철수', '이영희', '박민수', '철수', '영희', '민수']
        for name in name_keywords:
            if name in query:
                patients = self.patient_db.search_patients(name)
                if patients:
                    return patients[0]
        
        return None
    
    def enhance_query(self, original_query: str, patient_info: Optional[PatientData]) -> str:
        """환자 정보를 바탕으로 질문 강화"""
        if patient_info:
            enhanced = f"{original_query} [환자: {patient_info.name}, {patient_info.age}세, {patient_info.gender}, 진단: {patient_info.diagnosis}]"
        else:
            enhanced = original_query
        
        return enhanced
    
    def generate_answer(self, original_query: str, patient_info: Optional[PatientData], search_results: List[SearchResult]) -> str:
        """검색 결과를 바탕으로 답변 생성"""
        answer = f"질문: {original_query}\n\n"
        
        if patient_info:
            answer += f"환자 정보:\n"
            answer += f"- 이름: {patient_info.name}\n"
            answer += f"- 나이: {patient_info.age}세\n"
            answer += f"- 성별: {patient_info.gender}\n"
            answer += f"- 진단: {patient_info.diagnosis}\n"
            answer += f"- 현재 복용 약물: {', '.join(patient_info.current_medications)}\n\n"
            
            # Neo4j 관계 정보 추가
            if patient_info.relationships:
                answer += "관계 정보:\n"
                for rel_type, items in patient_info.relationships.items():
                    answer += f"- {rel_type}: {len(items)}개\n"
                answer += "\n"
        
        if search_results:
            answer += "의료 정보 (Pinecone 검색 결과):\n"
            for i, result in enumerate(search_results[:3], 1):  # 상위 3개 결과만
                answer += f"{i}. {result.content}\n"
                answer += f"   (출처: {result.source}, 관련성: {result.relevance_score:.3f})\n\n"
        else:
            answer += "관련 의료 정보를 찾을 수 없습니다.\n\n"
        
        answer += "추가 질문이나 Slack 전송 요청이 있으시면 말씀해 주세요."
        
        return answer

async def main():
    """메인 실행 함수"""
    assistant = MedicalAssistant()
    
    print("🏥 Neo4j + Pinecone 의료 AI 어시스턴트가 시작되었습니다!")
    print("사용 예시:")
    print("- 'P001 환자의 당뇨병 치료에 대해 알려줘'")
    print("- '이영희 환자의 고혈압 관리 방법을 slack으로 보내줘'")
    print("- '종료'를 입력하면 프로그램이 종료됩니다.\n")
    
    while True:
        try:
            user_input = input("질문을 입력하세요: ").strip()
            
            if user_input.lower() in ['종료', 'exit', 'quit']:
                print("프로그램을 종료합니다.")
                break
            
            if not user_input:
                continue
            
            # 비동기로 질문 처리
            answer = await assistant.process_user_query(user_input)
            print(f"\n답변:\n{answer}\n")
            
        except KeyboardInterrupt:
            print("\n프로그램을 종료합니다.")
            break
        except Exception as e:
            logger.error(f"오류 발생: {e}")
            print(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    # 환경 변수 설정 (실제 사용시 설정 필요)
    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USER", "neo4j")
    os.environ.setdefault("NEO4J_PASSWORD", "password")
    os.environ.setdefault("PINECONE_API_KEY", "your_pinecone_api_key")
    os.environ.setdefault("PINECONE_ENVIRONMENT", "your_pinecone_environment")
    os.environ.setdefault("PINECONE_INDEX_NAME", "medical-knowledge")
    os.environ.setdefault("OPENAI_API_KEY", "your_openai_api_key")
    os.environ.setdefault("SLACK_WEBHOOK_URL", "your_slack_webhook_url")
    
    # 비동기 실행
    asyncio.run(main()) 