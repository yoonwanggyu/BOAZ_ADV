import os
from typing import List, Dict
from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
from langchain_neo4j import Neo4jGraph
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Neo4j 연결
neo4j_graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),  
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),  
    refresh_schema=False
)

# OpenAI 클라이언트
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# MCP 서버 초기화
mcp = FastMCP(
    "Integrated_Retriever",
    instructions="An integrated retriever that combines Neo4j graph search with VectorDB retrieval for comprehensive medical information.",
    host="0.0.0.0",
    port=8005,
)

def _embed(text: str) -> List[float]:
    """OpenAI text-embedding-3-large → 3072-dim list[float]."""
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=text.replace("\n", " ")[:8192]
    )
    return resp.data[0].embedding

def create_retriever():
    """VectorDB retriever 생성"""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    pinecone_vs = PineconeVectorStore.from_existing_index(
        index_name="boazpubmed",
        embedding=embeddings,
        namespace="",
        text_key="page_content"
    )

    reranker = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
    compressor = CrossEncoderReranker(model=reranker, top_n=8)

    base = pinecone_vs.as_retriever(search_kwargs={"k": 15})
    compression_retriever = ContextualCompressionRetriever(
        base_retriever=base,
        base_compressor=compressor
    )
    
    return compression_retriever

@mcp.tool()
def neo4j_retriever(question: str, top_k: int = 3) -> List[Dict]:
    """
    Neo4j에서 유사한 환자 정보를 검색합니다.
    
    Args:
        question: 자연어 질문
        top_k: 반환할 상위 결과 수
    
    Returns:
        유사한 환자들의 이름과 유사도 점수
    """
    query_vec = _embed(question)

    cypher = """
    CALL db.vector.similarity.matchNodes(
        'patient_embedding_vector_idx',
        $vec,
        $k
    ) YIELD node, score
    RETURN node.name AS name, score
    """

    rows = neo4j_graph.query(cypher, {"vec": query_vec, "k": top_k})
    return [{"name": r["name"], "score": r["score"]} for r in rows]

@mcp.tool()
async def vector_db_retriever(query: str) -> str:
    """
    VectorDB에서 관련 문서를 검색합니다.
    
    Args:
        query: 검색 쿼리
    
    Returns:
        관련 문서들의 내용
    """
    retriever = create_retriever()
    retrieved_docs = await retriever.ainvoke(query)
    return "\n\n".join(doc.page_content.strip() for doc in retrieved_docs)

@mcp.tool()
async def integrated_search(question: str, neo4j_top_k: int = 3) -> Dict[str, any]:
    """
    Neo4j와 VectorDB를 통합하여 검색합니다.
    1. Neo4j에서 유사한 환자 검색
    2. 환자 정보를 활용해 VectorDB에서 관련 의학 문서 검색
    
    Args:
        question: 자연어 질문
        neo4j_top_k: Neo4j에서 검색할 상위 결과 수
    
    Returns:
        통합 검색 결과 (환자 정보 + 관련 문서)
    """
    # 1. Neo4j에서 유사한 환자 검색
    neo4j_results = neo4j_retriever(question, neo4j_top_k)
    
    # 2. Neo4j 결과로 쿼리 확장
    patient_context = "\n".join([
        f"- {r['name']} (similarity: {r['score']:.3f})" 
        for r in neo4j_results
    ])
    
    expanded_query = f"""
Original Question: {question}

Related Patients from Graph:
{patient_context}

Find relevant medical documents about similar cases, treatments, and outcomes.
"""
    
    # 3. VectorDB에서 관련 문서 검색
    vector_docs = await vector_db_retriever(expanded_query)
    
    # 4. 통합 결과 반환
    return {
        "original_question": question,
        "neo4j_patients": neo4j_results,
        "patient_context": patient_context,
        "related_documents": vector_docs,
        "summary": f"Found {len(neo4j_results)} similar patients and retrieved relevant medical documents."
    }

@mcp.tool()
async def patient_focused_search(patient_name: str) -> Dict[str, any]:
    """
    특정 환자와 유사한 케이스를 찾고 관련 의학 문서를 검색합니다.
    
    Args:
        patient_name: 환자 이름
    
    Returns:
        환자와 유사한 케이스 및 관련 문서
    """
    # 1. 환자 정보 가져오기
    cypher_get_patient = """
    MATCH (p:Patient {name: $name})
    RETURN p.나이 as age, p.증상 as symptoms, p.수술명 as surgery
    """
    
    patient_info = neo4j_graph.query(cypher_get_patient, {"name": patient_name})
    
    if not patient_info:
        return {"error": f"Patient '{patient_name}' not found"}
    
    info = patient_info[0]
    query = f"{info['age']}세 {info['symptoms']} {info['surgery']}"
    
    # 2. 통합 검색 실행
    return await integrated_search(query)

if __name__ == "__main__":
    mcp.run(transport="stdio")