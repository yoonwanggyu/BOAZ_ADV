from openai import OpenAI
import json
from tqdm import tqdm
import os
from dotenv import load_dotenv
import csv
from prompt import system_prompt

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))    # <-------------본인 API키

folder_path = ''   # <------------전처리한 데이터 폴더

output_csv_path = ""                          # <---------------최종 저장 경로
csv_rows = []

for file_name in tqdm(os.listdir(folder_path)):

    file_path = os.path.join(folder_path, file_name)

    with open(file_path, 'r', encoding='utf-8') as f:
        data = f.read()

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",  # 또는 gpt-4.0, gpt-3.5-turbo
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data}
            ],
            temperature=0.2
        )
        
        output = response.choices[0].message.content.strip()
        qna_list = json.loads(output,strict=False)

        for qna in qna_list:
            question = qna['question']
            reference_sentences = qna['reference_sentences']
            answer = qna['answer']
            csv_rows.append([file_name, question, reference_sentences, answer])

    except Exception as e:
        print(f"❌ Error processing {file_name}: {e}")
        continue

# 5. 최종 CSV 저장
with open(output_csv_path, "w", newline='', encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["파일명", "질문", "관련 문서", "답변"])  # 헤더
    writer.writerows(csv_rows)

print(f"✅ CSV 저장 완료: {output_csv_path}")
