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

if __name__ == "__main__":
    mcp.run(transport="stdio")