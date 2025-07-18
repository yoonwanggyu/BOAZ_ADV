from edge import *
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from mcp_client import setup_mcp_client_sync

# MCP 툴 확인
tools_dict = setup_mcp_client_sync()

print("현재 tools_dict에 등록된 MCP 툴 목록:")
for k, v in tools_dict.items():
    print(f"  - {k}: {v}")

# 환경 변수 설정
load_dotenv()

graph = create_chatbot_graph()

# 챗봇 실행 함수
async def run_chatbot(query, thread_id):
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "question": query,
        "loop_cnt": 0,
        "messages": [HumanMessage(content=query)]
    }
    async for event in graph.astream(initial_state, config=config):
        for node_name, node_state in event.items():
            print(f"--- Event: Node '{node_name}' finished ---")
            if node_name == END:
                print("\n\n" + "="*50)
                print("최종 실행 결과:")
                print(f"  - 최종 답변: {node_state['final_answer']}")
                if node_state.get('slack_response'):
                    print(f"  - 슬랙 응답: {node_state['slack_response']}")
                print("="*50)

# 실행용 main 함수
# 테스트 Example : Sequential case (Neo4j -> VectorDB)
async def main():
    query = "Rett syndrome에 기저질환이 있는 환자가 greenstick fracture of the left distal femur 수술을 받은 후 주의사항에 대해 의학적으로 조사해서 자세한 내용을 윤왕규에게 slack으로 보내줘."
    print("="*20 + " 테스트 : Sequential Case " + "="*20)
    await run_chatbot(query, "thread-2")

# Python 3.7+에서 asyncio.run() 사용
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()