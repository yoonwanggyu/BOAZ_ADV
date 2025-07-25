from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP
from embedder import *
from dotenv import load_dotenv
import os
import time

load_dotenv()

embedder = SMCEmbeddings(model="text-embedding-3-large", 
                         dimensions=256, 
                         api_key=os.getenv("OPENAI_API_KEY"))

NEO4J_URI = "neo4j+s://fbc3f4e2.databases.neo4j.io"
AUTH = ("neo4j", "VoHB3kKRDdUoX7jvbGnTr4toga6-MNlvFyN3HIIsoyE")
DATABASE = "neo4j"

# Neo4j 연결
driver = GraphDatabase.driver(NEO4J_URI, auth=AUTH)

# LLM 설정 (올바른 모델명 사용)
llm = OpenAILLM(model_name="gpt-4o-mini", model_params={"temperature": 0.1})

# 벡터 기반 검색기 설정
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

# elementId로 1-hop 연결 정보 가져오는 함수
def get_node_with_neighbors(driver, element_id):
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

# context 생성 함수
def build_context_from_vector(driver, query_text: str, top_k: int = 5) -> str:
    print(f"\n[Context Builder] 시작 - Query: '{query_text}', Top-k: {top_k}")
    total_start = time.time()
    
    # 1. query_text를 embedding으로 변환
    print("Step 1: Embedding 생성 중...")
    embed_start = time.time()
    query_vector = embedder.embed_query(query_text, dimensions=256)
    embed_time = time.time() - embed_start
    print(f"Embedding 완료 - 시간: {embed_time:.2f}초")

    # 2. search 시 query_text는 제거하고 query_vector만 전달
    print("Step 2: Vector 검색 중...")
    search_start = time.time()
    retriever_result = retriever.search(query_vector=query_vector, top_k=top_k)
    search_time = time.time() - search_start
    print(f"    Vector 검색 완료 - 시간: {search_time:.2f}초")
    print(f"   검색 결과 수: {len(retriever_result.items)}개")
    
    # 검색 결과 상세 출력
    for i, item in enumerate(retriever_result.items):
        score = getattr(item, 'score', 'N/A')
        element_id = item.metadata.get('id', 'Unknown')
        print(f"      [{i+1}] Element ID: {element_id}, Score: {score}")

    # 3. 1-hop 확장
    print("Step 3: 1-hop 노드 확장 중...")
    expand_start = time.time()
    expanded_contexts = []

    for i, item in enumerate(retriever_result.items):
        element_id = item.metadata['id']
        print(f"   [{i+1}/{len(retriever_result.items)}] Element ID: {element_id} 처리 중...")
        
        node_start = time.time()
        node_info = get_node_with_neighbors(driver, element_id)
        node_time = time.time() - node_start
        
        if node_info:
            start_node = node_info['starting_node']
            neighbors_count = len(node_info['neighbors'])
            print(f"      노드 '{start_node.get('name', 'Unknown')}' 처리 완료")
            print(f"       - 이웃 노드 수: {neighbors_count}개")
            print(f"       - 처리 시간: {node_time:.2f}초")
            expanded_contexts.append(node_info)
        else:
            print(f"      노드 정보를 찾을 수 없음 - 시간: {node_time:.2f}초")
    
    expand_time = time.time() - expand_start
    print(f"   1-hop 확장 완료 - 시간: {expand_time:.2f}초")
    print(f"   성공적으로 확장된 노드 수: {len(expanded_contexts)}개")

    # 4. Context 구성
    print("Step 4: Context 텍스트 구성 중...")
    context_start = time.time()
    context_lines = []
    total_neighbors = 0
    
    for ctx_idx, ctx in enumerate(expanded_contexts):
        start = ctx['starting_node']
        start_name = start.get('name', 'Unknown')
        start_labels = [l for l in start.get('labels', []) if l not in {'__KGBuilder__', '__Entity__'}]
        context_lines.append(f"starting_node: {start_name} ({', '.join(start_labels)})")
        
        neighbors_count = len(ctx['neighbors'])
        total_neighbors += neighbors_count
        print(f"   [{ctx_idx+1}] '{start_name}' - 이웃 {neighbors_count}개 처리 중...")

        for neighbor in ctx['neighbors']:
            labels = [l for l in neighbor.get('neighbor_labels', []) if l not in {'__KGBuilder__', '__Entity__'}]
            label_str = f"[{', '.join(labels)}]" if labels else "[Unknown]"

            # Chunk 노드면 텍스트, 아니면 name
            if 'Chunk' in neighbor.get('neighbor_labels', []):
                neighbor_value = neighbor.get('text', 'None')
                # 텍스트가 너무 길면 일부만 표시
                display_value = neighbor_value[:50] + "..." if len(neighbor_value) > 50 else neighbor_value
                print(f"      Chunk 노드: {display_value}")
            else:
                neighbor_value = neighbor.get('neighbor_name', 'None')
                print(f"      Entity 노드: {neighbor_value}")

            relation = neighbor.get('relation', 'UNKNOWN_RELATION')
            direction = neighbor.get('direction', 'out')

            if direction == 'out':
                triple = f"({start_name}, {relation}, {neighbor_value})"
            else:
                triple = f"({neighbor_value}, {relation}, {start_name})"

            context_lines.append(f"{label_str} : \"{neighbor_value}\" {triple}")

    return "\n".join(context_lines)

@mcp.tool()
# Neo4j 데이터베이스에서 컨텍스트를 검색하고 LLM으로 답변을 생성
def run_contextual_rag(query_text: str):
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