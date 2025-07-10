from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings

def create_retriever(openai_key, pinecone_key, index_name):

    # 1) pinecone retriever 설정
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", 
                                  api_key=openai_key)
    pc = Pinecone(api_key=pinecone_key)
    index = pc.Index(index_name)
    vectorstore = PineconeVectorStore(index=index, 
                                      embedding=embeddings, 
                                      text_key="page_content")
    pinecone_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    
    # 2) reranker 설정
    reranker = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-v2-m3")
    compressor = CrossEncoderReranker(model=reranker, 
                                      top_n=5)
    
    return ContextualCompressionRetriever(base_retriever=pinecone_retriever, 
                                          base_compressor=compressor)