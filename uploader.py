import os
import re
import json
import fitz
import google.generativeai as genai
from tqdm import tqdm
from pathlib import Path

def configure_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

def extract_course_number(filename):
    match = re.search(r'L(\d{2})', filename)
    if match:
        return f"L{match.group(1)}"
    return "L00"

def extract_images_from_pdf(pdf_path, output_dir):
    images = []
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            image_filename = f"page_{page_num + 1}_{img_index + 1}.{image_ext}"
            image_path = os.path.join(output_dir, image_filename)
            
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            images.append({
                "page_number": page_num + 1,
                "image_path": image_path,
                "image_filename": image_filename
            })
    
    doc.close()
    return images

def analyze_image_with_gemini(model, image_path):
    try:
        image = genai.upload_file(image_path)
        prompt = """
        请分析这张图片中的数学题目内容，返回以下格式的 JSON：
        
        {
            "question_text": "题目的完整文本内容",
            "knowledge_points": ["知识点1", "知识点2", "知识点3"],
            "difficulty": "简单|中等|困难",
            "difficulty_reason": "难度评估的理由"
        }
        
        注意：
        1. 题目文本要完整准确地包含所有题目内容和选项
        2. 知识点要具体，如"代数方程"、"几何图形"等
        3. 难度基于 AMC8 竞赛标准评估
        4. 必须返回有效的 JSON 格式，不要包含其他内容
        """
        
        response = model.generate_content([prompt, image])
        response.resolve()
        
        try:
            result = json.loads(response.text.strip())
            return result
        except json.JSONDecodeError:
            return {
                "question_text": response.text.strip(),
                "knowledge_points": [],
                "difficulty": "未知",
                "difficulty_reason": "解析失败"
            }
    except Exception as e:
        return {
            "question_text": "",
            "knowledge_points": [],
            "difficulty": "未知",
            "difficulty_reason": f"API调用失败: {str(e)}"
        }

def process_pdf_files(base_dir, api_key):
    model = configure_gemini(api_key)
    
    pdf_pattern = re.compile(r'^AMC8\s*L\d{2}.*\.pdf$', re.IGNORECASE)
    pdf_files = sorted([f for f in os.listdir(base_dir) if pdf_pattern.match(f)])
    
    if not pdf_files:
        print("未找到符合格式的PDF文件")
        return
    
    for pdf_file in pdf_files:
        course_num = extract_course_number(pdf_file)
        pdf_path = os.path.join(base_dir, pdf_file)
        
        images_dir = os.path.join(base_dir, "dist", "images", course_num)
        data_dir = os.path.join(base_dir, "dist", "data", course_num)
        
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        
        print(f"\n处理文件: {pdf_file}")
        print(f"课程编号: {course_num}")
        
        images = extract_images_from_pdf(pdf_path, images_dir)
        print(f"提取到 {len(images)} 张图片")
        
        questions_data = []
        
        for idx, image_info in enumerate(tqdm(images, desc=f"正在分析 {course_num}")):
            analysis = analyze_image_with_gemini(model, image_info["image_path"])
            questions_data.append({
                "page_number": image_info["page_number"],
                "image_filename": image_info["image_filename"],
                **analysis
            })
        
        json_path = os.path.join(data_dir, f"questions_{course_num}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(questions_data, f, ensure_ascii=False, indent=2)
        
        print(f"数据已保存到: {json_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='处理 AMC8 PDF 题库')
    parser.add_argument('--api-key', required=True, help='Google Gemini API Key')
    parser.add_argument('--base-dir', default=r'P:\documents\AMC8', 
                        help='PDF文件所在目录')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.base_dir):
        print(f"错误：目录不存在: {args.base_dir}")
        exit(1)
    
    process_pdf_files(args.base_dir, args.api_key)
    print("\n处理完成！")