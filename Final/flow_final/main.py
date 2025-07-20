from edge import *
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from mcp_client import setup_mcp_client_sync
import asyncio

# Runner 클래스 추가
class Runner:
    @classmethod
    async def run(cls, query, thread_id):
        return await run_chatbot(query, thread_id)

    @classmethod
    def run_sync(cls, query, thread_id):
        try:
            loop = asyncio.get_running_loop()
            future = asyncio.ensure_future(
                cls.run(query, thread_id)
            )
            return loop.run_until_complete(future)
        except RuntimeError:
            return asyncio.run(
                cls.run(query, thread_id)
            )

# 전역 변수들
tools_dict = None
graph = None

def initialize_chatbot():
    global tools_dict, graph
    
    # MCP 툴 확인
    tools_dict = setup_mcp_client_sync()
    
    print("현재 tools_dict에 등록된 MCP 툴 목록:")
    for k, v in tools_dict.items():
        print(f"  - {k}: {v}")
    
    # 환경 변수 설정
    load_dotenv()
    
    # 그래프 생성
    graph = create_chatbot_graph()
    
    return tools_dict, graph

# 챗봇 실행 함수
async def run_chatbot(query, thread_id):
    global tools_dict, graph
    
    # 초기화가 안 되어 있으면 초기화
    if graph is None:
        tools_dict, graph = initialize_chatbot()
    
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "question": query,
        "loop_cnt": 0,
        "messages": [HumanMessage(content=query)]
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
                answer_state = node_state  # 답변 상태 저장
            if node_name == 'reset_state_node':
                print("--- 상태 초기화 완료 ---")

    # 답변은 merge_and_respond 상태에서 반환
    if answer_state:
        if answer_state.get('slack_response'):
            return answer_state.get('slack_response')
        else:
            return answer_state.get('final_answer')

# 실행용 main 함수
# 테스트 Example : Sequential case (Neo4j -> VectorDB)
def main():
    initialize_chatbot()
    query = "박혜원 환자의 나이대와 진단내역에 대해 백다은에게 알려줘"
    print("="*20 + " 테스트 : Sequential Case " + "="*20)
    result = Runner.run_sync(query, "thread-2")
    print(result)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()