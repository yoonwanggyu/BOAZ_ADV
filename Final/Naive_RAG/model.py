from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI

# 알아서 사용하고픈 모델 설정
# def create_model():
#     return ChatOllama(model="exaone3.5:7.8b", 
#                       temperature=0.5)

def create_model():
    return ChatOpenAI(temperature=0,
                      model_name="gpt-4o")