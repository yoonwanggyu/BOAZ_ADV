from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import Dict, Any
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

# MCP 툴 설정
async def setup_mcp_client():
    mcp_client = MultiServerMCPClient(
        {
        "neo4j_retriever": {
            "command": "/opt/anaconda3/envs/boaz/bin/python",
            "args": ["neo4j_server.py"],
            "transport": "stdio",
        },
        "VectorDB_retriever": {
            "command": "/opt/anaconda3/envs/boaz/bin/python",
            "args": ["pinecone_server.py"],
            "transport": "stdio",
        },
        # Slack MCP 서버 설정
        "slack": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-slack"
            ],
            "transport": "stdio", 
            "env": {
                "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
                "SLACK_TEAM_ID": os.getenv("SLACK_TEAM_ID"),
            }
        }
    }
)
    
    mcp_tools = await mcp_client.get_tools()
    tools_dict = {tool.name: tool for tool in mcp_tools}
    print("tools_dict:", tools_dict)
    return tools_dict

# MCP 툴 설정 동기화
def setup_mcp_client_sync() -> Dict[str, Any]:
    try:
        # 기존 이벤트 루프가 있는지 확인
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 루프가 있으면 새 루프 생성
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, setup_mcp_client())
                return future.result()
        else:
            return loop.run_until_complete(setup_mcp_client())
    except RuntimeError:
        # 이벤트 루프가 없으면 새로 생성
        return asyncio.run(setup_mcp_client())