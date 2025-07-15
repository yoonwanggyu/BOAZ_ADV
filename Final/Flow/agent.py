from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv("/Users/yoon/BOAZ_ADV/Wang_Gyu/code/mcp/.env")

model = ChatOpenAI(temperature=0.2,
                    model_name="gpt-4.1")