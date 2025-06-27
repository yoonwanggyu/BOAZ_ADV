from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from mcp.server.fastmcp import FastMCP
# 바꿔야 할 새 버전
from langchain_community.vectorstores import Pinecone
from langchain_community.embeddings import OpenAIEmbeddings
import pinecone

load_dotenv()

def load_pinecone_retriever():
    # 1. 파인콘 초기화 (API키, 환경 설정)
    pinecone.init(api_key="PINECONE_API_KEY", environment="PINECONE_ENV")
    
    # 2. 인덱스 연결
    index_name = 'boazadv1'
    pinecone_index = pinecone.Index(index_name)
    
    # 3. 임베딩 함수 설정
    embedding_function = OpenAIEmbeddings(model="text-embedding-3-large")
    
    # 4. 파인콘 래퍼로 불러오기
    retriever = Pinecone(index=pinecone_index,
                         embedding_function=embedding_function,
                         top_k=10)  # 한번에 조회할 개수 지정
    
    return retriever


# 왕규오빠꺼 def create_retriever():
    
#     edit_path = "/Users/yoon/BOAZ_ADV/Wang_Gyu/edit_db"
    
#     load_edit_db = Chroma(persist_directory=edit_path,
#                         embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
#                         collection_name="edit")
    
#     reranker_model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-v2-m3")
#     compressor_retriever = CrossEncoderReranker(model=reranker_model, 
#                                                 top_n=5)
    
#     edit_db_retriever = load_edit_db.as_retriever(search_kwargs={"k": 10})
#     edit_retriever = ContextualCompressionRetriever(base_retriever=edit_db_retriever, 
#                                                     base_compressor=compressor_retriever)


#     return edit_retriever

mcp = FastMCP(
    "VectorDB_Retriever",
    instructions="A Retriever that can retrieve information from the Chroma VectorDB.",
    host="0.0.0.0",
    port=8005)

@mcp.tool()
async def VectorDB_retriever(query: str):

    retriever = create_retriever()

    retrieved_docs = retriever.invoke(query)

    return "\n".join([doc.page_content for doc in retrieved_docs])

if __name__ == "__main__":
    mcp.run(transport="stdio")