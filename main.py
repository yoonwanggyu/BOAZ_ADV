from src.edge import *
from src.mcp_client import *

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
import asyncio

load_dotenv()
tools_dict = None
graph = None

def initialize_chatbot():
    global tools_dict, graph
    
    tools_dict = setup_mcp_client_sync()
    if not tools_dict:
        print("MCP 도구를 불러오지 못했습니다. 서버 설정 또는 연결 상태를 확인하세요.")
        
    print("현재 tools_dict에 등록된 MCP 툴 목록:")
    for k, v in tools_dict.items():
        print(f"  - {k}: {v}")
    
    graph = create_chatbot_graph()
    
    return tools_dict, graph

async def run_chatbot(query, thread_id, user_name):
    global tools_dict, graph
    
    if graph is None:
        tools_dict, graph = initialize_chatbot()
    
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "question": query,
        "loop_cnt": 0,
        "messages": [HumanMessage(content=query)],
        "user_name": user_name,
    }
    answer_state = None
    async for event in graph.astream(initial_state, config=config):
        for node_name, node_state in event.items():
            print(f"--- Event: Node '{node_name}' finished ---")
            if node_name == 'merge_and_respond':
                print("\n\n" + "="*50)
                print("최종 실행 결과:")
                print(f"  - 최종 답변: {node_state['final_answer']}")
                if node_state.get('slack_response'):
                    print(f"  - 슬랙 응답: {node_state['slack_response']}")
                answer_state = node_state  
            if node_name == 'reset_state_node':
                print("--- 상태 초기화 완료 ---")

    if answer_state:
        if answer_state.get('slack_response'):
            return answer_state.get('slack_response')
        else:
            return answer_state.get('final_answer')
        
class Runner:
    @classmethod
    async def run(cls, query, thread_id, user_name):
        return await run_chatbot(query, thread_id, user_name)

    @classmethod
    def run_sync(cls, query, thread_id, user_name):
        try:
            loop = asyncio.get_running_loop()
            future = asyncio.ensure_future(
                cls.run(query, thread_id, user_name)
            )
            return loop.run_until_complete(future)
        except RuntimeError:
            return asyncio.run(
                cls.run(query, thread_id, user_name)
            )

def main():
    initialize_chatbot()
    query = "원하는 질문 입력"
    print("="*20 + " 테스트 : Sequential Case " + "="*20)
    result = Runner.run_sync(query, "thread-2", "user-1")
    print(result)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()