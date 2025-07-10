import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig
from trl import SFTTrainer
import huggingface_hub
from dotenv import load_dotenv

# 0) 환경 변수 & HF 로그인 (허깅페이스 API TOKEN 발급) 
load_dotenv()
huggingface_hub.login(os.getenv("HF_TOKEN"))

# 1) 설정 
base_model     = "meta-llama/Llama-3.2-1B" # 베이스 모델
dataset_path   = "/home/work/BOAZ_ADV/학술지_Llama3_Fine-tuning_Dataset.jsonl" # Custom Dataset
new_model_name = "llama3.2-1b-boaz-medical" # 출력 모델 이름 설정

# 2) JSONL 로드(우리는 전체를 train set으로 쓰고, shuffle해서 데이터 샘플 간 순서 섞기)
ds = load_dataset(
    "json",
    data_files={"train": dataset_path},
    split="train"
).shuffle()

# 3) QLoRA용 4-bit 양자화 설정
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,               # 4bit로 모델 가중치를 로드하여 메모리 사용량 크게 절감
    bnb_4bit_quant_type="nf4",       # NF4(NormalFloat4) 양자화 방식 사용
    bnb_4bit_compute_dtype=torch.float16,  # 내부 계산 시 float16 포맷 사용
    bnb_4bit_use_double_quant=False, # 이중 양자화(double quantization)는 미적용
)

# 4) 모델 로드
model = AutoModelForCausalLM.from_pretrained(
    base_model,                      # 사전학습된 LLaMA-3.2 1B 모델 식별자
    trust_remote_code=True,          # 모델 저장소의 custom code(예: Llama-3 사용자 정의)를 허용
    quantization_config=quant_config,# 위에서 생성한 4bit 양자화 설정 적용
    device_map="auto",               # 사용 가능한 GPU/CPU 장치에 자동으로 분산 배치
)

# LoRA fine-tuning 시 반드시 끄기
model.config.use_cache = False       # generation시 사용하는 past_key/value 캐시 비활성화
model.config.pretraining_tp = 1      # tensor parallelism을 1로 고정(단일 GPU 모드)

# 5) 토크나이저 로드
tokenizer = AutoTokenizer.from_pretrained(
    base_model,                      # 동일한 base_model에서 토크나이저 불러오기
    trust_remote_code=True,          # custom tokenizer 코드 허용
)

tokenizer.pad_token    = tokenizer.eos_token  # 패딩 토큰을 eos_token과 동일하게 설정
tokenizer.padding_side = "right"              # 오른쪽에 패딩 추가

# 6) LoRA(PEFT) 설정
peft_config = LoraConfig(
    task_type="CAUSAL_LM",   # LoRA 적용 - 답변 생성 Task
    inference_mode=False,    # 학습 모(LoRA 가중치 학습 허용)
    r=32,                    # LoRA low-rank 차원(rank) -> 작을수록 메모리·연산량 감소
    lora_alpha=16,           # LoRA 스케일링 계수(alpha) -> 작을수록 보수적으로 학습
    lora_dropout=0.1,        # 10% 드롭아웃으로 과적합 방지
    bias="none",             # LoRA 어댑터에는 편향(bias) 레이어 비활성화(편향까지 추가하면 불안정해질 수 있음)
)

# 7) 학습 인자
training_args = TrainingArguments(
    output_dir="./results_llama3_1b",     # 체크포인트와 로그 저장 디렉터리
    per_device_train_batch_size=1,        # GPU 당 배치 사이즈, 실제 GPU 하나당 매 스텝에 1개 샘플을 로드
    gradient_accumulation_steps=8,        # 매 8 스텝마다 한 번씩 역전파를 수행해 효과적으로 배치 크기를 8로 늘린 것과 같음
    num_train_epochs=3,                   # 전체 데이터를 3회 반복 학습
    learning_rate=2e-4,                   # 학습률 0.0002
    optim="paged_adamw_32bit",            # 32-bit AdamW 옵티마이저 (사용 빈도가 낮은 파라미터 페이지(메모리 블록)를 자동으로 CPU 메모리나 디스크로 옮겼다가, 필요할 때만 GPU로 불러오는 방식)
    fp16=True,                            # FP16 mixed-precision 활성화
    bf16=False,                           # BF16 사용 안 함
    save_steps=50,                        # 50 스텝마다 모델 저장
    logging_steps=50,                     # 50 스텝마다 로깅
    weight_decay=0.01,                    # 가중치 감쇠 0.01, L2계수
    warmup_ratio=0.03,                    # 전체의 3%만큼 워밍업 단계, 워밍업 단계에 learning rate를 선형 증가시켜 안정적인 학습을 도움
    max_grad_norm=0.3,                    # 그래디언트 클리핑 최대 L2 노름 0.3
    lr_scheduler_type="constant",         # constant : 학습 내내 고정된 학습률을 사용
    report_to="tensorboard",              # 텐서보드로 로그 전송
    group_by_length=True,                 # 길이가 비슷한 시퀀스끼리 묶어서 배치로 구성, 패딩 최소화
)

# 7) SFTTrainer 생성
trainer = SFTTrainer(
    model=model,                       # fine-tune할 모델
    train_dataset=ds,                  # 학습 데이터셋
    peft_config=peft_config,           # LoRA 설정
    dataset_text_field="text",         # 데이터셋 텍스트 필드 이름
    tokenizer=tokenizer,               # 토크나이저
    args=training_args,                # 학습 인자
    packing=False,                     # packing 비활성화(토크나이저 별도, 문장별 경계를 명확히 유지해야 할 때 주로 사용)
)

# 8) 학습 & 저장
trainer.train()                       # Fine-tuning 시작
trainer.save_model(new_model_name)    # 학습된 LoRA 어댑터 + Config 저장
print("✅ Fine-tuning 완료. Saved to:", new_model_name)