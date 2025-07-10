import sys
sys.path.append('jiyeon/mcp')  # 또는 'Wang_Gyu/code/mcp' 등 실제 경로

from typing import Annotated, List, TypedDict, Optional
from langgraph.graph.message import add_messages
from langchain_community.document_transformers import LongContextReorder
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from langchain_mcp_adapters.client import MultiServerMCPClient
from openai import OpenAI
import asyncio
import json
import os
import re

load_dotenv()


class ChatbotConfig:
    """챗봇 설정을 관리하는 클래스"""
    def __init__(self, config_file: str = "chatbot_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        default_config = {
            "model": {
                "name": "gpt-4o",
                "temperature": 0.2
            },
            "mcp_servers": {
                "neo4j_retriever": {
                    "command": "python",  # Windows에서는 python으로 변경
                    "args": ["mcp_neo4j_server.py"],
                    "transport": "stdio",
                },
                "VectorDB_retriever": {
                    "command": "python",  # Windows에서는 python으로 변경
                    "args": ["mcp_vectordb_server.py"],
                    "transport": "stdio",
                }
            },
            "slack": {
                "enabled": True,
                "token": os.getenv("SLACK_BOT_TOKEN", ""),
                "channel": os.getenv("SLACK_CHANNEL", ""),
                "user_mapping": {
                    "백지연": "U093ELJBE3X",  # 실제 Slack 사용자 ID로 변경 필요
                    #"김철수": "U0987654321",
                    #"이영희": "U1122334455"
                }
            },
            "use_dummy_tools": False,  # 실제 MCP 서버 사용
            "memory_enabled": True
        }
        
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return {**default_config, **json.load(f)}
        else:
            # 기본 설정 파일 생성
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config

# 설정 로드
config = ChatbotConfig()

#OpenAI API 키를 기반으로 클라이언트 생성
model_client = OpenAI()

#챗봇 상태정의
#LangGraph에서 사용될 상태 객체
#챗봇 흐름 중 주고받는 데이터 구조 정의
class ChatbotState(TypedDict):
    question: Annotated[str, "Question"]   #사용자 질문
    tools: Annotated[List, "Tools"] #사용할 도구
    neo4j_documents: Annotated[List, "Neo4j_Documents"] #	Neo4j 리트리버가 가져온 결과 
    vector_documents : Annotated[List,"Vector_Documents"] #VectorDB 리트리버가 가져온 결과
    final_answer: Annotated[str, "Final_Answer"] #최종응답
    messages: Annotated[List, add_messages] #전체 대화 메시지 기록록
    slack_recipient: Annotated[Optional[str], "Slack_Recipient"] #Slack 수신자
    slack_message: Annotated[Optional[str], "Slack_Message"] #Slack 메시지

#메모리 저장소 정의 
memory = MemorySaver() if config.config["memory_enabled"] else None

# Slack 연동 클래스
class SlackNotifier:
    """Slack 메시지 전송 클래스"""
    
    def __init__(self, token: str, channel: str, user_mapping: dict):
        self.token = token
        self.channel = channel
        self.user_mapping = user_mapping
        self.enabled = bool(token)
    
    async def send_message(self, recipient: str, message: str) -> str:
        """Slack으로 메시지 전송"""
        if not self.enabled:
            return f"[Slack 비활성화] {recipient}에게 전송할 메시지: {message}"
        
        try:
            import requests
            
            # Slack 사용자 ID 찾기
            user_id = self.user_mapping.get(recipient)
            if not user_id:
                return f"오류: '{recipient}' 사용자를 찾을 수 없습니다. (매핑된 사용자: {list(self.user_mapping.keys())})"
            
            print(f"Slack API 호출 중...")
            print(f"Token: {self.token[:10]}..." if self.token else "Token 없음")
            print(f"User ID: {user_id}")
            print(f"Message: {message[:50]}...")
            
            # 방법 1: 채널에 멘션으로 메시지 전송 (가장 간단)
            mention_message = f"<@{user_id}> {message}"
            
            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "channel": self.channel,  # 일반 채널에 전송
                    "text": mention_message,
                    "username": "ThankYouBot"
                }
            )
            
            print(f"Slack API 응답: {response.status_code}")
            print(f"응답 내용: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return f"✅ Slack 메시지 전송 완료!\n수신자: {recipient} (채널: {self.channel})\n메시지: {message[:100]}..."
                else:
                    error_msg = result.get('error', '알 수 없는 오류')
                    if error_msg == "missing_scope":
                        return f"❌ Slack 권한 부족: Bot Token에 'chat:write' 권한이 필요합니다."
                    elif error_msg == "channel_not_found":
                        return f"❌ 채널을 찾을 수 없음: '{self.channel}' 채널이 존재하지 않습니다."
                    else:
                        return f"❌ Slack API 오류: {error_msg}"
            else:
                return f"❌ HTTP 오류: {response.status_code} - {response.text}"
            
        except Exception as e:
            return f"Slack 메시지 전송 실패: {e}"

# Slack 노티파이어 초기화
slack_notifier = SlackNotifier(
    token=config.config["slack"]["token"],
    channel=config.config["slack"]["channel"],
    user_mapping=config.config["slack"]["user_mapping"]
)

# MCP 클라이언트 설정
async def setup_mcp_client():
    """MCP 클라이언트 설정 및 도구 가져오기"""
    try:
        # MCP 클라이언트 생성
        client = MultiServerMCPClient(
            {
                "neo4j_retriever": {
                    "command": config.config["mcp_servers"]["neo4j_retriever"]["command"],
                    "args": config.config["mcp_servers"]["neo4j_retriever"]["args"],
                    "transport": config.config["mcp_servers"]["neo4j_retriever"]["transport"],
                },
                "VectorDB_retriever": {
                    "command": config.config["mcp_servers"]["VectorDB_retriever"]["command"],
                    "args": config.config["mcp_servers"]["VectorDB_retriever"]["args"],
                    "transport": config.config["mcp_servers"]["VectorDB_retriever"]["transport"],
                }
            }
        )
        
        # MCP에서 사용할 도구 정보 받아오기
        tools = await client.get_tools()
        
        # 도구 이름 -> 객체 매핑
        tools_dict = {tool.name: tool for tool in tools}
        tools_dict["slack_sender"] = SlackTool(slack_notifier)
        
        print(f"MCP 클라이언트 설정 완료. 사용 가능한 도구: {list(tools_dict.keys())}")
        
        return client, tools, tools_dict
        
    except Exception as e:
        print(f"MCP 클라이언트 설정 실패: {e}")
        print("더미 도구로 대체합니다.")
        return None, [], {}

# 도구 정의 - MCP 대신 직접 정의 (백업용)
backup_tools = [
    {
        "type": "function",
        "function": {
            "name": "neo4j_retriever",
            "description": "Neo4j 데이터베이스에서 환자 관련 정보를 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 질문"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "VectorDB_retriever",
            "description": "VectorDB에서 의학 지식을 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 질문"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# 도구 이름 -> 객체 매핑
class DummyTool:
    """더미 도구 - 실제 서버 연결 전까지 사용"""
    def __init__(self, name):
        self.name = name
    
    async def ainvoke(self, params):
        return f"Dummy result for {self.name} with query: {params.get('query', '')}"

class SlackTool:
    """Slack 메시지 전송 도구"""
    def __init__(self, notifier: SlackNotifier):
        self.notifier = notifier
    
    async def ainvoke(self, params):
        recipient = params.get("recipient", "")
        message = params.get("message", "")
        return await self.notifier.send_message(recipient, message)

# 전역 변수 초기화
mcp_client = None
tools = backup_tools
tools_dict = {
    "neo4j_retriever": DummyTool("neo4j_retriever"),
    "VectorDB_retriever": DummyTool("VectorDB_retriever"),
    "slack_sender": SlackTool(slack_notifier)
}

async def initialize_mcp():
    """MCP 초기화"""
    global mcp_client, tools, tools_dict
    
    if not config.config["use_dummy_tools"]:
        mcp_client, mcp_tools, mcp_tools_dict = await setup_mcp_client()
        
        if mcp_client and mcp_tools:
            tools = mcp_tools
            tools_dict = mcp_tools_dict
            # Slack 도구 추가
            tools_dict["slack_sender"] = SlackTool(slack_notifier)
            print("MCP 도구 사용 중")
        else:
            print("MCP 연결 실패, 더미 도구 사용")
            # 더미 도구로 초기화
            tools = backup_tools
            tools_dict = {
                "neo4j_retriever": DummyTool("neo4j_retriever"),
                "VectorDB_retriever": DummyTool("VectorDB_retriever"),
                "slack_sender": SlackTool(slack_notifier)
            }
    else:
        print("설정에 따라 더미 도구 사용")
        # 더미 도구로 초기화
        tools = backup_tools
        tools_dict = {
            "neo4j_retriever": DummyTool("neo4j_retriever"),
            "VectorDB_retriever": DummyTool("VectorDB_retriever"),
            "slack_sender": SlackTool(slack_notifier)
        }

    print("Available tools:", list(tools_dict.keys()))
    print("Using dummy tools:", config.config["use_dummy_tools"])

#프롬프트 입력. 
LLM_SYSTEM_PROMPTY = """
# INSTRUCTION
당신은 의료 데이터에 특화된 전문가 AI입니다.
사용자의 질문에 대해 다음 두 가지 출처의 정보를 참고하여 답변을 생성하세요:

1. 🔎 Neo4j 검색 결과: 구조화된 환자 관련 정보 (예: 수술 이력, 검사 기록 등)
2. 📚 VectorDB 검색 결과: 일반적인 의학 지식 (예: 증상 설명, 치료 가이드라인 등)

- 두 결과 모두 존재할 경우, 각 출처를 구분하여 통합적으로 반영하되, 중복 내용은 요약하거나 통합하세요.
- 한 쪽의 결과만 존재할 경우, 해당 결과만을 바탕으로 답변하되, 정보의 한계에 대해 언급하지 말고 최대한 성실히 답변하세요.
- 결과가 너무 적거나 애매하더라도 반드시 유의미한 설명을 제공하려고 노력하세요.
- 불필요한 서론 없이, 질문에 바로 답변하세요.

# Neo4j CONTEXT
{Neo4j}

# Vector DB CONTEXT
{VectorDB}

# Question
{question}
"""

model = ChatOpenAI(
    temperature=config.config["model"]["temperature"],
    model_name=config.config["model"]["name"]
)

def extract_slack_info(question: str) -> tuple:
    """질문에서 Slack 전송 정보 추출"""
    # 간단한 패턴: "~에게"와 "전달해줘"가 포함되어 있으면 Slack 전송
    recipient_pattern = r'(.+?)에게'
    delivery_pattern = r'전달해줘'
    
    # 수신자와 전달 키워드가 모두 있는지 확인
    recipient_match = re.search(recipient_pattern, question)
    delivery_match = re.search(delivery_pattern, question)
    
    if recipient_match and delivery_match:
        recipient = recipient_match.group(1).strip()
        
        # "~에게"와 "전달해줘" 부분을 제거하여 의료 질문 추출
        # "백지연에게 3세는 마취를 조심해야하는 이유를 검색해서 전달해줘" 
        # → "3세는 마취를 조심해야하는 이유를 검색해서"
        clean_question = question.replace(f"{recipient}에게", "").replace("전달해줘", "").strip()
        
        # 앞뒤 공백과 불필요한 조사 제거
        clean_question = re.sub(r'^\s*[을를]\s*', '', clean_question)  # 앞의 "을/를" 제거
        clean_question = re.sub(r'\s*[을를]\s*$', '', clean_question)  # 뒤의 "을/를" 제거
        clean_question = clean_question.strip()
        
        print(f"🔍 Slack 전송 감지: 수신자={recipient}, 질문={clean_question}")
        return recipient, clean_question
    
    return None, question

async def decision_tools(state: ChatbotState):
    
    question = state["question"]
    
    # Slack 전송 정보 추출
    recipient, clean_question = extract_slack_info(question)
    
    # 도구 선택 로직
    selected_tools = []
    
    # 1. Slack 전송 요청이 있으면 slack_sender 추가
    if recipient:
        selected_tools.append("slack_sender")
        print(f"🔍 Slack 전송 요청 감지: {recipient}에게 전송")
        # 원본 질문을 정리된 질문으로 업데이트
        question = clean_question
    
    # 2. 의료 질문에 대한 도구 선택
    if clean_question and clean_question.strip():
        if config.config["use_dummy_tools"]:
            # 더미 도구 사용 시: 키워드 기반 선택
            medical_keywords = [
                '증상', '치료', '약물', '수술', '검사', '진단', '병', '질환', '마취', 
                '심장', '뇌', '폐', '간', '신장', '혈액', '감염', '염증', '통증',
                '소아', '성인', '노인', '응급', '중환자', '재활', '예방'
            ]
            
            patient_keywords = [
                '환자', '환자정보', '환자기록', '환자이력', '환자데이터', '환자상태',
                '수술이력', '검사기록', '진료기록', '입원', '퇴원', '복용약물'
            ]
            
            has_medical_content = any(keyword in clean_question for keyword in medical_keywords)
            has_patient_content = any(keyword in clean_question for keyword in patient_keywords)
            
            if has_medical_content:
                selected_tools.append("VectorDB_retriever")
                print(f"🔍 의료 질문 감지: VectorDB 검색")
                
                if has_patient_content:
                    selected_tools.append("neo4j_retriever")
                    print(f"🔍 환자 정보 감지: Neo4j 검색 추가")
            else:
                selected_tools.append("VectorDB_retriever")
                print(f"🔍 일반 질문 감지: VectorDB 검색")
        else:
            # MCP 사용 시: LLM이 자동으로 도구 선택
            input_messages = [
                {"role": "system", "content": "Decide which tools to use to answer the user's question. You may call one or both."},
                {"role": "user", "content": clean_question}
            ]
            
            response = model_client.chat.completions.create(
                model=config.config["model"]["name"],
                messages=input_messages,
                tools=tools
            )

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    tool_name = tool_call.function.name
                    if tool_name not in selected_tools:
                        selected_tools.append(tool_name)
                        print(f"🤖 LLM이 자동으로 도구 선택: {tool_name}")
    
    # 3. 도구가 선택되지 않았으면 기본적으로 VectorDB 선택
    if not selected_tools or (len(selected_tools) == 1 and selected_tools[0] == "slack_sender"):
        selected_tools.append("VectorDB_retriever")
        print(f"🔍 기본 도구 선택: VectorDB 검색")
    
    print(f"📋 선택된 도구: {selected_tools}")
    
    return ChatbotState(
        tools=selected_tools,
        slack_recipient=recipient,
        question=clean_question if recipient else question
    )

async def vector_db(state: ChatbotState):
    question = state["question"]
    neo4j_documents = state.get("neo4j_documents", [])
    
    if "VectorDB_retriever" in state["tools"]:
        vectordb_tool = tools_dict.get("VectorDB_retriever")
        
        if vectordb_tool:
            try:
                # Neo4j에서 환자 정보가 있으면 검색 쿼리에 포함
                if neo4j_documents and neo4j_documents != "Neo4j 도구를 찾을 수 없습니다.":
                    enhanced_query = f"환자 정보: {neo4j_documents}\n\n질문: {question}"
                    print(f"🔍 VectorDB 검색 (환자 정보 포함): {enhanced_query[:100]}...")
                else:
                    enhanced_query = question
                    print(f"🔍 VectorDB 검색: {question}")
                
                result = await vectordb_tool.ainvoke({"query": enhanced_query})
            except Exception as e:
                result = f"VectorDB 도구 실행 오류: {e}"
        else:
            result = "VectorDB 도구를 찾을 수 없습니다."
    else:
        result = None

    return ChatbotState(vector_documents=result)

async def neo4j_db(state: ChatbotState):
    question = state["question"]
    
    if "neo4j_retriever" in state["tools"]:
        neo4j_tool = tools_dict.get("neo4j_retriever")
        if neo4j_tool:
            try:
                result = await neo4j_tool.ainvoke({"query": question})
            except Exception as e:
                result = f"Neo4j 도구 실행 오류: {e}"
        else:
            result = "Neo4j 도구를 찾을 수 없습니다."
    else:
        result = None

    return ChatbotState(neo4j_documents=result)

async def slack_send(state: ChatbotState):
    """Slack 메시지 전송"""
    recipient = state.get("slack_recipient")
    final_answer = state.get("final_answer", "")
    
    if recipient and final_answer:
        slack_tool = tools_dict.get("slack_sender")
        if slack_tool:
            try:
                result = await slack_tool.ainvoke({
                    "recipient": recipient,
                    "message": final_answer
                })
            except Exception as e:
                result = f"Slack 전송 오류: {e}"
        else:
            result = "Slack 도구를 찾을 수 없습니다."
    else:
        result = None
    
    return ChatbotState(slack_message=result)

async def merge_outputs(state:ChatbotState):

    question = state['question']
    vector_documents = state['vector_documents']
    neo4j_documents = state['neo4j_documents']

    formatted = LLM_SYSTEM_PROMPTY.format(Neo4j = neo4j_documents,
                                          VectorDB = vector_documents,
                                          question = question)
    response = model.invoke(formatted)
    response_text = response.content if isinstance(response, AIMessage) else str(response)

    return ChatbotState(final_answer=response_text,
                        messages=[("user", question), ("assistant", response_text)])

class MedicalChatbot:
    """의료 챗봇 클래스"""
    
    def __init__(self):
        self.builder = StateGraph(ChatbotState)
        self.setup_graph()
        self.graph = self.builder.compile(checkpointer=memory)
        self.config = RunnableConfig(configurable={"thread_id": 1})
    
    def setup_graph(self):
        """그래프 설정"""
        self.builder.add_node("decision_tools", decision_tools)
        self.builder.add_node("vector_db", vector_db)
        self.builder.add_node("neo4j_db", neo4j_db)
        self.builder.add_node("merge_outputs", merge_outputs)
        self.builder.add_node("slack_send", slack_send)

        # 그래프 시작점 -> 첫 노드 연결 
        self.builder.add_edge(START, "decision_tools")

        # 조건 분기: 어떤 도구를 선택했는지에 따라 다음 노드 결정
        def route_tools(state: ChatbotState):
            tools = state.get("tools", [])
            
            # 환자 정보가 있으면 Neo4j 먼저 실행
            if "neo4j_retriever" in tools:
                return "neo4j_db"
            elif "VectorDB_retriever" in tools:
                return "vector_db"
            else:
                return "merge_outputs"  # 도구가 없으면 바로 답변 생성

        self.builder.add_conditional_edges(
            "decision_tools",
            route_tools,
            {
                "neo4j_db": "neo4j_db",
                "vector_db": "vector_db",
                "merge_outputs": "merge_outputs"
            }
        )
        
        # Neo4j 실행 후 → VectorDB로 이어짐 (환자 정보를 바탕으로 검색)
        def route_after_neo4j(state: ChatbotState):
            if "VectorDB_retriever" in state.get("tools", []):
                return "vector_db"
            else:
                return "merge_outputs"
        
        self.builder.add_conditional_edges(
            "neo4j_db",
            route_after_neo4j,
            {
                "vector_db": "vector_db",
                "merge_outputs": "merge_outputs"
            }
        )
        
        # VectorDB 실행 후 → merge_outputs로 이어짐
        self.builder.add_edge("vector_db", "merge_outputs")
        
        # merge_outputs 후 → slack_send (조건부)
        def route_after_merge(state: ChatbotState):
            if "slack_sender" in state.get("tools", []):
                return "slack_send"
            return END
        
        self.builder.add_conditional_edges(
            "merge_outputs",
            route_after_merge,
            {
                "slack_send": "slack_send",
                END: END
            }
        )
        
        # slack_send → END
        self.builder.add_edge("slack_send", END)
    
    def create_initial_state(self, question: str):
        """초기 상태 생성"""
        return {
            "question": question,
            "tools": [],
            "neo4j_documents": [],
            "vector_documents": [],
            "final_answer": "",
            "messages": [],
            "slack_recipient": None,
            "slack_message": None,
        }
    
    async def ask(self, question: str, verbose: bool = False):
        """질문에 답변"""
        initial_state = self.create_initial_state(question)
        
        if verbose:
            print(f"질문: {question}")
            print("처리 중...")
        
        # 방법 1: invoke를 사용하여 최종 상태 직접 가져오기
        try:
            final_state = await self.graph.ainvoke(initial_state, config=self.config)
            final_answer = final_state.get("final_answer", "")
            slack_message = final_state.get("slack_message", "")
            
            if verbose:
                print(f"최종 상태: {final_state}")
            
            # Slack 메시지가 있으면 함께 반환
            if slack_message:
                return f"{final_answer}\n\n📱 Slack 전송 결과:\n{slack_message}"
            
            return final_answer
            
        except Exception as e:
            if verbose:
                print(f"invoke 실패, astream으로 시도: {e}")
            
            # 방법 2: astream을 사용한 백업 방법
            final_answer = None
            slack_message = None
            async for event in self.graph.astream(initial_state, config=self.config):
                if verbose:
                    print(f"이벤트: {event}")
                
                if "final_answer" in event and event["final_answer"]:
                    final_answer = event["final_answer"]
                if "slack_message" in event and event["slack_message"]:
                    slack_message = event["slack_message"]
            
            if slack_message:
                return f"{final_answer}\n\n📱 Slack 전송 결과:\n{slack_message}"
            
            return final_answer

async def interactive_chat():
    """대화형 채팅 인터페이스"""
    # MCP 초기화
    await initialize_mcp()
    
    chatbot = MedicalChatbot()
    print("의료 챗봇에 오신 것을 환영합니다!")
    print("질문을 입력하세요 (종료하려면 'quit' 또는 'exit' 입력)")
    print("Slack 전송: '누구에게 이 내용을 전달해줘' 형식으로 입력")
    print("-" * 50)
    
    while True:
        try:
            question = input("\n질문: ").strip()
            
            if question.lower() in ['quit', 'exit', '종료']:
                print("챗봇을 종료합니다.")
                break
            
            if not question:
                continue
            
            # 모든 질문을 LangGraph를 통해 처리 (Slack 전송 포함)
            print("질문을 처리하는 중...")
            answer = await chatbot.ask(question, verbose=True)
            print(f"\n답변: {answer}")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\n\n챗봇을 종료합니다.")
            break
        except Exception as e:
            print(f"오류가 발생했습니다: {e}")

async def single_question(question: str):
    """단일 질문 처리"""
    # MCP 초기화
    await initialize_mcp()
    
    chatbot = MedicalChatbot()
    answer = await chatbot.ask(question, verbose=True)
    print(f"\n최종 답변: {answer}")
    return answer

# 실행 함수들
async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="의료 챗봇")
    parser.add_argument("--question", "-q", help="질문")
    parser.add_argument("--interactive", "-i", action="store_true", help="대화형 모드")
    
    args = parser.parse_args()
    
    if args.question:
        await single_question(args.question)
    else:
        # 기본적으로 대화형 모드로 시작
        await interactive_chat()

if __name__ == "__main__":
    asyncio.run(main())
