from edge import *
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# .env 파일 로드
load_dotenv("/Users/yoon/BOAZ_ADV/Wang_Gyu/code/mcp/.env")

graph = create_chatbot_graph()

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

async def main():
    """메인 함수"""
    # 테스트 1: VectorDB Only (자동 쿼리 보정)
    query1 = "윤왕규 환자의 나이와 성별, 처방받은 약물에 대해 조사해서 백다은에게 slack으로 보내줘."
    print("="*20 + " 테스트 1: VectorDB Only (With Self-Correction) " + "="*20)
    await run_chatbot(query1, "thread-1")
    
    print("\n\n" + "="*80 + "\n\n")

    # 테스트 2: Sequential (Neo4j -> VectorDB)
    # query2 = "6세 여아 폐렴 환자가 받을 수술을 알려주고, 수술에 사용될 마취 약물에 대해 조사해서 백지연에게 slack으로 보내줘."
    # print("="*20 + " 테스트 2: Sequential " + "="*20)
    # await run_chatbot(query2, "thread-2")

if __name__ == "__main__":
    """Python 파일로 직접 실행될 때만 main() 함수 실행"""
    try:
        # Python 3.7+에서 asyncio.run() 사용
        asyncio.run(main())
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()