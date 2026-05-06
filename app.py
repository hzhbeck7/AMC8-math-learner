"""
AMC 8 智学助手 —— 风趣幽默的数学竞赛教练
技术栈: Streamlit + Google Gemini API (Vision)
部署: Streamlit Cloud（支持多用户，API Key 通过侧边栏输入或 st.secrets 配置）
"""

import streamlit as st
import base64
import json
import re
import sys
import io
from pathlib import Path

# ──────────────────────────────────────────────
# PDF 处理依赖（可选，仅在用户上传 PDF 时需要）
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
# 页面配置
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="AMC 8 智学助手",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# 自定义 CSS —— 讲义风格
# ──────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    /* 全局字体 */
    .stApp {
        font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    }

    /* 标题区域 */
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

    /* 模块卡片 */
    .module-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-left: 5px solid;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .module-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
    }

    /* 数学小剧场 —— 橙色 */
    .card-theater {
        border-left-color: #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%);
    }
    .card-theater .card-icon { color: #f59e0b; }

    /* 核心知识点 —— 蓝色 */
    .card-knowledge {
        border-left-color: #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
    }
    .card-knowledge .card-icon { color: #3b82f6; }

    /* 步进式解法 —— 绿色 */
    .card-steps {
        border-left-color: #10b981;
        background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%);
    }
    .card-steps .card-icon { color: #10b981; }

    /* 衍生思考 —— 紫色 */
    .card-bonus {
        border-left-color: #8b5cf6;
        background: linear-gradient(135deg, #f5f3ff 0%, #ffffff 100%);
    }
    .card-bonus .card-icon { color: #8b5cf6; }

    .card-icon {
        font-size: 1.6rem;
        margin-right: 0.5rem;
        vertical-align: middle;
    }
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
    .card-body ol, .card-body ul {
        padding-left: 1.5rem;
    }
    .card-body li {
        margin-bottom: 0.4rem;
    }

    /* 侧边栏美化 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
    }
    [data-testid="stSidebar"] .stMarkdown {
        font-size: 0.95rem;
    }

    /* 上传区域 */
    .upload-hint {
        text-align: center;
        color: #9ca3af;
        font-size: 0.9rem;
        padding: 0.5rem;
    }

    /* 成功提示 */
    .success-banner {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: 1px solid #6ee7b7;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #065f46;
        text-align: center;
        font-weight: 600;
    }

    /* 错误提示 */
    .error-banner {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border: 1px solid #fca5a5;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #991b1b;
        text-align: center;
    }

    /* 警告提示 */
    .warning-banner {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 1px solid #fbbf24;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        color: #92400e;
        text-align: center;
    }

    /* 题目预览 */
    .question-preview {
        background: #f9fafb;
        border: 1px dashed #d1d5db;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .question-preview img {
        max-width: 100%;
        max-height: 400px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* 加载动画 */
    .loading-text {
        text-align: center;
        color: #6b7280;
        font-size: 1.1rem;
        padding: 2rem;
    }

    /* 页脚 */
    .footer {
        text-align: center;
        color: #9ca3af;
        font-size: 0.85rem;
        padding: 1.5rem 0;
        border-top: 1px solid #e5e7eb;
        margin-top: 2rem;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════

def pdf_to_images(pdf_bytes: bytes) -> list:
    """将 PDF 转换为图片列表（每页一张）"""
    if not PDF_SUPPORT:
        raise RuntimeError(
            "PDF 支持需要安装 pdf2image 和 poppler。\n"
            "请运行: pip install pdf2image\n"
            "并确保系统已安装 poppler-utils。"
        )
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
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


# ══════════════════════════════════════════════
# Prompt 工程
# ══════════════════════════════════════════════

SYSTEM_PROMPT = """\
你是一位风趣幽默、知识渊博的 AMC 8 数学竞赛教练。你的教学风格生动活泼，善于用类比和故事激发学生的数学兴趣。

当学生上传一道 AMC 8 数学题（图片或文字）后，你必须严格按照以下四个模块输出内容。每个模块必须用对应的标题标记。

## 输出格式要求

### 🎭 数学小剧场
- 讲一个与本题知识点相关的数学历史故事、数学家轶事或生活中的趣味应用。
- 语言生动有趣，像讲故事一样，控制在 150 字以内。
- 目的：激发学习兴趣，让学生感受到数学的魅力。

### 🎯 核心知识点
- 用简洁的要点列表总结本题考查的 AMC 8 核心考点（2-5 个）。
- 每个考点用一句话概括，并简要说明为什么这个考点重要。
- 如果涉及公式，请用清晰的方式呈现。

### 🧩 步进式解法
- 分步骤展示解题逻辑，每一步都要有**引导性的提问**（用 ❓ 标记），引导学生主动思考。
- 不要直接给出最终答案，而是通过层层递进的提问让学生自己推导。
- 每一步之间要有逻辑衔接，像教练在旁边一步步引导学生。
- 格式示例：
  **第一步：观察与发现**
  ❓ 你注意到题目中有什么特殊的数字或关系吗？
  → 引导分析...

  **第二步：建立联系**
  ❓ 如果我们把...和...联系起来，会发现什么规律？
  → 推导过程...

### 💡 衍生思考
- 给出一道类似思路的变式题（不需要解答，只给题目）。
- 简要说明这道变式题与原题的关联，帮助学生举一反三。

## 注意事项
- 全程使用中文回答。
- 语气亲切自然，像一位经验丰富的教练在和学生对话。
- 如果图片模糊或无法识别，请诚实告知并建议学生重新上传。
- 如果上传的不是数学题，请幽默地提醒学生"教练只教数学哦～"。
- 数学公式请用清晰的文本格式呈现，避免使用 LaTeX 代码。
"""


# ══════════════════════════════════════════════
# Gemini API 调用
# ══════════════════════════════════════════════

def call_gemini(api_key: str, image_bytes: bytes, mime_type: str, model: str = "gemini-2.0-flash", user_text: str = "") -> str:
    """
    调用 Google Gemini API 分析数学题并生成结构化讲解。
    """
    if not GEMINI_AVAILABLE:
        raise RuntimeError(
            "需要安装 google-generativeai 库。请运行: pip install google-generativeai"
        )

    # 配置 API Key
    genai.configure(api_key=api_key)

    # 创建模型实例
    model_instance = genai.GenerativeModel(model)

    # 构建提示词
    prompt_parts = [SYSTEM_PROMPT]

    # 添加用户补充说明
    if user_text.strip():
        prompt_parts.append(f"学生补充说明：{user_text.strip()}")

    # 添加图片
    image_part = {
        "mime_type": mime_type,
        "data": image_bytes
    }
    prompt_parts.append(image_part)

    prompt_parts.append("请分析这道 AMC 8 数学题，并按照四个模块输出讲解内容。")

    # 配置安全设置（降低安全阈值以允许更多内容）
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # 配置生成参数
    generation_config = {
        "temperature": 0.7,
        "max_output_tokens": 4096,
    }

    # 调用 API
    response = model_instance.generate_content(
        prompt_parts,
        generation_config=generation_config,
        safety_settings=safety_settings,
    )

    return response.text


# ══════════════════════════════════════════════
# 输出渲染
# ══════════════════════════════════════════════

def render_module(title: str, icon: str, body: str, card_class: str):
    """渲染一个模块卡片"""
    st.markdown(
        f"""
        <div class="module-card {card_class}">
            <div class="card-title">
                <span class="card-icon">{icon}</span>
                {title}
            </div>
            <div class="card-body">
                {body}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def parse_and_render(response_text: str):
    """
    解析 LLM 回复，按模块渲染为讲义卡片。
    支持多种分隔格式：### 标题、## 标题、**标题** 等。
    """
    # 定义模块匹配规则（按优先级排序）
    module_patterns = [
        ("🎭 数学小剧场", "card-theater", [
            r"###\s*[🎭🎭]*\s*数学小剧场\s*[🎭🎭]*\s*\n(.*?)(?=###\s*[🎯🎯]*\s*核心知识点|$)",
            r"##\s*[🎭🎭]*\s*数学小剧场\s*[🎭🎭]*\s*\n(.*?)(?=##\s*[🎯🎯]*\s*核心知识点|$)",
            r"\*\*🎭\s*数学小剧场\*\*\s*\n(.*?)(?=\*\*🎯|$)",
        ]),
        ("🎯 核心知识点", "card-knowledge", [
            r"###\s*[🎯🎯]*\s*核心知识点\s*[🎯🎯]*\s*\n(.*?)(?=###\s*[🧩🧩]*\s*步进式解法|$)",
            r"##\s*[🎯🎯]*\s*核心知识点\s*[🎯🎯]*\s*\n(.*?)(?=##\s*[🧩🧩]*\s*步进式解法|$)",
            r"\*\*🎯\s*核心知识点\*\*\s*\n(.*?)(?=\*\*🧩|$)",
        ]),
        ("🧩 步进式解法", "card-steps", [
            r"###\s*[🧩🧩]*\s*步进式解法\s*[🧩🧩]*\s*\n(.*?)(?=###\s*[💡💡]*\s*衍生思考|$)",
            r"##\s*[🧩🧩]*\s*步进式解法\s*[🧩🧩]*\s*\n(.*?)(?=##\s*[💡💡]*\s*衍生思考|$)",
            r"\*\*🧩\s*步进式解法\*\*\s*\n(.*?)(?=\*\*💡|$)",
        ]),
        ("💡 衍生思考", "card-bonus", [
            r"###\s*[💡💡]*\s*衍生思考\s*[💡💡]*\s*\n(.*?)(?=$)",
            r"##\s*[💡💡]*\s*衍生思考\s*[💡💡]*\s*\n(.*?)(?=$)",
            r"\*\*💡\s*衍生思考\*\*\s*\n(.*?)(?=$)",
        ]),
    ]

    modules_found = {}

    for title, card_class, patterns in module_patterns:
        for pattern in patterns:
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                body = match.group(1).strip()
                # 将 Markdown 转为 HTML（简单处理）
                body = simple_markdown_to_html(body)
                modules_found[title] = (card_class, body)
                break

    # 如果解析失败，将整个回复作为单个模块显示
    if not modules_found:
        render_module("📋 讲解内容", "📋", simple_markdown_to_html(response_text), "card-theater")
        return

    # 按顺序渲染各模块
    for title, card_class, _ in module_patterns:
        if title in modules_found:
            cls, body = modules_found[title]
            render_module(title, "", body, cls)


def simple_markdown_to_html(text: str) -> str:
    """简单的 Markdown → HTML 转换（处理加粗、列表、换行等）"""
    if not text:
        return ""

    # 加粗
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # 行内代码
    text = re.sub(r'`(.+?)`', r'<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">\1</code>', text)
    # 有序列表
    text = re.sub(r'^(\d+)\.\s+(.+)$', r'<li>\2</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*</li>\n?)+', lambda m: '<ol>' + m.group(0) + '</ol>', text, flags=re.DOTALL)
    # 无序列表
    text = re.sub(r'^[-*]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    # 换行
    text = text.replace('\n', '<br>')
    # 清理多余 <br>
    text = re.sub(r'<br>\s*<br>\s*<(ol|ul|li)', r'<\1', text)
    text = re.sub(r'</(ol|ul)>\s*<br>', r'</\1>', text)

    return text


# ══════════════════════════════════════════════
# 主界面
# ══════════════════════════════════════════════

def main():
    # ── 标题 ──
    st.markdown(
        """
        <div class="app-title">
            <h1>🧠 AMC 8 智学助手</h1>
            <p>上传一道 AMC 8 数学题，你的专属竞赛教练即刻开讲！</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 侧边栏 ──
    with st.sidebar:
        st.markdown("## ⚙️ 设置")

        # API Key 输入（用户优先）
        user_api_key = st.text_input(
            "请输入您的 Gemini API Key",
            type="password",
            placeholder="AI...",
            help="您的 API Key 仅在当前会话有效，不会被存储到服务器",
        )

        # 优先级逻辑：用户输入 > st.secrets
        if user_api_key and user_api_key.strip():
            api_key = user_api_key.strip()
            st.success("✅ 使用您输入的 API Key", icon="🔑")
        else:
            # 尝试读取 st.secrets
            try:
                api_key = st.secrets["GEMINI_API_KEY"]
                st.success("✅ 使用服务器配置的 API Key", icon="🔒")
            except KeyError:
                api_key = None
                st.warning("⚠️ 未配置 API Key", icon="⚠️")

        st.markdown("---")

        # 模型选择
        model_choice = st.selectbox(
            "🤖 模型",
            [
                "gemini-2.0-flash",
                "gemini-2.5-flash-preview-05-20",
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ],
            index=0,
            help="gemini-2.0-flash 稳定免费；gemini-3 系列推理能力更强",
        )

        st.markdown("---")

        # 附加说明
        user_text = st.text_area(
            "✏️ 补充说明（可选）",
            placeholder="例如：这道题我不理解第 2 步...",
            height=100,
            help="可以补充你对这道题的疑问",
        )

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size:0.85rem;color:#6b7280;">
                <p>📌 <strong>支持格式：</strong>JPG / PNG / PDF</p>
                <p>📌 <strong>使用方法：</strong>上传题目图片，点击"开始分析"</p>
                <p>📌 <strong>隐私说明：</strong>图片仅发送至 Google Gemini API，不会存储</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── 检查 API Key 是否配置 ──
    if not api_key:
        st.markdown(
            '<div class="warning-banner">⚠️ 请在左侧填入 API Key 后再开始解题</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # ── 主区域 ──
    # 文件上传
    with st.container():
        col_upload, col_preview = st.columns([1, 1])

        with col_upload:
            st.markdown("### 📤 上传题目")
            uploaded_file = st.file_uploader(
                "选择图片或 PDF 文件",
                type=["jpg", "jpeg", "png", "gif", "webp", "pdf"],
                label_visibility="collapsed",
            )

            if uploaded_file is None:
                st.markdown(
                    '<div class="upload-hint">👆 点击上方按钮上传题目图片</div>',
                    unsafe_allow_html=True,
                )

        with col_preview:
            if uploaded_file is not None:
                if uploaded_file.type.startswith("image/"):
                    st.image(uploaded_file, caption="题目预览", use_container_width=True)
                elif uploaded_file.type == "application/pdf":
                    st.markdown(
                        '<div class="question-preview">📄 已上传 PDF 文件</div>',
                        unsafe_allow_html=True,
                    )

    # ── 分析按钮 ──
    analyze_clicked = st.button(
        "🚀 开始分析",
        type="primary",
        use_container_width=True,
        disabled=(uploaded_file is None),
    )

    # ── 执行分析 ──
    if analyze_clicked:
        if not GEMINI_AVAILABLE:
            st.markdown(
                '<div class="error-banner">⚠️ 需要安装 google-generativeai 库。请运行: pip install google-generativeai</div>',
                unsafe_allow_html=True,
            )
            st.stop()

        # 处理上传文件
        try:
            with st.spinner("🔍 正在识别题目，教练准备开讲..."):
                file_bytes = uploaded_file.read()
                filename = uploaded_file.name

                if filename.lower().endswith(".pdf"):
                    # PDF → 图片
                    images = pdf_to_images(file_bytes)
                    # 取第一页（AMC 8 题目通常一页一题）
                    image_bytes = images[0]
                    mime_type = "image/png"
                else:
                    image_bytes = file_bytes
                    mime_type = get_mime_type(filename)

                # 调用 Gemini
                response_text = call_gemini(
                    api_key=api_key,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    model=model_choice,
                    user_text=user_text,
                )

            # ── 渲染结果 ──
            st.markdown("---")
            st.markdown(
                '<div class="success-banner">✅ 教练分析完成！请查看下方讲义 👇</div>',
                unsafe_allow_html=True,
            )
            st.markdown("")

            parse_and_render(response_text)

            # 页脚
            st.markdown(
                '<div class="footer">🧠 AMC 8 智学助手 · 让每一道题都成为进步的阶梯</div>',
                unsafe_allow_html=True,
            )

        except Exception as e:
            error_msg = str(e)
            # 友好化常见错误
            if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                friendly_msg = "🔑 API Key 无效，请检查您输入的 Key 是否正确"
            elif "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                friendly_msg = "⏳ 请求过于频繁或额度不足，请稍后再试"
            elif "timeout" in error_msg.lower():
                friendly_msg = "⏰ 请求超时，请检查网络后重试"
            elif "safety" in error_msg.lower() or "blocked" in error_msg.lower():
                friendly_msg = "🛡️ 内容被安全过滤器拦截，请尝试上传其他题目"
            else:
                friendly_msg = f"❌ 分析出错：{error_msg}"

            st.markdown(
                f'<div class="error-banner">{friendly_msg}</div>',
                unsafe_allow_html=True,
            )

    # ── 空状态提示 ──
    elif uploaded_file is None:
        st.markdown("")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                """
                <div style="text-align:center;padding:2rem;">
                    <div style="font-size:3rem;">📸</div>
                    <h3 style="color:#374151;">第一步</h3>
                    <p style="color:#6b7280;">上传题目图片或 PDF</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                """
                <div style="text-align:center;padding:2rem;">
                    <div style="font-size:3rem;">🤖</div>
                    <h3 style="color:#374151;">第二步</h3>
                    <p style="color:#6b7280;">AI 教练智能识别与分析</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                """
                <div style="text-align:center;padding:2rem;">
                    <div style="font-size:3rem;">📝</div>
                    <h3 style="color:#374151;">第三步</h3>
                    <p style="color:#6b7280;">获得精美讲义式讲解</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
