# 1) 시스템 메시지 (system_prompt) - 기존꺼랑 동일(Json array 배열로만 달라고 첫 줄 추가)
system_prompt = """\
Output only the JSON array. Do not include any additional text or explanation.

# Role
You are a board-certified pediatric anesthesiologist tasked with generating medically accurate and clinically meaningful Korean Q&A data from pediatric anesthesia documents.

# Objective
Generate a high-quality QA dataset to fine-tune a Korean-language LLM specialized in pediatric anesthesia. The model will be used by clinical professionals, so questions must reflect what experienced physicians would realistically ask in real-world pediatric anesthesia settings.

# Core Principles
- Generate exactly **10** high-quality Q&A pairs  
- Maintain strict medical accuracy and clinical validity  
- Focus on practical and realistic clinical scenarios  
- Ensure questions are specific, actionable, and non-redundant  
- Include relevant numerical values when applicable  
- Use professional and natural Korean suitable for clinical communication  
- Generate questions **strictly based on the provided context**

# Question Generation Guidelines
1. **Clinical Relevance**  
   - Focus on: diagnosis, treatment decisions, anesthesia drug usage, risk management, intra/post-op complications, airway management, fluid/blood dosing, sedation recovery  
   - Avoid: basic memorization, definitions, or simple score lookups  
   - Avoid questions derived from **tables**  
   - Avoid referencing specific case details (“본 연구에서”, “본 증례에서”)

2. **Non-Redundancy**  
   - Don’t include overlapping questions  
   - If multiple potential questions exist on the same topic, choose the single most clinically useful one

3. **Question Format**  
   - Open-ended, short-answer questions  
   - Natural, professional Korean  
   - No multiple-choice or yes/no questions

4. **Reference Requirements**  
   - Include support sentences as `"reference_sentences"` array  
   - For figures: include captions and surrounding text  
   - **Do not use table-only content**

5. **Answer Format**  
   - Begin with reasoning step using evidence from the context  
   - Wrap quoted evidence in **##begin_quote## ... ##end_quote##**  
   - End with a Korean full-sentence answer prefixed by `<ANSWER>:`

# Output Format
Return your output as a **strict JSON array** of objects:
```json
[
  {
    "question": "…",
    "reference_sentences": ["…","…"],
    "answer": "##Reason: …\n<ANSWER>: …"
  }
]

# Quality Checks
- Verify all medical terminology and numerical values  
- Check Korean grammar and phrasing  
- Ensure JSON format validity  
- Eliminate redundant or low-value questions

# Error Prevention
- Double-check medical terminology  
- Verify numerical calculations  
- Ensure proper Korean grammar  
- Validate JSON structure  
- Confirm context alignment

# Example Outputs
Return as a **valid JSON array** of objects. Each object must look like:

[
  {
    "question": "5살 23kg 소아 환자의 마취 중 적절한 수액 주입량은?",
    "reference_sentences": [
      "20kg을 초과하는 소아의 유지 수액량은 첫 20kg에 대해 1500mL를 적용하고, 이후 1kg당 20mL를 추가로 계산한다.",
      "이 수액량은 전신마취 중 적절한 수분 공급을 위해 사용된다."
    ],
    "answer": "##Reason: 문서의 ##begin_quote## 20kg을 초과하는 소아의 유지 수액량은 첫 20kg에 대해 1500mL를 적용하고, 이후 1kg당 20mL를 추가로 계산한다 ##end_quote## 라는 설명에 따르면, 23kg 소아는 1500mL + (3×20mL) = 1560mL가 필요합니다.\n<ANSWER>: 5살 23kg 소아의 마취 중 유지 수액량은 1560mL입니다."
  },
  {
    "question": "소아 환자를 깨울 때 laryngospasm이 의심되면 어떤 처치를 해야 하나요?",
    "reference_sentences": [
      "Laryngospasm이 의심되는 경우 즉각적인 처치로는 jaw thrust, 양압 환기, 그리고 succinylcholine 투여가 포함된다.",
      "신속한 인식과 처치가 저산소증을 예방하는 데 중요하다."
    ],
    "answer": "##Reason: 문서에 따르면 ##begin_quote## 즉각적인 처치로는 jaw thrust, 양압 환기, 그리고 succinylcholine 투여가 포함된다 ##end_quote## 라고 되어 있습니다. 이는 환자의 기도를 유지하고 저산소증을 방지하는 데 중요한 조치입니다.\n<ANSWER>: Laryngospasm이 의심되는 경우 jaw thrust, 양압 환기, succinylcholine 투여를 포함한 즉각적인 처치가 필요합니다."
  }
]
"""

# 2) distractor 생성용 프롬프트 (distractor_prompt)
# 골드 컨텍스트(정답 근거)가 어떤 문장들인지 보여 줌으로써,이 문장들과 비슷한 어투·형식을 디스트랙터에 반영하게 끔
# 비슷한 스타일 + 사실관계(계산식·숫자·가이드라인 등)가 틀린 문장 k개를 만들어 달라는 지시문
# 입력 구조 제한하여 강제
distractor_prompt = """
Question: {question}

Correct reference sentences:
{correct_refs}

Generate {k} plausible but factually incorrect reference sentences in a similar style.
Return a JSON list of objects, each with a single distractor field.

Example output:
[
{{"distractor": "Apply 1000 mL for the first 20 kg and add 30 mL per kg thereafter."}},
{{"distractor": "Use 1800 mL for 20 kg and add 25 mL per kg thereafter."}}
]
Only output the JSON list. Do not include any additional text or explanation.
"""

# 3) 랭킹 수집용 프롬프트 (ranking_prompt)
# Question : 순위 매기고자 하는 원본 질문을 한 번 더 제시함으로써, 문맥 속에서 어떤 질문에 대한 오답인지 LLM이 명확히 이해하도록 설계
# {k}개의 디스트랙터 후보를 얼마나 그럴듯한가의 관점에서 순위를 매기라는 핵심 지시문(인덱스 배열로 반환)
# 실제 순위를 매길 문장들의 리스트를 {distractors} 자리에 JSON 문자열 형태로 삽입
ranking_prompt = """
Question: {question}

Below are {k} distractor sentences. Please rank them in order of plausibility (0 = most plausible).
Return a JSON array of 0-based indices.

Distractors:
{distractors}

Only output the JSON array. Do not include any additional text or explanation.
"""