import os
from langgraph_node import build_graph
from model import create_ollama_model, create_llama_model, create_GPT_model
from prompt import build_GPT_prompt, build_Llama_prompt
from retriever import create_retriever
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

load_dotenv()

def run_chatbot(question: str, thread_id: str = "1"):

    # <------------------------------------------------- 본인 API 및 Pinecone index 설정
    openai_key = os.environ["OPENAI_API_KEY"]
    pinecone_key = os.environ["PINECONE_API_KEY"]
    index_name = "boaz-adv"

    model = create_llama_model()                     # <--------- 원하는 모델로 바꾸기
    prompt = build_Llama_prompt()                    # <--------- 모델에 맞는 프롬프트 쓰기
    retriever = create_retriever(openai_key, pinecone_key, index_name)

    # 그래프 생성
    graph = build_graph(model, prompt, retriever)

    config = RunnableConfig(configurable={"thread_id": thread_id})
    input_state = {"question": question, "messages": []}

    for event in graph.stream(input_state, config=config):
        for value in event.values():
            if 'documents' in value:
                for idx, doc in enumerate(value['documents']):  
                    print(f"📄 {idx+1}번째 문서 / 문서 이름 : {doc.metadata['document_name']} / 페이지 : {doc.metadata['page']}")
                    print(doc.page_content)

            if 'chatbot' in value:
                response = value["chatbot"]
                print("💬 답변:")
                full_text = getattr(response, "content", response) # AIMessage or str : GPT / Llama 형식이 다름

                if isinstance(full_text, str) and "Answer:" in full_text:
                    answer_only = full_text.split("Answer:", 1)[-1].strip()
                    print("💬(Llama) 추출된 답변:")
                    print(answer_only)
                else:
                    print("💬(GPT) 전체 응답:")
                    print(full_text)

if __name__ == "__main__":
    q = input("질문 입력: ")
    run_chatbot(q)