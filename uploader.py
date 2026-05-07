import os
import re
import json
import fitz
import google.generativeai as genai
from tqdm import tqdm
from pathlib import Path
import subprocess
from PIL import Image
import io

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("已加载 .env 文件")
except ImportError:
    print("提示：未安装 python-dotenv，将使用环境变量或命令行参数")

def configure_gemini(api_key):
    """
    配置 Google Gemini API
    """
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

def extract_course_number(filename):
    """
    从文件名中提取课程编号（L01, L02 等）
    """
    match = re.search(r'L(\d{2})', filename)
    if match:
        return f"L{match.group(1)}"
    return "L00"

def is_likely_logo(image_bytes, min_size_kb=10, min_width=200, min_height=200):
    """
    判断图片是否可能是 logo 等无关图片

    Args:
        image_bytes: 图片二进制数据
        min_size_kb: 最小文件大小（KB）
        min_width: 最小宽度（像素）
        min_height: 最小高度（像素）

    Returns:
        如果可能是 logo 则返回 True，否则返回 False
    """
    try:
        size_kb = len(image_bytes) / 1024
        
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            aspect_ratio = width / height if height > 0 else 0
            
            if size_kb < min_size_kb:
                return True
            
            if width < min_width and height < min_height:
                return True
            
            if aspect_ratio > 2.5 or aspect_ratio < 0.4:
                return True
            
            img = img.convert('RGB')
            pixels = img.getcolors(width * height)
            if pixels:
                color_count = len(pixels)
                if color_count < 10:
                    return True
            
            total_pixels = width * height
            dominant_color, count = pixels[0] if pixels else (None, 0)
            if dominant_color and count / total_pixels > 0.7:
                return True
                
    except Exception:
        pass
    
    return False

def extract_images_from_pdf(pdf_path, output_dir, filter_logo=True):
    """
    使用 PyMuPDF 从 PDF 中提取所有图片

    Args:
        pdf_path: PDF 文件路径
        output_dir: 图片输出目录
        filter_logo: 是否筛选掉 logo 等无关图片

    Returns:
        包含图片信息的列表
    """
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

            if filter_logo and is_likely_logo(image_bytes):
                continue

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
    """
    使用 Gemini 2.0 Flash 分析图片中的题目内容

    Args:
        model: 已配置的 Gemini 模型
        image_path: 图片路径

    Returns:
        包含题目分析结果的字典
    """
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

def push_to_github(local_repo_path, commit_message="Update question bank"):
    """
    使用 Git 命令将本地更改推送到 GitHub 仓库

    Args:
        local_repo_path: 本地仓库路径（包含 .git 文件夹）
        commit_message: 提交信息

    Returns:
        是否成功
    """
    try:
        os.chdir(local_repo_path)

        subprocess.run(['git', 'add', 'dist/'], check=True, capture_output=True)

        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            print("没有检测到文件变更，跳过提交")
            return True

        subprocess.run(['git', 'commit', '-m', commit_message], check=True, capture_output=True, text=True)

        subprocess.run(['git', 'push'], check=True, capture_output=True, text=True)

        print("成功推送到 GitHub！")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Git 操作失败: {e}")
        if e.stderr:
            print(f"错误详情: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}")
        return False
    except Exception as e:
        print(f"推送失败: {e}")
        return False

def process_pdf_files(base_dir, api_key, github_repo_path=None, auto_push=False, filter_logo=True):
    """
    处理 PDF 文件并提取题目数据

    Args:
        base_dir: PDF 文件所在目录
        api_key: Gemini API 密钥
        github_repo_path: GitHub 仓库本地路径（用于推送）
        auto_push: 是否处理完成后自动推送到 GitHub
        filter_logo: 是否筛选掉 logo 等无关图片
    """
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

        images = extract_images_from_pdf(pdf_path, images_dir, filter_logo=filter_logo)
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

    if auto_push and github_repo_path:
        print("\n正在推送到 GitHub...")
        push_to_github(github_repo_path)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='处理 AMC8 PDF 题库并可选推送到 GitHub',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  1. 仅处理 PDF 文件:
     python uploader.py --api-key YOUR_GEMINI_KEY --base-dir "P:\\documents\\AMC8"

  2. 处理后推送到 GitHub:
     python uploader.py --api-key YOUR_GEMINI_KEY --base-dir "P:\\documents\\AMC8" \\
                        --github-repo "C:\\path\\to\\your\\repo" --auto-push

  3. 使用环境变量存储 API Key:
     python uploader.py --base-dir "P:\\documents\\AMC8"
     (需要设置环境变量 GEMINI_API_KEY)

GitHub Personal Access Token (PAT) 配置方法:
  1. 登录 GitHub (https://github.com)
  2. 点击右上角头像 -> Settings
  3. 左侧菜单找到 "Developer settings"
  4. 点击 "Personal access tokens" -> "Tokens (classic)"
  5. 点击 "Generate new token" -> "Generate new token (classic)"
  6. 配置选项:
     - Note: 填写令牌描述，如 "AMC8 Uploader Script"
     - Expiration: 选择过期时间，建议 30-90 天
     - Select scopes: 勾选 "repo" (完全控制私有仓库)
  7. 点击 "Generate token"
  8. 重要：立即复制并保存令牌！页面刷新后将无法查看

  配置凭据的方式（选择一种）:
  A. 命令行输入（每次运行时）:
     python uploader.py --github-token ghp_xxxxxx ...

  B. 环境变量（推荐，更安全）:
     - Windows PowerShell: $env:GITHUB_TOKEN = "ghp_xxxxxx"
     - Windows CMD: set GITHUB_TOKEN=ghp_xxxxxx
     - 或在 Python 代码中: os.environ['GITHUB_TOKEN'] = 'ghp_xxxxxx'

  C. Git 凭据管理器（持久化）:
     git config --global credential.helper store
     echo "https://ghp_xxxxxx@github.com" > ~/.git-credentials

  D. 使用 .env 文件 + python-dotenv:
     在项目根目录创建 .env 文件:
     GITHUB_TOKEN=ghp_xxxxxx
     GEMINI_API_KEY=your_gemini_key
        """
    )

    parser.add_argument('--api-key', '--gemini-key',
                        help='Google Gemini API Key (也可通过 GEMINI_API_KEY 环境变量设置)')
    parser.add_argument('--base-dir', default=r'P:\documents\AMC8',
                        help='PDF文件所在目录')
    parser.add_argument('--github-token',
                        help='GitHub Personal Access Token (也可通过 GITHUB_TOKEN 环境变量设置)')
    parser.add_argument('--github-repo',
                        help='GitHub 仓库本地路径 (需要包含 .git 文件夹)')
    parser.add_argument('--auto-push', action='store_true',
                        help='处理完成后自动推送到 GitHub')
    parser.add_argument('--no-filter-logo', action='store_true',
                        help='不筛选 logo 等小图片（默认会筛选）')

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('GEMINI_API_KEY')
    github_token = args.github_token or os.environ.get('GITHUB_TOKEN')

    if not api_key:
        print("错误：未提供 Gemini API Key")
        print("请通过 --api-key 参数或 GEMINI_API_KEY 环境变量提供")
        exit(1)

    if not os.path.exists(args.base_dir):
        print(f"错误：目录不存在: {args.base_dir}")
        exit(1)

    if args.auto_push and args.github_repo:
        if not github_token:
            print("错误：启用了 --auto-push 但未提供 GitHub Token")
            print("请通过 --github-token 参数或 GITHUB_TOKEN 环境变量提供")
            exit(1)

        if not os.path.exists(os.path.join(args.github_repo, '.git')):
            print(f"错误：目录不是 Git 仓库: {args.github_repo}")
            exit(1)

        repo_url = subprocess.run(
            ['git', '-C', args.github_repo, 'remote', 'get-url', 'origin'],
            capture_output=True, text=True
        ).stdout.strip()

        if 'github.com' in repo_url and '@' not in repo_url:
            tokenized_url = repo_url.replace(
                'https://github.com/',
                f'https://{github_token}@github.com/'
            )
            subprocess.run(
                ['git', '-C', args.github_repo, 'remote', 'set-url', 'origin', tokenized_url],
                check=True, capture_output=True
            )

    filter_logo = not args.no_filter_logo
    process_pdf_files(args.base_dir, api_key, args.github_repo, args.auto_push, filter_logo=filter_logo)
    print("\n处理完成！")
