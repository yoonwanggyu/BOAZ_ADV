from typing import Annotated, List, TypedDict
from langgraph.graph.message import add_messages
from langchain_community.document_transformers import LongContextReorder
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END

# 1) GraphState 상태 정의
class ChatbotState(TypedDict):
    question: Annotated[str, "Question"]  # 질문
    documents: Annotated[List, "Context"]  # 문서의 검색 결과
    chatbot: Annotated[str, "Answer"]  # 답변
    messages: Annotated[List, add_messages]  # 메시지(누적되는 list)

# 2) 메모리 저장 및 문서 재정렬
memory = MemorySaver()

# 3) graph 노드 설정
def build_graph(model, prompt, retriever):

    reorder = LongContextReorder()

    def retrieve_document(state: ChatbotState):
        question = state["question"]
        docs = retriever.invoke(question)
        ordered = reorder.transform_documents(docs)
        return ChatbotState(documents=ordered)

    def llm_answer(state: ChatbotState):
        question = state["question"]
        docs = state["documents"]

        # 모델이 Llama일 때 활성화
        docs = "\n\n".join(doc.page_content.strip() for doc in docs)

        formatted = prompt.format(context=docs, question=question)
        response = model.invoke(formatted)
        response_text = response.content if isinstance(response, AIMessage) else str(response)
        return ChatbotState(chatbot=response_text,
                            messages=[("user", question), ("assistant", response_text)])

    builder = StateGraph(ChatbotState)

    builder.add_node("docs", retrieve_document)
    builder.add_node("llm_answer", llm_answer)

    builder.add_edge(START, "docs")
    builder.add_edge("docs", "llm_answer")
    builder.add_edge("llm_answer", END)

    return builder.compile(checkpointer=memory)