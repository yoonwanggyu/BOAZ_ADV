import os
from langgraph_node import build_graph
from model import create_model
from prompt import build_prompt
from retriever import create_retriever
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

load_dotenv()

def run_chatbot(question: str, thread_id: str = "1"):

    # <------------------------------------------------- 본인 API 및 Pinecone index 설정
    openai_key = os.environ["OPENAI_API_KEY"]
    pinecone_key = os.environ["PINECONE_API_KEY"]
    index_name = ""

    model = create_model()                  # <--------- model.py에서 원하는 모델로 바꾸기
    prompt = build_prompt()
    retriever = create_retriever(openai_key, pinecone_key, index_name)

    # 그래프 생성
    graph = build_graph(model, prompt, retriever)

    config = RunnableConfig(configurable={"thread_id": thread_id})
    input_state = {"question": question, "messages": []}

    for event in graph.stream(input_state, config=config):
        print(event)

if __name__ == "__main__":
    q = input("질문 입력: ")
    run_chatbot(q)