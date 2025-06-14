from langchain_community.graphs import Neo4jGraph
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv
from typing import Annotated, List, TypedDict
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage,HumanMessage
import json
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from openai import OpenAI
from langchain.chat_models import ChatOpenAI
import requests
import socket
import time

load_dotenv()

# MCP 설정
MCP_HOST = os.getenv("MCP_HOST", "localhost")
MCP_PORT = int(os.getenv("MCP_PORT", "5000"))
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#medical-alerts")

# Neo4j 연결
neo4j_graph = Neo4jGraph(
    url="bolt://localhost:7687",  
    username="neo4j",
    password="123456789",  
    refresh_schema=False)

# LLM 정의 (OpenAI 사용 예시)
llm = ChatOpenAI(model="gpt-4", 
                 temperature=0.3)

# GraphState 상태 정의
class ChatbotState(TypedDict):
    question: Annotated[str, "Question"] 
    neo4j_data: Annotated[List, "Context"]  
    vector_data: Annotated[List, "Context"]  
    answer: Annotated[str, "Answer"]  
    messages: Annotated[List, add_messages]  
    tools : Annotated[List,"tool"]

# 질문을 Cypher로 변환 함수 후 검색된 값 리턴
def change_query_to_cypher(state: ChatbotState):

    CYPHER_GENERATION_TEMPLATE = PromptTemplate.from_template("""
# Task:
Generate a Cypher query to answer the user's question using the provided graph schema.

# Guidelines:
- Use only the relationship types and node properties defined in the schema.
- Use MATCH and RETURN clauses to extract only the necessary properties.
- Always filter using WHERE clauses with node properties when appropriate (e.g., p.name CONTAINS "xxx").
- If the question expects a count or number, use count(*) with an alias.
- If descriptive fields are expected, use RETURN ... AS [Korean field name] style.
- Avoid returning full nodes unless explicitly requested.
- If the question refers to information not present in the schema, respond with: `UNSUPPORTED_QUERY`

# Schema (Node:Label and Relationship):
(:Patient)-[:UNDERWENT]->(:Surgery)
(:Surgery)-[:HAS_SYMPTOM]->(:Symptom)
(:Surgery)-[:HAS_PROCEDURE]->(:Procedure)
(:Surgery)-[:HAS_RESULT]->(:Result)
(:Surgery)-[:HAS_NOTE]->(:Note)

# Examples:
Question: How many surgeries has Patient A undergone?
MATCH (p:Patient)-[:UNDERWENT]->(s:Surgery) WHERE p.name CONTAINS  "Patient A" RETURN count(s) AS 수술횟수

Question: What is the result of 환아 B's surgery?
MATCH (p:Patient)-[:UNDERWENT]->(s:Surgery)-[:HAS_RESULT]->(r:Result) WHERE p.name CONTAINS  "환아 B" RETURN s.name AS 수술명, r.description AS 수술후상태
# User's Question:
{question}
""")
    
    query = state["question"]
    
    CYPHER_GENERATION_PROMPT = CYPHER_GENERATION_TEMPLATE.format(question=query)

    cypher_query = llm.invoke(CYPHER_GENERATION_PROMPT)

    if isinstance(cypher_query, AIMessage):
        response_text = cypher_query.content
    else:
        response_text = str(cypher_query)

    data = neo4j_graph.query(response_text)

    return ChatbotState(neo4j_data=[json.dumps(data, ensure_ascii=False)])

# 그래프 db 데이터를 기반으로 답변 생성
def generate_cypher_to_answer(state: ChatbotState):

    prompt = PromptTemplate.from_template("""You are a helpful assistant for medical patient queries.
                Based on the data below from the knowledge graph, answer the user's question.

                Question: {question}

                Graph Results:{results}

                Answer:
                """)
    
    query = state["question"]
    docs = state['documents']
    
    formatted_prompt = prompt.format(question = query, results = docs)

    response = llm.invoke(formatted_prompt) 

    if isinstance(response, AIMessage):
        response_text = response.content
    else:
        response_text = str(response)

    return ChatbotState(answer=response_text,
                        messages=[HumanMessage(content=query),AIMessage(content=response_text)])


# vector db에서 문서 검색하는 노드
def retrieve_vector_db(state:ChatbotState):

    query = state["question"]
    
    edit_path = "./edit_db"
    
    load_edit_db = Chroma(persist_directory=edit_path,
                        embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
                        collection_name="edit")
    
    reranker_model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-v2-m3")
    compressor_retriever = CrossEncoderReranker(model=reranker_model, 
                                                top_n=5)
    
    edit_db_retriever = load_edit_db.as_retriever(search_kwargs={"k": 10})
    edit_retriever = ContextualCompressionRetriever(base_retriever=edit_db_retriever, 
                                                    base_compressor=compressor_retriever)
    
    docs = edit_retriever.invoke(query)

    return ChatbotState(vector_data = docs)

# 벡터 db에서 검색된 내용을 바탕으로 답변 생성
def generate_answer(state:ChatbotState):

    query = state["question"]
    docs = state['vector_data']

    prompt = PromptTemplate.from_template("""You are a helpful assistant for medical patient queries.
                Based on the data below from the knowledge graph, answer the user's question accurately and concisely.
                Only use the information retrieved — do not add any extra or speculative content.

                User's Question:
                {user_question}

                Retrieved Documents:
                {retrieved_content}

                Your Response:

                """)
    
    formatted_prompt = prompt.format(user_question = query, retrieved_content = docs)

    response = llm.invoke(formatted_prompt) 

    if isinstance(response, AIMessage):
        response_text = response.content
    else:
        response_text = str(response)

    return ChatbotState(answer=response_text,
                        messages=[HumanMessage(content=query),AIMessage(content=response_text)])

# 이메일 보내는 노드
def send_email(state: ChatbotState):
    try:
        # MCP 메시지 포맷
        mcp_message = {
            "type": "slack_message",
            "channel": SLACK_CHANNEL,
            "content": {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚨 의료 알림",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*환자 질문:*\n{state['question']}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*처리 결과:*\n{state.get('answer', '처리 중')}"
                            }
                        ]
                    }
                ]
            }
        }

        # MCP 서버에 연결
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((MCP_HOST, MCP_PORT))
            # 메시지 전송
            s.sendall(json.dumps(mcp_message).encode('utf-8'))
            # 응답 대기
            response = s.recv(1024).decode('utf-8')
            
            if response:
                return ChatbotState(
                    answer="MCP를 통해 Slack으로 알림이 전송되었습니다.",
                    messages=[HumanMessage(content=state["question"]), AIMessage(content="MCP를 통해 Slack으로 알림이 전송되었습니다.")]
                )
            else:
                return ChatbotState(
                    answer="MCP 메시지 전송 실패: 응답 없음",
                    messages=[HumanMessage(content=state["question"]), AIMessage(content="MCP 메시지 전송 실패: 응답 없음")]
                )
            
    except ConnectionRefusedError:
        return ChatbotState(
            answer="MCP 서버 연결 실패: 서버가 실행 중이지 않습니다.",
            messages=[HumanMessage(content=state["question"]), AIMessage(content="MCP 서버 연결 실패: 서버가 실행 중이지 않습니다.")]
        )
    except Exception as e:
        return ChatbotState(
            answer=f"MCP 메시지 전송 중 오류 발생: {str(e)}",
            messages=[HumanMessage(content=state["question"]), AIMessage(content=f"MCP 메시지 전송 중 오류 발생: {str(e)}")]
        )

# tool(함수) 목록 정의
tools = [
    {
        "type": "function",
        "function": {
            "name": "change_query_to_cypher",
            "description": "환자의 정보를 찾기 위해 그래프 DB에서 검색하는 함수입니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Patient name, e.g., 환아 A"
                    }
                },
                "required": ["name"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_vector_db",
            "description": "의학 정보를 Chroma Vector DB에서 검색하는 함수입니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query, e.g., 혈소판감소증의 주된 원인은 무엇인가요?"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "이메일을 보내는 함수입니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query, e.g., 간호사1한테 이메일좀 보내줘."
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
]

client = OpenAI()
# 어떤 함수를 호출할지 결정하는 에이전트
def agent_llm(state: ChatbotState):
    query = state["question"]
    
    messages = [
        {"role": "system", "content": "You are a helpful medical assistant that can use various tools to help answer questions."},
        {"role": "user", "content": query}
    ]

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=tools,
        tool_choice="auto",               
        parallel_tool_calls=True)

    assistant_message = completion.choices[0].message
    tool_calls = assistant_message.tool_calls

    tools = []
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        tools.append(function_name)
        function_args = json.loads(tool_call.function.arguments)

    return ChatbotState(tools=tools)

# 최종 선택된 노드들의 결과값을 합치는 LLM
def aggregate_node(state:ChatbotState):
    tool_list = state['tools']
    neo4j_data = state.get('neo4j_data', [])
    vector_data = state.get('vector_data', [])
    answer = state.get('answer', '')
    
    # Combine all available information
    combined_context = []
    if neo4j_data:
        combined_context.append("Graph Database Results:")
        combined_context.extend(neo4j_data)
    if vector_data:
        combined_context.append("\nVector Database Results:")
        combined_context.extend([str(doc) for doc in vector_data])
    
    # Generate final response
    prompt = PromptTemplate.from_template("""You are a helpful medical assistant. Please provide a comprehensive answer 
    based on all available information. If there are conflicting information, prioritize the most recent or most specific data.

    User's Question: {question}

    Available Information:
    {context}

    Please provide a clear and concise response that addresses the user's question.
    """)
    
    formatted_prompt = prompt.format(
        question=state["question"],
        context="\n".join(combined_context)
    )
    
    response = llm.invoke(formatted_prompt)
    
    if isinstance(response, AIMessage):
        final_response = response.content
    else:
        final_response = str(response)
    
    return ChatbotState(
        answer=final_response,
        messages=[HumanMessage(content=state["question"]), AIMessage(content=final_response)]
    )

# 그래프 정의
builder = StateGraph(ChatbotState)

# 노드 정의
builder.add_node("change_query_to_cypher", change_query_to_cypher)
builder.add_node("generate_cypher_to_answer", generate_cypher_to_answer)
builder.add_node("retrieve_vector_db", retrieve_vector_db)
builder.add_node("generate_answer", generate_answer)
builder.add_node("send_mail", send_email)
builder.add_node("aggregate_node", aggregate_node)
builder.add_node("agent_llm", agent_llm)

# 노드 연결
builder.add_edge(START, "agent_llm")
builder.add_edge("agent_llm", "change_query_to_cypher", condition=lambda x: "change_query_to_cypher" in x["tools"])
builder.add_edge("agent_llm", "retrieve_vector_db", condition=lambda x: "retrieve_vector_db" in x["tools"])
builder.add_edge("agent_llm", "send_mail", condition=lambda x: "send_email" in x["tools"])
builder.add_edge("change_query_to_cypher", "generate_cypher_to_answer")
builder.add_edge("retrieve_vector_db", "generate_answer")
builder.add_edge("generate_cypher_to_answer", "aggregate_node")
builder.add_edge("generate_answer", "aggregate_node")
builder.add_edge("send_mail", "aggregate_node")
builder.add_edge("aggregate_node", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

if __name__ == "__main__":
    # 테스트 쿼리
    test_query = "환아 A의 수술 정보를 알려주세요"
    
    # 초기 상태 설정
    initial_state = ChatbotState(
        question=test_query,
        neo4j_data=[],
        vector_data=[],
        answer="",
        messages=[],
        tools=[]
    )
    
    # 그래프 실행
    try:
        result = graph.invoke(initial_state)
        print("\n최종 응답:")
        print(result["answer"])
    except Exception as e:
        print(f"에러 발생: {str(e)}")