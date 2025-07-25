from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 환경변수 설정
load_dotenv()

# 답변용 OpenAI LLM 설정
model = ChatOpenAI(temperature=0.2, model = "gpt-4.1") # 보수적인 답변을 위해 temperature는 0.2로 제한