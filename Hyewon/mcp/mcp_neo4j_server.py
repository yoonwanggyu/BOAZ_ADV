from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain.chat_models import ChatOpenAI
from langgraph.graph.message import add_messages
from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage,HumanMessage
import json
import os

load_dotenv()

# Neo4j 연결
neo4j_graph = Neo4jGraph(
    url = os.getenv("NEO4J_URI"),  
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),  
    refresh_schema=False)

# Tool description 자세히 쓰기
mcp = FastMCP(
    "Neo4j_Retriever",
    instructions="A Retriever that can retrieve information from the Neo4j database.",
    host="0.0.0.0",
    port=8005,
)

@mcp.tool()
def neo4j_retriever(query:str):

    data = neo4j_graph.query(query=query)

    return data

# 실행
if __name__ == "__main__":
    print(" MCP neo4j server is running on port 8005...")
    mcp.run(transport="stdio")



# from mcp.server.fastmcp import FastMCP
# from dotenv import load_dotenv
# from langchain_community.graphs import Neo4jGraph as CommunityNeo4jGraph
# from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
# from langchain.chat_models import ChatOpenAI
# import os

# load_dotenv()

# # 🔌 Neo4j 연결
# neo4j_graph = Neo4jGraph(
#     url=os.getenv("NEO4J_URI"),
#     username=os.getenv("NEO4J_USER"),
#     password=os.getenv("NEO4J_PASSWORD"),
#     refresh_schema=True   # schema를 보고 Cypher 생성할 수 있게
# )

# # 🔗 Cypher 자동 생성 QA 체인 구성
# llm = ChatOpenAI(model="gpt-4", temperature=0)
# qa_chain = GraphCypherQAChain.from_llm(
#     llm=llm,
#     graph=neo4j_graph,
#     verbose=True,
# )


# # 🛠️ MCP 설정
# mcp = FastMCP(
#     "neo4j_retriever",
#     instructions="A retriever that converts natural language questions into Cypher and queries Neo4j.",
#     host="0.0.0.0",
#     port=8005,
# )

# # 🧠 자연어 질문 → Cypher 변환 → Neo4j 실행
# @mcp.tool()
# def neo4j_retriever(query: str) -> str:
#     """Ask a natural language question to Neo4j and return the result."""
#     try:
#         result = qa_chain.run(query)
#         return result
#     except Exception as e:
#         return f"❌ Error: {str(e)}"

# # ▶️ 실행
# if __name__ == "__main__":
#     print("📡 MCP neo4j server is running on port 8005...")
#     mcp.run(transport="stdio")




