"""
AMC 8 智学助手 —— 风趣幽默的数学竞赛教练
技术栈: Streamlit + Google Gemini API (Vision) + edge-tts (语音)
部署: Streamlit Cloud
特性: 移动端优化、语音朗读、幽默名师人设
"""

import streamlit as st
import base64
import re
import io
import asyncio
import tempfile
import os
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
# 页面配置
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="AMC 8 智学助手",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
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

    /* 语音按钮样式 */
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

    /* 模块卡片 */
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

    /* 设置区域 */
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

    /* 提示横幅 */
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
    }
    .warning-banner {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 1px solid #fbbf24;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #92400e;
        text-align: center;
    }

    .footer {
        text-align: center;
        color: #9ca3af;
        font-size: 0.85rem;
        padding: 1.5rem 0;
        border-top: 1px solid #e5e7eb;
        margin-top: 2rem;
    }

    /* 聊天消息样式 */
    [data-testid="stChatMessage"] {
        background: #ffffff;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════

def pdf_to_images(pdf_bytes: bytes) -> list:
    """将 PDF 转换为图片列表"""
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
    """根据文件扩展名返回 MIME 类型"""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


# ══════════════════════════════════════════════
# 语音合成函数
# ══════════════════════════════════════════════

async def generate_voice_async(text: str, voice: str = "zh-CN-YunxiNeural") -> bytes:
    """异步生成语音"""
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
    """同步包装异步语音生成"""
    return asyncio.run(generate_voice_async(text, voice))


def play_voice_button(text: str, key: str):
    """显示语音播放按钮"""
    if not EDGE_TTS_AVAILABLE:
        st.warning("语音功能需要安装 edge-tts")
        return
    
    # 使用线程池在后台生成语音
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
    """调用 Gemini API"""
    if not GEMINI_AVAILABLE:
        raise RuntimeError("需要安装 google-generativeai")

    genai.configure(api_key=api_key)
    model_instance = genai.GenerativeModel(model)

    prompt_parts = [SYSTEM_PROMPT]
    if user_text.strip():
        prompt_parts.append(f"学生补充：{user_text.strip()}")

    image_part = {"mime_type": mime_type, "data": image_bytes}
    prompt_parts.append(image_part)
    prompt_parts.append("来，用你幽默的风格讲讲这道题！")

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    generation_config = {"temperature": 0.8, "max_output_tokens": 4096}

    response = model_instance.generate_content(
        prompt_parts,
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    return response.text


# ══════════════════════════════════════════════
# 输出渲染
# ══════════════════════════════════════════════

def simple_markdown_to_html(text: str) -> str:
    """Markdown 转 HTML"""
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
    """渲染模块并添加语音按钮"""
    # 清理文本用于语音（移除 HTML 标签）
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
    
    # 语音按钮
    if EDGE_TTS_AVAILABLE and clean_text.strip():
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(f"🔊 听教练说", key=f"btn_{voice_key}"):
                with st.spinner("生成语音中..."):
                    try:
                        audio_bytes = generate_voice(clean_text[:1500])  # 限制长度
                        st.audio(audio_bytes, format="audio/mp3")
                    except Exception as e:
                        st.error(f"语音失败: {e}")


def parse_and_render_with_voice(response_text: str):
    """解析回复并渲染，带语音功能"""
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

    # 按顺序渲染（小剧场和解法带语音）
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
# 主界面
# ══════════════════════════════════════════════

def main():
    # 标题
    st.markdown(
        """
        <div class="app-title">
            <h1>🧠 AMC 8 智学助手</h1>
            <p>你的幽默数学教练，让解题像听相声一样有趣！</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 设置区域
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

    # 文件上传
    st.markdown("---")
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
    else:
        st.markdown('<div class="upload-hint">👆 点击上方按钮上传题目</div>', unsafe_allow_html=True)

    # 分析按钮
    st.markdown("")
    analyze_clicked = st.button(
        "🚀 开始分析",
        type="primary",
        use_container_width=True,
        disabled=(uploaded_file is None),
    )

    # 执行分析
    if analyze_clicked:
        if not GEMINI_AVAILABLE:
            st.error("需要安装 google-generativeai")
            st.stop()

        try:
            with st.spinner("🔍 教练正在备课..."):
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

            # 使用 chat_message 展示结果
            st.markdown("---")
            
            with st.chat_message("assistant", avatar="🎓"):
                st.markdown('<div class="success-banner">✅ 来听听教练的幽默讲解！</div>', unsafe_allow_html=True)
                parse_and_render_with_voice(response_text)
            
            st.markdown('<div class="footer">🧠 AMC 8 智学助手 · 让数学像段子一样有趣</div>', unsafe_allow_html=True)

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
            st.markdown(f'<div class="error-banner">{friendly_msg}</div>', unsafe_allow_html=True)

    # 空状态
    elif uploaded_file is None:
        st.markdown("")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;">📸</div><h4 style="color:#374151;">上传题目</h4></div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;">🎤</div><h4 style="color:#374151;">听教练讲</h4></div>', unsafe_allow_html=True)
        with col3:
            st.markdown('<div style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;">📝</div><h4 style="color:#374151;">掌握技巧</h4></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
