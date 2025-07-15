from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv("/Users/daeunbaek/nuebaek/BOAZ/BOAZ_ADV/Daeun/.env")

model = ChatOpenAI(temperature=0.2,
                    model_name="gpt-4.1")