from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 환경변수 설정
load_dotenv()

# 베이스 LLM 설정
model = ChatOpenAI(temperature=0.1, model = "gpt-4o")