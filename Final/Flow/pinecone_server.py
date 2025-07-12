from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from mcp.server.fastmcp import FastMCP
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
import os

load_dotenv()

def create_retriever():
    
    # 1536차원 임베딩 사용 (인덱스와 일치)
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002",
                                  api_key=os.getenv("OPENAI_API_KEY"))
    
    # 올바른 설정
    pinecone_vs = PineconeVectorStore.from_existing_index(
        index_name="boazpubmed",
        embedding=embeddings,
        namespace="",  # 빈 네임스페이스 (26483개 문서가 있는 곳)
        text_key="page_content"  # 🎯 핵심: 실제 텍스트가 저장된 키
    )

    # Reranker 설정
    reranker = HuggingFaceCrossEncoder(model_name="ncbi/MedCPT-Cross-Encoder") #MedCPT-Cross-Encoder 리랭커 사용용
    compressor = CrossEncoderReranker(model=reranker, top_n=4)

    base = pinecone_vs.as_retriever(search_kwargs={"k": 10})
    compression_retriever = ContextualCompressionRetriever(
        base_retriever=base,
        base_compressor=compressor)
    
    return compression_retriever

mcp = FastMCP(
    "VectorDB_Retriever",
    instructions="A Retriever that can retrieve information from the Chroma VectorDB.",
    host="0.0.0.0",
    port=8005
)

@mcp.tool()
async def VectorDB_retriever(query: str):

    retriever = create_retriever()

    return retriever

if __name__ == "__main__":
    mcp.run(transport="stdio")