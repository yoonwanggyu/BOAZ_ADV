from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from mcp.server.fastmcp import FastMCP
from langchain_community.vectorstores import Pinecone
from langchain_community.embeddings import OpenAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
import os

load_dotenv()

# def create_retriever():
    
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

# def load_pinecone_retriever():

#     embeddings = OpenAIEmbeddings(model="text-embedding-3-large",
#                                           api_key=os.getenv("OPENAI_API_KEY"))

#     pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
#     index_name = 'boazpubmed'
#     pinecone_index = pc.Index(index_name)
    
#     vectorstore = PineconeVectorStore(index=pinecone_index , 
#                                       embedding=embeddings, 
#                                       text_key="page_content")
    
#     pinecone_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

#     reranker = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-v2-m3")
#     compressor = CrossEncoderReranker(model=reranker, 
#                                       top_n=5)

#     final_retriever = ContextualCompressionRetriever(base_retriever=pinecone_retriever, 
#                                                     base_compressor=compressor)
#     return final_retriever

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
    reranker = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
    compressor = CrossEncoderReranker(model=reranker, top_n=8)

    base = pinecone_vs.as_retriever(search_kwargs={"k": 15})
    compression_retriever = ContextualCompressionRetriever(
        base_retriever=base,
        base_compressor=compressor
    )
    
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

    retrieved_docs = retriever.invoke(query)

    # return "\n".join([doc.page_content for doc in retrieved_docs])
    return "\n\n".join(doc.page_content.strip() for doc in retrieved_docs)

if __name__ == "__main__":
    mcp.run(transport="stdio")