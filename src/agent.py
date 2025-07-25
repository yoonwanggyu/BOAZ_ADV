from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

model = ChatOpenAI(temperature=0.2, 
                   model = "gpt-4.1") 