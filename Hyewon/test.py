import requests
from dotenv import load_dotenv
import os

# API 키 정보 로드
load_dotenv()

# upstage 불러오기
analyzer_api = os.environ.get("UPSTAGE_API_KEY")
print(analyzer_api)

file_path = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818016300204-main.pdf"

# API 요청 보내기
response = requests.post(
    "https://api.upstage.ai/v1/document-ai/layout-analysis",
    headers = {"Authorization": f"Bearer {analyzer_api}"},
    data={"ocr": False},
    files={"document": open(file_path, "rb")})

print("Response Status Code:", response.status_code)  # ✅ API 응답 상태 코드 확인
print("Response JSON:", response.json())  # ✅ 응답 내용 출력