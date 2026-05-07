"""
AMC 8 智学助手 —— 风趣幽默的数学竞赛教练
技术栈: Streamlit + Google Gemini API (Vision) + edge-tts (语音)
部署: Streamlit Cloud
特性: 移动端优化、语音朗读、幽默名师人设、云端题库支持、网页端入库
"""

import streamlit as st
import base64
import re
import io
import asyncio
import tempfile
import os
import json
import requests
from urllib.parse import quote
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ──────────────────────────────────────────────
# PDF 处理依赖
# ──────────────────────────────────────────────
try:
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ──────────────────────────────────────────────
# PyMuPDF 依赖
# ──────────────────────────────────────────────
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ──────────────────────────────────────────────
# Gemini API 依赖
# ──────────────────────────────────────────────
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ──────────────────────────────────────────────
# 语音合成依赖
# ──────────────────────────────────────────────
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

# ──────────────────────────────────────────────
# 云端题库配置
# ──────────────────────────────────────────────
GITHUB_BASE_URL = "https://raw.githubusercontent.com/hzbeck7/AMC8-math-learner/main/data/questions"
GITHUB_API_URL = "https://api.github.com/repos/hzbeck7/AMC8-math-learner/contents/data/questions"
COURSES = [f"L{i:02d}" for i in range(1, 14)]  # L01 到 L13

# ──────────────────────────────────────────────
# 页面配置
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="AMC 8 智学助手",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# 自定义 CSS
# ──────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    .stApp {
        font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
        font-size: 16px;
    }
    
    @media screen and (max-width: 768px) {
        .stApp { font-size: 15px; }
        .app-title h1 { font-size: 1.8rem !important; }
        .app-title p { font-size: 0.95rem !important; }
    }

    .app-title {
        text-align: center;
        padding: 1.2rem 0 0.5rem 0;
    }
    .app-title h1 {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .app-title p {
        font-size: 1.05rem;
        color: #6b7280;
    }

    .voice-btn {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.6rem 1.2rem;
        font-size: 0.95rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        margin: 0.5rem 0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .voice-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(245, 87, 108, 0.4);
    }

    .module-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-left: 5px solid;
    }
    
    @media screen and (max-width: 768px) {
        .module-card {
            padding: 1rem 1.2rem !important;
            margin-bottom: 0.8rem !important;
        }
    }

    .card-theater { border-left-color: #f59e0b; background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%); }
    .card-knowledge { border-left-color: #3b82f6; background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%); }
    .card-steps { border-left-color: #10b981; background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%); }
    .card-bonus { border-left-color: #8b5cf6; background: linear-gradient(135deg, #f5f3ff 0%, #ffffff 100%); }

    .card-icon { font-size: 1.6rem; margin-right: 0.5rem; }
    .card-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
    }
    .card-body {
        font-size: 1rem;
        line-height: 1.85;
        color: #374151;
    }

    .settings-section {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        border: 1px solid #e2e8f0;
    }
    
    @media screen and (max-width: 768px) {
        .settings-section {
            padding: 1rem;
            margin: 1rem 0;
        }
    }

    .success-banner {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: 1px solid #6ee7b7;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #065f46;
        text-align: center;
        font-weight: 600;
    }
    .error-banner {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border: 1px solid #fca5a5;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #991b1b;
        text-align: center;
        font-weight: 600;
    }
    .warning-banner {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 1px solid #fbbf24;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #92400e;
        text-align: center;
        font-weight: 600;
    }

    .footer {
        text-align: center;
        color: #9ca3af;
        font-size: 0.85rem;
        padding: 1.5rem 0;
        border-top: 1px solid #e5e7eb;
        margin-top: 2rem;
    }

    [data-testid="stChatMessage"] {
        background: #ffffff;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }

    .admin-panel {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 1px solid #fbbf24;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1rem;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════

def pdf_to_images(pdf_bytes: bytes) -> list:
    if not PDF_SUPPORT:
        raise RuntimeError("PDF 支持需要安装 pdf2image 和 poppler")
    images = convert_from_bytes(pdf_bytes, dpi=200)
    result = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result.append(buf.getvalue())
    return result


def get_mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


def extract_course_number(filename):
    match = re.search(r'L(\d{2})', filename)
    if match:
        return f"L{match.group(1)}"
    return "L00"


def extract_images_from_pdf_bytes(pdf_bytes):
    images = []
    doc = fitz.open("pdf", pdf_bytes)
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            image_filename = f"page_{page_num + 1}_{img_index + 1}.{image_ext}"
            
            images.append({
                "page_number": page_num + 1,
                "image_bytes": image_bytes,
                "image_filename": image_filename
            })
    
    doc.close()
    return images


def analyze_image_with_gemini(model, image_bytes):
    try:
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
        
        response = model.generate_content([prompt, {"mime_type": "image/png", "data": image_bytes}])
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


def upload_to_github(github_token, path, content, message):
    encoded_path = quote(path)
    url = f"https://api.github.com/repos/hzbeck7/AMC8-math-learner/contents/{encoded_path}"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if isinstance(content, str):
        content_bytes = content.encode('utf-8')
    else:
        content_bytes = content
    
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode('utf-8')
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            payload["sha"] = response.json()["sha"]
        
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"上传失败: {e}")
        return False


# ──────────────────────────────────────────────
# 云端题库工具函数
# ──────────────────────────────────────────────

def fetch_course_questions(course: str) -> list:
    try:
        json_url = f"{GITHUB_BASE_URL}/data/{course}/questions_{course}.json"
        response = requests.get(json_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.warning(f"获取课程 {course} 题目列表失败: {e}")
        return []


def fetch_question_image(course: str, image_name: str) -> tuple:
    try:
        image_url = f"{GITHUB_BASE_URL}/images/{course}/{image_name}"
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        mime_type = get_mime_type(image_name)
        return response.content, mime_type
    except Exception as e:
        st.warning(f"下载图片 {image_name} 失败: {e}")
        return None, None


# ══════════════════════════════════════════════
# 语音合成函数
# ══════════════════════════════════════════════

async def generate_voice_async(text: str, voice: str = "zh-CN-YunxiNeural") -> bytes:
    if not EDGE_TTS_AVAILABLE:
        raise RuntimeError("需要安装 edge-tts 库")
    
    communicate = edge_tts.Communicate(text, voice)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def generate_voice(text: str, voice: str = "zh-CN-YunxiNeural") -> bytes:
    return asyncio.run(generate_voice_async(text, voice))


def play_voice_button(text: str, key: str):
    if not EDGE_TTS_AVAILABLE:
        st.warning("语音功能需要安装 edge-tts")
        return
    
    with ThreadPoolExecutor() as executor:
        future = executor.submit(generate_voice, text)
        
        if st.button(f"🔊 听听教练怎么说", key=f"voice_{key}"):
            with st.spinner("正在生成语音..."):
                try:
                    audio_bytes = future.result(timeout=30)
                    st.audio(audio_bytes, format="audio/mp3")
                except Exception as e:
                    st.error(f"语音生成失败: {e}")


# ══════════════════════════════════════════════
# Prompt 工程 - 幽默名师人设
# ══════════════════════════════════════════════

SYSTEM_PROMPT = """\
你是一位极其幽默、接地气的 AMC 8 数学竞赛教练，绰号"数学段子手"。你的教学风格就像脱口秀演员讲数学，能把枯燥的公式变成有趣的故事。

## 你的说话风格：
- 大量使用接地气的比喻（比如：把勾股定理叫做三角形的"铁三角"关系，把因数分解叫做"数学拆快递"）
- 每道题必须加入 1-2 句冷笑话或幽默鼓励
- 用网络流行语和学生打成一片
- 偶尔自黑，展现亲和力

## 输出格式要求

### 🎭 数学小剧场
- 讲一个与知识点相关的趣味故事或数学家八卦，控制在 150 字以内
- 必须包含至少一个段子或冷笑话
- 示例风格："话说毕达哥拉斯当年发现勾股定理的时候，据说杀了100头牛庆祝。要是我，可能只杀一头——毕竟现在牛肉挺贵的..."

### 🎯 核心知识点
- 用大白话总结考点，避免术语堆砌
- 每个知识点配一个接地气的比喻
- 示例："这题考的是质因数分解，说白了就是给数字'拆快递'，看看里面装了多少个2、3、5..."

### 🧩 步进式解法
- 每步都要有引导性提问（用 ❓ 标记）
- 穿插幽默点评和鼓励
- 必须包含至少一句冷笑话或鼓励，例如：
  * "这步你要是做对了，我看你离数学家高斯也就差两斤头发的距离了"
  * "别慌，这题比你的前任简单多了"
  * "相信自己，你的脑细胞正在开派对呢"
  * "错一次没关系，爱因斯坦小时候数学还考过1分呢（虽然后来证明是谣言）"

### 💡 衍生思考
- 给出一道变式题
- 用轻松语气说明关联

## 注意事项
- 全程中文，语气像朋友聊天
- 数学公式用通俗文字表达
- 如果识别失败，幽默地吐槽图片质量
- 如果不是数学题，开玩笑说自己"只会教数学，不会算命"
"""


# ══════════════════════════════════════════════
# Gemini API 调用
# ══════════════════════════════════════════════

def call_gemini(api_key: str, image_bytes: bytes, mime_type: str, 
                model: str = "gemini-2.5-flash", user_text: str = "") -> str:
    if not GEMINI_AVAILABLE:
        raise RuntimeError("需要安装 google-generativeai")

    genai.configure(api_key=api_key)

    model_instance = genai.GenerativeModel(
        model,
        system_instruction=SYSTEM_PROMPT,
    )

    user_parts = []
    if user_text.strip():
        user_parts.append(f"学生补充：{user_text.strip()}\n\n")
    user_parts.append({"mime_type": mime_type, "data": image_bytes})
    user_parts.append("来，用你幽默的风格讲讲这道题！")

    generation_config = {
        "temperature": 0.8,
        "max_output_tokens": 4096,
    }

    import time
    last_error = None
    for attempt in range(3):
        try:
            response = model_instance.generate_content(
                user_parts,
                generation_config=generation_config,
            )
            return response.text
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            if "500" in error_msg or "internal" in error_msg:
                wait_time = (attempt + 1) * 3
                time.sleep(wait_time)
                continue
            raise
    
    raise last_error


# ══════════════════════════════════════════════
# 输出渲染
# ══════════════════════════════════════════════

def simple_markdown_to_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">\1</code>', text)
    text = re.sub(r'^(\d+)\.\s+(.+)$', r'<li>\2</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*</li>\n?)+', lambda m: '<ol>' + m.group(0) + '</ol>', text, flags=re.DOTALL)
    text = re.sub(r'^[-*]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = text.replace('\n', '<br>')
    text = re.sub(r'<br>\s*<br>\s*<(ol|ul|li)', r'<\1', text)
    text = re.sub(r'</(ol|ul)>\s*<br>', r'</\1>', text)
    return text


def render_module_with_voice(title: str, body: str, card_class: str, voice_key: str):
    clean_text = re.sub(r'<[^>]+>', '', body)
    clean_text = clean_text.replace('<br>', ' ').replace('&nbsp;', ' ')
    
    st.markdown(
        f"""
        <div class="module-card {card_class}">
            <div class="card-title">{title}</div>
            <div class="card-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if EDGE_TTS_AVAILABLE and clean_text.strip():
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(f"🔊 听教练说", key=f"btn_{voice_key}"):
                with st.spinner("生成语音中..."):
                    try:
                        audio_bytes = generate_voice(clean_text[:1500])
                        st.audio(audio_bytes, format="audio/mp3")
                    except Exception as e:
                        st.error(f"语音失败: {e}")


def parse_and_render_with_voice(response_text: str):
    module_patterns = [
        ("🎭 数学小剧场", "card-theater", "theater", [
            r"###\s*[🎭🎭]*\s*数学小剧场\s*[🎭🎭]*\s*\n(.*?)(?=###\s*[🎯🎯]*\s*核心知识点|$)",
            r"##\s*[🎭🎭]*\s*数学小剧场\s*[🎭🎭]*\s*\n(.*?)(?=##\s*[🎯🎯]*\s*核心知识点|$)",
        ]),
        ("🎯 核心知识点", "card-knowledge", "knowledge", [
            r"###\s*[🎯🎯]*\s*核心知识点\s*[🎯🎯]*\s*\n(.*?)(?=###\s*[🧩🧩]*\s*步进式解法|$)",
            r"##\s*[🎯🎯]*\s*核心知识点\s*[🎯🎯]*\s*\n(.*?)(?=##\s*[🧩🧩]*\s*步进式解法|$)",
        ]),
        ("🧩 步进式解法", "card-steps", "steps", [
            r"###\s*[🧩🧩]*\s*步进式解法\s*[🧩🧩]*\s*\n(.*?)(?=###\s*[💡💡]*\s*衍生思考|$)",
            r"##\s*[🧩🧩]*\s*步进式解法\s*[🧩🧩]*\s*\n(.*?)(?=##\s*[💡💡]*\s*衍生思考|$)",
        ]),
        ("💡 衍生思考", "card-bonus", "bonus", [
            r"###\s*[💡💡]*\s*衍生思考\s*[💡💡]*\s*\n(.*?)(?=$)",
            r"##\s*[💡💡]*\s*衍生思考\s*[💡💡]*\s*\n(.*?)(?=$)",
        ]),
    ]

    modules_found = {}
    
    for title, card_class, key, patterns in module_patterns:
        for pattern in patterns:
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                body = simple_markdown_to_html(match.group(1).strip())
                modules_found[key] = (title, card_class, body)
                break

    for key in ["theater", "knowledge", "steps", "bonus"]:
        if key in modules_found:
            title, card_class, body = modules_found[key]
            if key in ["theater", "steps"]:
                render_module_with_voice(title, body, card_class, key)
            else:
                st.markdown(
                    f'<div class="module-card {card_class}"><div class="card-title">{title}</div><div class="card-body">{body}</div></div>',
                    unsafe_allow_html=True,
                )

    if not modules_found:
        st.markdown(
            f'<div class="module-card card-theater"><div class="card-body">{simple_markdown_to_html(response_text)}</div></div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════
# 管理员面板
# ══════════════════════════════════════════════

def admin_panel():
    with st.sidebar.expander("🔐 管理后台", expanded=False):
        admin_password = st.text_input(
            "管理密码",
            type="password",
            placeholder="请输入管理员密码",
            key="admin_password"
        )
        
        if admin_password == st.secrets.get("ADMIN_PASSWORD", "admin123"):
            st.success("✅ 身份验证通过")
            
            st.markdown("---")
            st.markdown("### 📤 上传题库")
            
            uploaded_pdfs = st.file_uploader(
                "选择 PDF 文件（支持多个）",
                type=["pdf"],
                accept_multiple_files=True,
                key="admin_pdf_uploader"
            )
            
            github_token = st.text_input(
                "GitHub Token",
                type="password",
                placeholder="输入 GitHub Token",
                key="github_token",
                value=st.secrets.get("GITHUB_TOKEN", "")
            )
            
            gemini_key = st.text_input(
                "Gemini API Key",
                type="password",
                placeholder="输入 Gemini API Key",
                key="gemini_admin_key",
                value=st.secrets.get("GEMINI_API_KEY", "")
            )
            
            if st.button("🚀 开始入库", key="start_upload"):
                if not uploaded_pdfs:
                    st.error("请先上传 PDF 文件")
                    return
                if not github_token:
                    st.error("请输入 GitHub Token")
                    return
                if not gemini_key:
                    st.error("请输入 Gemini API Key")
                    return
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_pages = 0
                all_images = {}
                
                status_text.text("📊 正在统计总页数...")
                for pdf_file in uploaded_pdfs:
                    pdf_bytes = pdf_file.read()
                    images = extract_images_from_pdf_bytes(pdf_bytes)
                    course_num = extract_course_number(pdf_file.name)
                    if course_num not in all_images:
                        all_images[course_num] = []
                    all_images[course_num].extend(images)
                    total_pages += len(images)
                
                status_text.text(f"📚 共发现 {total_pages} 页题目")
                
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                processed_count = 0
                
                for course_num, images in all_images.items():
                    questions_data = []
                    
                    status_text.text(f"🔄 正在处理课程 {course_num}...")
                    
                    for idx, image_info in enumerate(images):
                        processed_count += 1
                        progress = processed_count / total_pages
                        progress_bar.progress(progress)
                        
                        status_text.text(f"🧠 正在分析第 {image_info['page_number']} 页 ({processed_count}/{total_pages})")
                        
                        analysis = analyze_image_with_gemini(model, image_info["image_bytes"])
                        questions_data.append({
                            "page_number": image_info["page_number"],
                            "image": image_info["image_filename"],
                            "title": f"第 {image_info['page_number']} 题",
                            **analysis
                        })
                        
                        image_path = f"data/questions/images/{course_num}/{image_info['image_filename']}"
                        upload_to_github(
                            github_token,
                            image_path,
                            image_info["image_bytes"],
                            f"Add image for {course_num} page {image_info['page_number']}"
                        )
                    
                    json_data = json.dumps(questions_data, ensure_ascii=False, indent=2)
                    json_path = f"data/questions/data/{course_num}/questions_{course_num}.json"
                    upload_to_github(
                        github_token,
                        json_path,
                        json_data,
                        f"Update questions for {course_num}"
                    )
                    
                    status_text.text(f"✅ 课程 {course_num} 处理完成")
                
                progress_bar.progress(1.0)
                status_text.text("🎉 所有题库已成功入库！")
                st.balloons()
                
                st.session_state.pop('analysis_result', None)
                st.experimental_rerun()
            
        elif admin_password:
            st.error("❌ 密码错误")


# ══════════════════════════════════════════════
# 主界面
# ══════════════════════════════════════════════

def main():
    st.markdown(
        """
        <div class="app-title">
            <h1>🧠 AMC 8 智学助手</h1>
            <p>你的幽默数学教练，让解题像听相声一样有趣！</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="settings-section">', unsafe_allow_html=True)
    st.markdown("### ⚙️ 设置")

    user_api_key = st.text_input(
        "请输入您的 Gemini API Key",
        type="password",
        placeholder="AI...",
        key="api_key_input",
    )

    if user_api_key and user_api_key.strip():
        api_key = user_api_key.strip()
        st.success("✅ 使用您输入的 API Key", icon="🔑")
    else:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("✅ 使用服务器配置的 API Key", icon="🔒")
        except KeyError:
            api_key = None
            st.warning("⚠️ 未配置 API Key", icon="⚠️")

    st.markdown("---")

    model_choice = st.selectbox(
        "🤖 模型",
        ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
        index=0,
        key="model_select",
    )

    st.markdown("---")

    user_text = st.text_area(
        "✏️ 补充说明（可选）",
        placeholder="例如：这道题我不理解第 2 步...",
        height=100,
        key="user_text_input",
    )

    st.markdown('</div>', unsafe_allow_html=True)

    if not api_key:
        st.markdown('<div class="warning-banner">⚠️ 请在上方填入 API Key 后再开始解题</div>', unsafe_allow_html=True)
        st.stop()

    # ── 侧边栏 ──
    with st.sidebar:
        st.markdown("### 📚 云端题库")
        st.markdown("从 GitHub 获取题目")
        
        selected_course = st.selectbox(
            "选择课程",
            COURSES,
            key="course_select",
        )
        
        questions = fetch_course_questions(selected_course)
        
        if questions:
            question_options = [f"{q.get('id', q.get('page_number', i+1))}: {q.get('title', '无题')}" for i, q in enumerate(questions)]
            selected_question_idx = st.selectbox(
                "选择题目",
                range(len(question_options)),
                format_func=lambda x: question_options[x],
                key="question_select",
            )
            selected_question = questions[selected_question_idx]
        else:
            selected_question = None
            st.info(f"课程 {selected_course} 暂无题目")
        
        use_cloud = st.checkbox("使用云端题库", key="use_cloud_checkbox")
        
        st.markdown("---")
        admin_panel()

    # ── 主内容区 ──
    tab1, tab2 = st.tabs(["📤 上传题目", "☁️ 云端题库"])
    
    image_bytes = None
    mime_type = None
    source_type = None

    with tab1:
        st.markdown("### 📤 上传题目")
        
        uploaded_file = st.file_uploader(
            "选择图片或 PDF 文件",
            type=["jpg", "jpeg", "png", "gif", "webp", "pdf"],
            key="file_uploader",
        )

        if uploaded_file is not None:
            st.markdown("#### 📷 题目预览")
            if uploaded_file.type.startswith("image/"):
                st.image(uploaded_file, use_container_width=True)
            elif uploaded_file.type == "application/pdf":
                st.info("📄 PDF 已上传，点击下方按钮开始分析")

    with tab2:
        st.markdown("### ☁️ 云端题库")
        
        if selected_question and use_cloud:
            image_name = selected_question.get("image")
            if image_name:
                with st.spinner("🔄 正在加载题目图片..."):
                    img_bytes, img_mime = fetch_question_image(selected_course, image_name)
                    if img_bytes:
                        image_bytes = img_bytes
                        mime_type = img_mime
                        source_type = "cloud"
                        st.image(img_bytes, use_container_width=True)
                        st.markdown(f"**题目信息：** {selected_question.get('title', '')}")
                    else:
                        st.error("无法加载题目图片")
            else:
                st.warning("该题目没有关联图片")
        else:
            st.info("请在侧边栏选择课程和题目，并勾选「使用云端题库」")

    # ── 初始化 session_state ──
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None
    if "analysis_error" not in st.session_state:
        st.session_state.analysis_error = None
    if "cloud_image_bytes" not in st.session_state:
        st.session_state.cloud_image_bytes = None
    if "cloud_mime_type" not in st.session_state:
        st.session_state.cloud_mime_type = None

    if image_bytes:
        st.session_state.cloud_image_bytes = image_bytes
        st.session_state.cloud_mime_type = mime_type
    
    has_source = (uploaded_file is not None) or (st.session_state.cloud_image_bytes is not None)
    analyze_clicked = st.button(
        "🚀 开始分析",
        type="primary",
        use_container_width=True,
        disabled=not has_source,
    )

    if analyze_clicked:
        if not GEMINI_AVAILABLE:
            st.error("需要安装 google-generativeai")
            st.stop()

        try:
            with st.spinner("🔍 教练正在备课..."):
                if source_type == "cloud" and st.session_state.cloud_image_bytes:
                    image_bytes = st.session_state.cloud_image_bytes
                    mime_type = st.session_state.cloud_mime_type
                elif uploaded_file:
                    file_bytes = uploaded_file.read()
                    filename = uploaded_file.name

                    if filename.lower().endswith(".pdf"):
                        images = pdf_to_images(file_bytes)
                        image_bytes = images[0]
                        mime_type = "image/png"
                    else:
                        image_bytes = file_bytes
                        mime_type = get_mime_type(filename)

                response_text = call_gemini(
                    api_key=api_key,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    model=model_choice,
                    user_text=user_text,
                )

            st.session_state.analysis_result = response_text
            st.session_state.analysis_error = None

        except Exception as e:
            error_msg = str(e).lower()
            if "api key" in error_msg or "authentication" in error_msg:
                friendly_msg = "🔑 API Key 无效，请检查"
            elif "rate limit" in error_msg or "quota" in error_msg:
                friendly_msg = "⏳ 请求太频繁，请稍后再试"
            elif "safety" in error_msg or "blocked" in error_msg:
                friendly_msg = "🛡️ 内容被拦截，换道题试试"
            else:
                friendly_msg = f"❌ 出错啦：{e}"
            st.session_state.analysis_error = friendly_msg
            st.session_state.analysis_result = None

    if st.session_state.analysis_result:
        st.markdown("---")

        with st.chat_message("assistant", avatar="🎓"):
            st.markdown('<div class="success-banner">✅ 来听听教练的幽默讲解！</div>', unsafe_allow_html=True)
            parse_and_render_with_voice(st.session_state.analysis_result)

        st.markdown('<div class="footer">🧠 AMC 8 智学助手 · 让数学像段子一样有趣</div>', unsafe_allow_html=True)

    elif st.session_state.analysis_error:
        st.markdown(f'<div class="error-banner">{st.session_state.analysis_error}</div>', unsafe_allow_html=True)

    elif not has_source:
        st.markdown("")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;">📸</div><h4 style="color:#374151;">上传题目</h4></div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;">☁️</div><h4 style="color:#374151;">云端题库</h4></div>', unsafe_allow_html=True)
        with col3:
            st.markdown('<div style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;">🎤</div><h4 style="color:#374151;">听教练讲</h4></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
