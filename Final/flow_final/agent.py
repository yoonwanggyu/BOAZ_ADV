from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 환경변수 설정
load_dotenv()

# 베이스 LLM 설정
model = ChatOpenAI(temperature=0.2, model = "gpt-4o") # 보수적인 답변을 위해 temperature는 0.2로 제한