import pymupdf4llm
import pathlib

pdf_path1 = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818016300204-main.pdf"
pdf_path2 = r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818022000101-main.pdf"

# metadata list & example data 
def show_metadata(docs):
    if docs:
        print("[metadata]")
        print(list(docs[0].metadata.keys()))
        print("-----------------")
        print("\n[examples]")
        max_key_length = max(len(k) for k in docs[0].metadata.keys())
        for k, v in docs[0].metadata.items():
            print(f"{k:<{max_key_length}} : {v}")

# Markdown 변환
llama_reader = pymupdf4llm.LlamaMarkdownReader()

# 페이지별로 저장된 Markdown 문서 객체 리스트
llama_docs1 = llama_reader.load_data(pdf_path1)
llama_docs2 = llama_reader.load_data(pdf_path2)

show_metadata(llama_docs1)
print("____________________________________________________")
show_metadata(llama_docs2)

# 모든 페이지의 텍스트를 리스트로 저장
doc_list = []
for doc in llama_docs2:
    doc_list.append(doc.text)
print(doc_list[2])




# 불필요한 metadata 정보 제거
# OCR로 추출된 텍스트 정리(공백, 특수 문자 등)
# 목차 감지 및 구조화("## Introduction" 같은 부분 정리)
# 페이지별 마크다운 개별 파일로 저장
# LlamaIndex에서 사용할 수 있도록 청킹된 텍스트를 JSON으로 저장

# PDF 파일을 Markdown 형식으로 변환 (pymupdf4llm)
# 페이지 별 데이터 청킹
# 텍스트 전처리 → 불필요한 공백, DOI, URL, 인용 삭제
# OCR을 활용하여 이미지 속 텍스트 추출 (pytesseract)
# 이미지 속 "Figure 2" 같은 항목이 본문 어디에서 설명되는지 매칭
# 결과물을 Markdown 및 JSON 파일로 저장


import pymupdf4llm
import re
import os
import json
from pathlib import Path
import pytesseract
from PIL import Image

# 1. PDF 파일 경로 설정
pdf_files = [
    r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818016300204-main.pdf",
    r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818022000101-main.pdf"
]

# 2. 결과 저장 디렉토리 생성
output_dir = Path("markdown_output") # 변환된 Markdown 파일 저장
image_dir = Path("extracted_images") # PDF에서 추출된 이미지 저장
output_dir.mkdir(exist_ok=True)
image_dir.mkdir(exist_ok=True)

# 3. PDF를 Markdown으로 변환
llama_reader = pymupdf4llm.LlamaMarkdownReader()

# 4. 텍스트 전처리
def preprocess_text(text):
    """ Markdown 데이터 정제 """
    text = re.sub(r"\n{3,}", "\n\n", text) 
    text = re.sub(r"\s{2,}", " ", text) # 불필요한 공백 → OCR 텍스트에서 연속된 공백을 하나로 변환
    text = re.sub(r"https?://\S+|doi:\S+", "", text) # 학술지 링크 및 DOI 정보 삭제
    text = re.sub(r"\[\d+\]", "", text) # 인용 각주 삭제
    return text.strip()

# 5. OCR로 이미지 속 텍스트 추출
def extract_text_from_image(image_path):
    """ OCR을 이용해 이미지 속 텍스트 추출 """
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="eng")  # 영어 OCR 적용
    return text.strip()

# 6. 특정 이미지 번호가 포함된 문단 찾기
# "Figure 2"나 "Fig. 2"라는 단어가 포함된 문단을 찾아서 해당 이미지와 연결
def find_related_text(page_text, figure_number):
    """
    "Figure 2", "Fig. 2" 같은 레퍼런스를 찾아 관련 문단을 반환
    """
    figure_patterns = [
        rf"Figure\s*{figure_number}",  # Figure 2
        rf"Fig\.\s*{figure_number}",  # Fig. 2
    ]

    # 문단 단위로 나누기
    paragraphs = page_text.split("\n\n")

    for para in paragraphs:
        if any(re.search(pattern, para, re.IGNORECASE) for pattern in figure_patterns):
            return para.strip()  # 해당 문단을 반환

    return "관련 문단을 찾을 수 없음"  # 만약 찾지 못하면 기본값 반환

# 7. PDF 변환 & 이미지 정보 추출
def process_pdf(pdf_path):
    """ PDF를 Markdown으로 변환하고 이미지 & 관련 텍스트 저장 """
    pdf_name = Path(pdf_path).stem  
    metadata_list = []  

    print(f"📖 변환 중: {pdf_name} ...")
    llama_docs = llama_reader.load_data(pdf_path, write_images=True, image_path=str(image_dir))

    # 전체 Markdown 저장
    full_markdown = "\n\n".join([doc.text for doc in llama_docs])
    full_markdown = preprocess_text(full_markdown)
    with open(output_dir / f"{pdf_name}.md", "w", encoding="utf-8") as f:
        f.write(full_markdown)
    print(f"전체 Markdown 저장 완료: {pdf_name}.md")

    # 페이지별 Markdown 저장 + 이미지 & 관련 텍스트 매칭
    for i, doc in enumerate(llama_docs):
        page_markdown = preprocess_text(doc.text)
        page_num = i + 1  

        # 개별 페이지 Markdown 저장
        with open(output_dir / f"{pdf_name}_page_{page_num}.md", "w", encoding="utf-8") as f:
            f.write(page_markdown)

        # 해당 페이지에서 저장된 이미지 찾기
        image_files = sorted(image_dir.glob(f"{pdf_name}-{page_num}-*.png"))
        for img_file in image_files:
            img_text = extract_text_from_image(img_file)  

            # OCR에서 "Figure 2" 같은 패턴 찾기
            match = re.search(r"Figure\s*(\d+)|Fig\.\s*(\d+)", img_text, re.IGNORECASE)
            figure_number = match.group(1) if match else None

            # "Figure X" 패턴이 있는 경우 관련 문단 찾기
            related_text = find_related_text(page_markdown, figure_number) if figure_number else "관련 문단 없음"

            # 이미지 메타데이터 저장
            metadata = {
                "image_file": img_file.name,
                "pdf_name": pdf_name,
                "page_number": page_num,
                "figure_number": figure_number,
                "related_text": related_text,
                "ocr_text": img_text
            }
            metadata_list.append(metadata)

    # 이미지 메타데이터 JSON 저장
    with open(output_dir / f"{pdf_name}_image_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=4, ensure_ascii=False)
    
    print(f"📄 페이지별 Markdown & 이미지 데이터 저장 완료: {pdf_name}")

# 8. 모든 PDF 변환 실행
for pdf in pdf_files:
    process_pdf(pdf)

print("모든 PDF 변환 및 이미지 메타데이터 저장 완료!")





#################################
## Recursive Character Text Split

import pymupdf
import pymupdf4llm
import re
import os
import json
from pathlib import Path
import pytesseract
from PIL import Image
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 1. PDF 파일 경로 설정
pdf_files = [
    r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818016300204-main.pdf",
    r"C:\Users\user\OneDrive\바탕 화면\BOAZ\2025_분석_ADV session\챗봇 프로젝트\GUIDELINES\1-s2.0-S0952818022000101-main.pdf"
]

# 2. 결과 저장 디렉토리 생성
output_dir = Path("markdown_output")  # 변환된 Markdown 저장
json_dir = Path("json_output")  # JSON 저장
image_dir = Path("extracted_images")  # PDF에서 추출된 이미지 저장
output_dir.mkdir(exist_ok=True)
json_dir.mkdir(exist_ok=True)
image_dir.mkdir(exist_ok=True)

# 3. PDF를 Markdown으로 변환하는 객체 생성
llama_reader = pymupdf4llm.LlamaMarkdownReader()

# 4. 텍스트 전처리 함수
def preprocess_text(text):
    """ Markdown 데이터 정제 """
    text = re.sub(r"\n{3,}", "\n\n", text)  # 개행 정리
    text = re.sub(r"\s{2,}", " ", text)  # 공백 정리
    text = re.sub(r"https?://\S+|doi:\S+", "", text)  # DOI, URL 삭제
    text = re.sub(r"\[\d+\]", "", text)  # 인용 각주 삭제
    return text.strip()

# 5. RecursiveCharacterTextSplitter 설정 (청킹)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # 한 청크의 최대 길이 (1000자)
    chunk_overlap=200,  # 청크 간 200자 겹침 → 문맥 유지
    length_function=len,
)

# 6. PDF 메타데이터 저장 함수
def save_metadata(pdf_path, llama_docs):
    """PDF에서 메타데이터를 추출하고 JSON으로 저장"""
    pdf_name = Path(pdf_path).stem  
    metadata_list = []

    for i, doc in enumerate(llama_docs):
        metadata = {
            "pdf_name": pdf_name,
            "page_number": i + 1,
            "title": doc.metadata.get("title", "Unknown"),
            "author": doc.metadata.get("author", "Unknown"),
            "subject": doc.metadata.get("subject", "Unknown"),
            "keywords": doc.metadata.get("keywords", "Unknown"),
            "modDate": doc.metadata.get("modDate", "Unknown"),
            "total_pages": doc.metadata.get("total_pages", "Unknown"),
            "file_path": pdf_path,
        }
        metadata_list.append(metadata)

    # JSON 파일로 저장
    metadata_path = json_dir / f"{pdf_name}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=4, ensure_ascii=False)

    print(f"메타데이터 저장 완료: {metadata_path}")

# 7. OCR로 이미지 속 텍스트 추출 함수
def extract_text_from_image(image_path):
    """ OCR을 이용해 이미지 속 텍스트 추출 """
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="eng")  # 영어 OCR 적용
    return text.strip()

# 8. PDF에서 이미지 추출 함수 (PyMuPDF)
def extract_images_from_pdf(pdf_path, output_dir):
    """ PDF에서 이미지를 추출하고 저장 """
    pdf_document = pymupdf.open(pdf_path)
    image_count = 0
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)  # 페이지 로드
        img_list = page.get_images(full=True)  # 이미지 목록 추출

        for img_index, img in enumerate(img_list):
            xref = img[0]
            image = pdf_document.extract_image(xref)
            image_bytes = image["image"]

            # 이미지 저장
            image_filename = output_dir / f"{Path(pdf_path).stem}_page_{page_num + 1}_img_{img_index + 1}.png"
            with open(image_filename, "wb") as img_file:
                img_file.write(image_bytes)
                image_count += 1

    return image_count

# 9. 표를 마크다운 형식으로 변환하는 함수
def convert_table_to_markdown(text):
    """텍스트에서 표 형식 찾고 마크다운으로 변환"""
    lines = text.splitlines()
    table = []
    
    for line in lines:
        if "|" in line:  # 표의 줄을 감지
            table.append(line.strip())
    
    if table:
        # 표 문법에 맞게 파이프 문자로 마크다운 테이블 생성
        markdown_table = "\n".join(table)
        return markdown_table
    else:
        return text  # 표가 없는 경우 원본 텍스트 반환

# 10. PDF 변환 & 청킹 & 이미지 처리 함수
def process_pdf(pdf_path):
    """ PDF를 Markdown으로 변환하고 RecursiveCharacterTextSplitter 적용 """
    pdf_name = Path(pdf_path).stem  
    print(f"변환 중: {pdf_name} ...")
    
    # 이미지 추출
    image_count = extract_images_from_pdf(pdf_path, image_dir)
    print(f"추출된 이미지 수: {image_count}")

    # PDF에서 텍스트 변환
    llama_docs = llama_reader.load_data(pdf_path, write_images=True, image_path=str(image_dir))
    full_text = "\n\n".join([doc.text for doc in llama_docs])
    clean_text = preprocess_text(full_text)
    
    # 표를 마크다운 문법으로 변환
    clean_text_with_tables = convert_table_to_markdown(clean_text)
    
    # 메타데이터 저장
    save_metadata(pdf_path, llama_docs)

    # RecursiveCharacterTextSplitter 적용 청킹
    chunks = text_splitter.split_text(clean_text_with_tables)

    # 전체 Markdown 저장
    with open(output_dir / f"{pdf_name}.md", "w", encoding="utf-8") as f:
        f.write(clean_text_with_tables)
    
    print(f"전체 Markdown 저장 완료: {pdf_name}.md")

    # 청크별 JSON 저장
    chunk_data = []
    for i, chunk in enumerate(chunks):
        chunk_info = {
            "chunk_id": i + 1,
            "pdf_name": pdf_name,
            "text": chunk
        }
        chunk_data.append(chunk_info)

    with open(json_dir / f"{pdf_name}_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunk_data, f, indent=4, ensure_ascii=False)

    print(f"청크 데이터 JSON 저장 완료: {pdf_name}_chunks.json")

# 11. 모든 PDF 변환 실행
for pdf in pdf_files:
    process_pdf(pdf)

print("모든 PDF 변환 및 청킹 완료!")

