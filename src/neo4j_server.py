from embedder import *

from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import VectorRetriever
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import time

load_dotenv()

embedder = SMCEmbeddings(model="text-embedding-3-large", 
                         dimensions=256, 
                         api_key=os.getenv("OPENAI_API_KEY"))

NEO4J_URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("DATABASE"), os.getenv("AUTH_LINK"))
DATABASE = os.getenv("DATABASE")

driver = GraphDatabase.driver(NEO4J_URI, auth=AUTH)

llm = OpenAILLM(model_name="gpt-4o-mini", 
                model_params={"temperature": 0.1})

retriever = VectorRetriever(
    driver,
    index_name="entity_vector",
    embedder=embedder,
    return_properties=["name"],
)

mcp = FastMCP(
    "Neo4j_Retriever",
    instructions="A Retriever that can retrieve information from the Neo4j database.",
    host="0.0.0.0",
    port=8005,
)

def get_node_with_neighbors(driver, element_id):
    """
    elementId로 1-hop 연결 정보 가져오는 함수
    """
    query = """
    MATCH (n) WHERE elementId(n) = $elementId
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN 
      n {.name, labels: labels(n)} AS starting_node,
      collect({
        neighbor_name: m.name,
        text: m.text,
        neighbor_labels: labels(m),
        relation: type(r),
        direction: CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END
      }) AS neighbors
    """
    with driver.session() as session:
        result = session.run(query, elementId=element_id)
        return result.single()


def build_context_from_vector(driver, query_text: str, top_k: int = 5) -> str:
    """
    context 생성 함수
    """

    query_vector = embedder.embed_query(query_text, dimensions=256)

    retriever_result = retriever.search(query_vector=query_vector, top_k=top_k)

    for i, item in enumerate(retriever_result.items):
        element_id = item.metadata.get('id', 'Unknown')

    expanded_contexts = []

    for i, item in enumerate(retriever_result.items):
        element_id = item.metadata['id']
        
        node_start = time.time()
        node_info = get_node_with_neighbors(driver, element_id)
        node_time = time.time() - node_start
        
        if node_info:
            neighbors_count = len(node_info['neighbors'])
            expanded_contexts.append(node_info)
        else:
            print(f"노드 정보를 찾을 수 없음 - 시간: {node_time:.2f}초")

    context_lines = []
    total_neighbors = 0
    
    for ctx_idx, ctx in enumerate(expanded_contexts):
        start = ctx['starting_node']
        start_name = start.get('name', 'Unknown')
        start_labels = [l for l in start.get('labels', []) if l not in {'__KGBuilder__', '__Entity__'}]
        context_lines.append(f"starting_node: {start_name} ({', '.join(start_labels)})")
        
        neighbors_count = len(ctx['neighbors'])
        total_neighbors += neighbors_count

        for neighbor in ctx['neighbors']:
            labels = [l for l in neighbor.get('neighbor_labels', []) if l not in {'__KGBuilder__', '__Entity__'}]
            label_str = f"[{', '.join(labels)}]" if labels else "[Unknown]"

            if 'Chunk' in neighbor.get('neighbor_labels', []):
                neighbor_value = neighbor.get('text', 'None')
            else:
                neighbor_value = neighbor.get('neighbor_name', 'None')

            relation = neighbor.get('relation', 'UNKNOWN_RELATION')
            direction = neighbor.get('direction', 'out')

            if direction == 'out':
                triple = f"({start_name}, {relation}, {neighbor_value})"
            else:
                triple = f"({neighbor_value}, {relation}, {start_name})"

            context_lines.append(f"{label_str} : \"{neighbor_value}\" {triple}")

    return "\n".join(context_lines)

@mcp.tool()
def run_contextual_rag(query_text: str):
    """
    Neo4j 데이터베이스에서 컨텍스트를 검색하고 LLM으로 답변을 생성
    """
    try:
        context = build_context_from_vector(driver, query_text, top_k=2)

        prompt = f"context: {context}\n\n질문: {query_text}"
        response = llm.invoke(prompt)

        print(response)
        
        return response
        
    except Exception as e:
        error_msg = f"오류가 발생했습니다: {str(e)}"
        print(error_msg)
        return error_msg

if __name__ == "__main__":
    mcp.run(transport="stdio")