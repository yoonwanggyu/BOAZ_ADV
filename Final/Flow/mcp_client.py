from langchain_mcp_adapters.client import MultiServerMCPClient
import os

async def setup_mcp_client():
    mcp_client = MultiServerMCPClient(
        {
            "neo4j_retriever": {
                "command": "/opt/anaconda3/envs/boaz/bin/python",
                "args": ["mcp_neo4j_server.py"],
                "transport": "stdio",
            },
            "VectorDB_retriever": {
                "command": "/opt/anaconda3/envs/boaz/bin/python",
                "args": ["mcp_vectordb_server.py"],
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
                    "SLACK_CHANNEL_IDS": "C093H2LTEF4"
                }
            }
        }
    )
    
    mcp_tools = await mcp_client.get_tools()
    tools_dict = {tool.name: tool for tool in mcp_tools}
    return tools_dict