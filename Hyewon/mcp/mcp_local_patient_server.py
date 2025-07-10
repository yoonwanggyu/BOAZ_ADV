from mcp.server.fastmcp import FastMCP
import json
import os
import sys

# UTF-8 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')
sys.stdin.reconfigure(encoding='utf-8')

# JSON 파일 로드
json_path = "local_patient_cases.json"
with open(json_path, 'r', encoding='utf-8') as f:
    patient_data = json.load(f)

# # MCP 서버 생성
# mcp = FastMCP(
#     "Local_Patient_Retriever",
#     instructions="Retrieve patient case information from a local JSON file based on case number or other identifiers."
# )

# # MCP tool
# @mcp.tool()
# async def local_patient_retriever(case_number: str = "", full_name: str = ""):
#     try:
#         for case in patient_data:
#             if case.get('case') == case_number or case.get('full_name') == full_name:
#                 return case
#         return {"error": f"No patient found with case: {case_number or full_name}"}
#     except Exception as e:
#         return {"error": str(e)}

# # MCP 실행
# if __name__ == "__main__":
#     print("mcp local patient server start!")
#     mcp.run(transport="stdio")



# MCP 서버 생성
mcp = FastMCP(
    "Local_Patient_Retriever",
    instructions=(
        "Retrieve patient case information from a local JSON file. "
        "You can search by case_number or by full_name."
    )
)

# MCP tool: 이제 case_number 와 full_name 둘 다 받습니다.
@mcp.tool()
async def local_patient_retriever(case_number: str = "", full_name: str = ""):
    """
    환자 케이스 번호(case) 혹은 full_name 으로 로컬 JSON 데이터에서 검색
    """
    # 1) case_number 로 우선 검색
    if case_number:
        for case in patient_data:
            if case.get("case") == case_number:
                return case

    # 2) full_name 으로 대체 검색
    if full_name:
        for case in patient_data:
            if case.get("full_name") == full_name:
                return case

    # 둘 다 매칭되지 않으면 에러 리턴
    return {
        "error": f"No patient found for case_number='{case_number}' full_name='{full_name}'"
    }

# MCP 실행
if __name__ == "__main__":
    print("✅ mcp local patient server start!")
    mcp.run(transport="stdio")

