from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain_community.llms import HuggingFacePipeline

# 1) Ollama
def create_ollama_model():
    return ChatOllama(model="exaone3.5:7.8b", 
                      temperature=0.5)

# 2) GPT
def create_GPT_model():
    return ChatOpenAI(temperature=0,
                      model_name="gpt-4o")

# 3) HuggingFace
def create_llama_model():
    model_id = "meta-llama/Llama-3.2-1B-Instruct"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto")

    tokenizer = AutoTokenizer.from_pretrained(model_id)

    pipe = pipeline(
                    "text-generation",
                    model=model,
                    tokenizer=tokenizer,
                    max_new_tokens=1024,
                    do_sample=True,
                    temperature=0.3,
                    pad_token_id=tokenizer.eos_token_id,
                    repetition_penalty=1.1)

    model = HuggingFacePipeline(pipeline=pipe)

    return model