from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import Dict, Any
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

async def setup_mcp_client():
    mcp_client = MultiServerMCPClient(
        {
        "neo4j_retriever": {
            "command": "본인 로컬 PYTHON 경로",
            "args": ["neo4j_server.py"],
            "transport": "stdio",
        },
        "VectorDB_retriever": {
            "command": "본인 로컬 PYTHON 경로",
            "args": ["pinecone_server.py"],
            "transport": "stdio",
        },
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
    return tools_dict


def setup_mcp_client_sync() -> Dict[str, Any]:
    """
    MCP 툴 설정 동기화
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, setup_mcp_client())
                return future.result()
        else:
            return loop.run_until_complete(setup_mcp_client())
    except RuntimeError:
        return asyncio.run(setup_mcp_client())