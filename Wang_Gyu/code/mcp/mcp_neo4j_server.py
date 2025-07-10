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
from openai import OpenAI
from typing import List, Dict

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

# @mcp.tool()
# def neo4j_retriever(query:str):

#     data = neo4j_graph.query(query=query)

#     return data


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _embed(text: str) -> List[float]:
    """OpenAI text-embedding-3-large → 3072-dim list[float]."""
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=text.replace("\n", " ")[:8192]  # 토큰 한도 대비
    )
    return resp.data[0].embedding

@mcp.tool()
def neo4j_retriever(question: str, top_k: int = 3) -> List[Dict]:
    """
    자연어 질문을 임베딩하여 (:Patient.embedding) 벡터 인덱스와 코사인 유사도 Top-k 환자를 반환.
    """
    query_vec = _embed(question)

    cypher = """
    CALL db.vector.similarity.matchNodes(
        'patient_embedding_vector_idx',  // 인덱스 이름
        $vec,                            // 쿼리 벡터
        $k                               // Top-k
    ) YIELD node, score
    RETURN node.name AS name, score
    """

    rows = neo4j_graph.query(cypher, {"vec": query_vec, "k": top_k})
    return [{"name": r["name"], "score": r["score"]} for r in rows]

if __name__ == "__main__":
    mcp.run(transport="stdio")
