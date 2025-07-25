from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from mcp.server.fastmcp import FastMCP
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
import os

# 환경변수 설정
load_dotenv()

openai_api_key = os.environ["OPENAI_API_KEY"]
pinecone_api_key = os.environ["PINECONE_API_KEY"]
pinecone_index_name = os.environ['pinecone_index_name']

# 리트리버 생성 함수
def create_retriever():
    # 임베딩 모델
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        api_key=openai_api_key
    )

    # Pinecone 클라이언트 및 인덱스 로드
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(pinecone_index_name)

    # LangChain VectorStore로 래핑
    vectorstore = PineconeVectorStore(
        index=index,
        embedding=embeddings,
        text_key="page_content"
    )

    # CrossEncoder reranker 설정
    reranker_model = HuggingFaceCrossEncoder(model_name="ncbi/MedCPT-Cross-Encoder")
    compressor_retriever = CrossEncoderReranker(
        model=reranker_model,
        top_n=3
    )
    # 기본 검색기 → 압축된 Retriever로 감싸기
    base_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    retriever = ContextualCompressionRetriever(
        base_retriever=base_retriever,
        base_compressor=compressor_retriever
    )

    return retriever

# MCP 서버 정의
mcp = FastMCP(
    "VectorDB_Retriever",
    instructions="A Retriever that can retrieve information from the Pinecone VectorDB.",
    host="0.0.0.0",
    port=8005
)

# MCP tool 함수 정의
@mcp.tool()
async def VectorDB_retriever(query: str):
    retriever = create_retriever()
    retrieved_docs = retriever.invoke(query)
    return "\n".join([doc.page_content for doc in retrieved_docs])

# 실행
if __name__ == "__main__":
    print("MCP server is running on port 8005...")
    mcp.run(transport="stdio")

