import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stdin.reconfigure(encoding='utf-8')

# 1. 환경변수 로드
load_dotenv()

# 2. LLM 모델 세팅
model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

# 3. MCP 서버 등록 (Windows 실제 python 경로로 수정!)
client = MultiServerMCPClient(
    {
        "VectorDB_retriever": {
            "command": "C:/Users/user/anaconda3/envs/chatbot/python.exe",
            "args": ["mcp_vectordb_server.py"],
            "transport": "stdio",
        }
    }
)
print(" MCP client set")

# 4. RunnableConfig 세팅
config = RunnableConfig(recursion_limit=30, thread_id=1)

# 5. 프롬프트
long_medical_prompt = """
You are an assistant specialized in question-answering tasks based on PubMed anesthesia research papers.
Use the following pieces of retrieved context to answer the question. If you don't know the answer, simply say that you don't know.
Answer in Korean.

# Direction:
1. Understand the intent of the question and provide the most accurate answer.
2. Identify and select the most relevant content from the retrieved context that directly relates to the question.
3. Construct a concise and logical answer by rearranging the selected information into coherent paragraphs.
4. If there is no relevant context for the question, state: "I can't find an answer to that question in the materials I have."
5. Present your answer in a table of key points where applicable.
6. Include all sources by listing the **paper_title** field from the document metadata.
7. Write your answer entirely in Korean.
8. Be as detailed as possible in your answer.

#Context: 
{context}

###

#Example Format:
**📚 PubMed 마취 논문에서 검색한 내용 기반 답변입니다**

(상세 답변)

**📌 출처**
- paper_title
- paper_title
- ...

###

#Question:
{question}

#Answer:
"""


# 6. 에이전트 실행 함수
async def run_agent(question):
    print(" MCP tools load")
    tools = await client.get_tools()
    print(f" available MCP tools: {[tool.name for tool in tools]}")

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=long_medical_prompt,   # ← 커스텀 프롬프트 사용!
        checkpointer=MemorySaver(),
    )

    print(" agent run")
    try:
        result = await agent.ainvoke({
            "messages": [
                {"role": "user", "content": question}
            ]
        }, config=config)
        print(" result object:", result)
    except Exception as e:
        print("❌ agent.ainvoke에서 예외 발생:", e)
        import traceback
        traceback.print_exc()
        return

    print(" result print")
    for msg in result['messages']:
        role = msg.__class__.__name__
        if hasattr(msg, "content") and msg.content:
            print(f"{role} : {msg.content}")
        elif role == "AIMessage":
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                print(f"{role} : tool_calls → {tool_calls}")
            else:
                print(f"{role} : [No content and no tool_calls]")
        else:
            print(f"{role} : [No content]")

if __name__ == "__main__":
    user_input = "Maquet Flow-i의 자동 가스 제어를 사용할 때와 수동 모드로 사용할 때 소아 마취에서 sevoflurane 사용량 차이는 어느 정도인가요?"
    asyncio.run(run_agent(user_input))
