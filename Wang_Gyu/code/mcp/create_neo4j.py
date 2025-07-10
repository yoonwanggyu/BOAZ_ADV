import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

# # ──────────────────────────────────────────────
# # 1. 설정
# # ──────────────────────────────────────────────
# CSV_PATH   = "/Users/yoon/BOAZ_ADV/Wang_Gyu/code/mcp/patient_data.csv"
NEO4J_URI  = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PW   = os.getenv("NEO4J_PASSWORD")

# # ──────────────────────────────────────────────
# # 2. CSV 로드
# # ──────────────────────────────────────────────
# df = pd.read_csv(CSV_PATH)

# # 간단한 성별 매핑(짝수: 남, 홀수: 여)
# df["성별"] = ["남" if i % 2 == 0 else "여" for i in range(len(df))]

# # ──────────────────────────────────────────────
# # 3. Cypher 템플릿
# # ──────────────────────────────────────────────
# CYTHER = """
# MERGE (p:Patient {name:$name})
#   ON CREATE SET
#       p.age         = $age,
#       p.gender      = $gender

# MERGE (g:Gender {type:$gender})
# MERGE (p)-[:HAS_GENDER]->(g)

# MERGE (d:Diagnosis {name:$symptom})
# MERGE (p)-[:HAS_DIAGNOSIS]->(d)

# MERGE (s:Surgery {name:$surgery})
#   ON CREATE SET s.detail = $detail
# MERGE (p)-[r:UNDERWENT]->(s)
#   ON CREATE SET
#       r.date        = date($date),
#       r.duration    = $duration

# WITH p
# MERGE (st:Status {desc:$post_status})
# MERGE (p)-[:POST_OP_STATUS]->(st)

# WITH p
# MERGE (note:IntraOpNote {desc:$intra_note})
# MERGE (p)-[:INTRA_OP_NOTE]->(note);
# """

# # ──────────────────────────────────────────────
# # 4. Neo4j 적재
# # ──────────────────────────────────────────────
# driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PW))

# with driver.session(database="neo4j") as session:  
#     for _, row in df.iterrows():
#         session.run(
#             CYTHER,
#             name        = row["환자 이름"],
#             age         = row["환자 나이"],
#             gender      = row["성별"],
#             symptom     = row["환자 증상"],
#             surgery     = row["환자 수술명"],
#             detail      = row["수술 내용"],
#             date        = row["환자 수술 날짜"],
#             duration    = row["환자 총 수술 시간"],
#             post_status = row["수술 후 상태"],
#             intra_note  = row["수술 중 특이사항"],
#         )
# driver.close()
# print("✅  데이터 적재 완료!")

# 환자 나이 + 환자 증상 + 환자 수술명 + 수술 내용 + 수술 중 특이사항 묶어서 임베딩 
# from sentence_transformers import SentenceTransformer
# import numpy as np
# from tqdm import tqdm
# import pandas as pd
# from neo4j import GraphDatabase
# import os
# from openai import OpenAI

# CSV_PATH   = "/Users/yoon/BOAZ_ADV/Wang_Gyu/code/mcp/patient_data.csv"
# NEO4J_URI  = os.getenv("NEO4J_URI")
# NEO4J_USER = os.getenv("NEO4J_USERNAME")
# NEO4J_PW   = os.getenv("NEO4J_PASSWORD")
# OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# client = OpenAI(api_key=OPENAI_KEY)

# # ───────────────────────── 1. CSV 로드 ─────────────────────────
# df = pd.read_csv(CSV_PATH)

# # ───────────────────────── 2. 임베딩 함수 ─────────────────────────
# def embed_large(text: str) -> list[float]:
#     resp = client.embeddings.create(
#         model="text-embedding-3-large",   # 3072 차원
#         input=text.replace("\n", " ")[:8192]
#     )
#     return resp.data[0].embedding  # list[float] 반환

# # ───────────────────────── 3. Neo4j 연결 ─────────────────────────
# driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PW))

# UPDATE_CYPHER = """
# MATCH (p:Patient {name:$name})
# SET   p.embedding = $vec
# """

# with driver.session(database="neo4j") as session:
#     for _, row in tqdm(df.iterrows(), total=len(df)):
#         # 원하는 5개 필드만 합쳐 임베딩
#         text = " ".join([
#             str(row["환자 나이"]),
#             row["환자 증상"],
#             row["환자 수술명"],
#             row["수술 내용"],
#             row["수술 중 특이사항"]
#         ])
#         print(text)
#         vec = embed_large(text)
#         session.run(UPDATE_CYPHER, name=row["환자 이름"], vec=vec)

# driver.close()
# print("✅  text-embedding-3-large 벡터 저장 완료!")

from neo4j import GraphDatabase
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PW))
with driver.session(database="neo4j") as s:
    rec = s.run("""
        CALL dbms.components() YIELD name, versions
        RETURN name, versions
    """).single()
    print(rec["name"], rec["versions"][0])   # Neo4j/5.11.0