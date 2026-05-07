"""
AMC 8 智学助手 — app.py
技术栈: Streamlit + Google Gemini 2.5 Flash + Edge-TTS (云希)
"""

import streamlit as st
import google.generativeai as genai
import base64
import json
import asyncio
import tempfile
import os
import io
import re
from PIL import Image
import fitz  # PyMuPDF

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AMC 8 智学助手",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

:root {
    --gold: #F5C842;
    --navy: #0C1829;
    --card-bg: rgba(255,255,255,0.05);
    --border: rgba(245,200,66,0.22);
    --text: #EEF2FF;
    --muted: #8899BB;
}

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(150deg, #0C1829 0%, #101E38 60%, #0A1E40 100%) !important;
    color: var(--text) !important;
    font-family: 'Noto Sans SC', sans-serif !important;
}

[data-testid="stAppViewContainer"]::after {
    content: '';
    position: fixed; inset: 0;
    background-image: radial-gradient(rgba(245,200,66,0.06) 1px, transparent 1px);
    background-size: 44px 44px;
    pointer-events: none;
    z-index: 0;
}

[data-testid="block-container"] { position: relative; z-index: 1; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#080F1D 0%,#0C1829 100%) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* Sidebar inputs */
[data-testid="stSidebar"] .stTextInput > div > div > input,
[data-testid="stSidebar"] .stTextArea  > div > div > textarea {
    background: #1C2E4A !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    caret-color: #F5C842 !important;
}
[data-testid="stSidebar"] .stTextInput > div > div > input::placeholder,
[data-testid="stSidebar"] .stTextArea  > div > div > textarea::placeholder {
    color: #6B82A8 !important;
    -webkit-text-fill-color: #6B82A8 !important;
}
[data-testid="stSidebar"] input[type="password"] {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] * {
    color: #D0DCF0 !important;
}

/* Hero */
.hero-wrap { text-align:center; padding:2rem 1rem 1.2rem; }
.hero-icon  { font-size:3.2rem; line-height:1; margin-bottom:.35rem; }
.hero-title {
    font-family:'ZCOOL XiaoWei',serif;
    font-size:clamp(2rem,5vw,3.4rem);
    background:linear-gradient(130deg,#F5C842 0%,#FFE87C 55%,#F59E0B 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; margin:0; letter-spacing:.06em; line-height:1.15;
}
.hero-sub   { color:var(--muted); font-size:clamp(.8rem,1.8vw,.92rem); letter-spacing:.18em; margin-top:.5rem; font-weight:300; }
.hero-badge {
    display:inline-block;
    background:linear-gradient(90deg,rgba(245,200,66,.12),rgba(245,200,66,.04));
    border:1px solid rgba(245,200,66,.38); border-radius:20px;
    padding:.22rem 1rem; font-size:.72rem; color:var(--gold);
    margin-top:.7rem; letter-spacing:.1em;
}

/* Section Header (装饰条) — 仅标题用 HTML，正文交给 Streamlit markdown */
.sec-header {
    position:relative;
    border:1px solid var(--border);
    border-radius:14px 14px 0 0;
    padding:1rem 1.3rem .7rem;
    margin:1.2rem 0 0;
    background:var(--card-bg);
    backdrop-filter:blur(8px);
    border-bottom:none;
}
.sec-header::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    border-radius:14px 14px 0 0;
}
.sec-header.sh-t::before { background:linear-gradient(90deg,#F5C842,#FB923C); }
.sec-header.sh-c::before { background:linear-gradient(90deg,#3B82F6,#8B5CF6); }
.sec-header.sh-l::before { background:linear-gradient(90deg,#22C55E,#16A34A); }
.sec-header p {
    font-family:'ZCOOL XiaoWei',serif; font-size:1.22rem;
    margin:0; letter-spacing:.03em;
}
.sh-t p { color:#F5C842; }
.sh-c p { color:#60A5FA; }
.sh-l p { color:#4ADE80; }

/* Section body container */
.sec-body-wrap {
    border:1px solid var(--border);
    border-top:none;
    border-radius:0 0 14px 14px;
    padding:.3rem 1.3rem 1.2rem;
    margin:0 0 1rem;
    background:var(--card-bg);
    backdrop-filter:blur(8px);
}
.sec-body-wrap .katex { color: var(--text) !important; font-size:1.02em; }
.sec-body-wrap .katex-display { margin:.8em 0 !important; }
.sec-body-wrap p, .sec-body-wrap li { line-height:1.95; font-size:.93rem; color:var(--text); }
.sec-body-wrap code {
    background:rgba(245,200,66,.1);
    color:#FFE87C;
    padding:.08em .35em;
    border-radius:4px;
    font-size:.9em;
}

/* Buttons */
.stButton > button {
    background:linear-gradient(135deg,#F5C842,#F59E0B) !important;
    color:#0C1829 !important; font-weight:700 !important;
    border:none !important; border-radius:10px !important;
    padding:.55rem 1.4rem !important;
    font-family:'Noto Sans SC',sans-serif !important;
    font-size:.92rem !important; letter-spacing:.03em !important;
    box-shadow:0 4px 14px rgba(245,200,66,.28) !important;
    transition:all .2s ease !important;
}
.stButton > button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 7px 22px rgba(245,200,66,.42) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background: #1C2E4A !important;
    border: 1px solid rgba(245,200,66,.35) !important;
    border-radius: 10px !important;
    color: #FFFFFF !important;
    caret-color: #F5C842 !important;
    font-family: 'Noto Sans SC', sans-serif !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea  > div > div > textarea::placeholder {
    color: #6B82A8 !important;
    -webkit-text-fill-color: #6B82A8 !important;
    opacity: 1 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 2px rgba(245,200,66,.2) !important;
    background: #1E3356 !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: rgba(245,200,66,.03) !important;
    border: 2px dashed rgba(245,200,66,.35) !important;
    border-radius: 14px !important;
}
[data-testid="stFileUploader"] * { color: #D0DCF0 !important; }
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] p { color: #A0B4CC !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background:rgba(0,0,0,.22) !important;
    border-radius:10px !important; padding:4px !important; gap:4px !important;
}
.stTabs [data-baseweb="tab"] {
    background:transparent !important; color:var(--muted) !important;
    border-radius:8px !important; font-family:'Noto Sans SC',sans-serif !important;
}
.stTabs [aria-selected="true"] {
    background:rgba(245,200,66,.18) !important; color:var(--gold) !important;
}

/* Misc */
hr { border-color:var(--border) !important; margin:1.4rem 0 !important; }
.stSpinner > div { border-top-color:var(--gold) !important; }
.stSuccess,.stInfo,.stWarning,.stError { border-radius:10px !important; }

/* Sidebar buttons override */
[data-testid="stSidebar"] .stButton > button {
    background:rgba(255,255,255,.06) !important;
    color:var(--text) !important; font-weight:400 !important;
    border:1px solid rgba(255,255,255,.1) !important;
    border-radius:8px !important; box-shadow:none !important;
    font-size:.82rem !important; text-align:left !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color:var(--gold) !important; background:rgba(245,200,66,.07) !important;
    transform:none !important; box-shadow:none !important;
}

.sb-label {
    color:var(--gold) !important; font-family:'ZCOOL XiaoWei',serif;
    font-size:.98rem; margin:1rem 0 .4rem; letter-spacing:.05em;
}

/* 让 Streamlit 默认的 markdown 公式显示得更清晰 */
.stMarkdown .katex { font-size:1.02em; }
.stMarkdown .katex-display {
    background:rgba(255,255,255,.02);
    padding:.4em 0;
    border-radius:6px;
    margin:.6em 0 !important;
}

@media (max-width:768px) {
    .sec-header, .sec-body-wrap { padding-left:.9rem; padding-right:.9rem; }
    .hero-wrap { padding:1.2rem .5rem .8rem; }
}

.footer { text-align:center; padding:2rem 0 1rem; color:#1E2D45; font-size:.72rem; line-height:1.9; }
</style>
""", unsafe_allow_html=True)


# ─── Constants ────────────────────────────────────────────────────────────────────
def get_admin_password() -> str:
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return os.environ.get("ADMIN_PASSWORD", "amc8admin2025")
QUESTION_BANK_FILE = "question_bank.json"


# ─── Question bank ────────────────────────────────────────────────────────────────
def load_bank():
    if os.path.exists(QUESTION_BANK_FILE):
        try:
            with open(QUESTION_BANK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_bank(data):
    with open(QUESTION_BANK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── PDF ─────────────────────────────────────────────────────────────────────────
def pdf_to_pil(pdf_bytes, max_pages=10):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    imgs = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        imgs.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    doc.close()
    return imgs


# ─── Gemini ───────────────────────────────────────────────────────────────────────
TUTOR_PROMPT = r"""你是一位风趣幽默、充满激情的奥数教练，专门辅导AMC 8竞赛。
风格：说话接地气、爱用比喻和段子、善于鼓励孩子、把复杂数学变得有趣好玩。

【极其重要的排版规则，必须严格遵守】
1. 所有数学内容必须使用标准 LaTeX 符号，并用美元符号包裹：
   - 行内公式用 $...$，例如 $a^2 + b^2 = c^2$
   - 独立公式（单独成行展示）用 $$...$$，例如 $$\frac{7!}{1! \times 1! \times 2! \times 3!} = 420$$
2. 绝对禁止在 LaTeX 公式里写中文（不要用 \text{排列方式} 这样的写法）。
   如果需要给公式加中文标签，把中文写在公式外面，例如：
   排列方式数 $= \dfrac{7!}{1! \cdot 1! \cdot 2! \cdot 3!} = 420$
3. 所有数字运算、变量、分数、根号、上下标、求和、阶乘等都必须写成 LaTeX。
   - 乘号用 \times 或 \cdot
   - 分数用 \dfrac{...}{...}
   - 根号用 \sqrt{...}
   - 不等号用 \le \ge \ne
4. 普通中文文字、段落标题正常写，不要用 $...$ 包裹。

请严格按以下 Markdown 格式输出四个板块（顺序不可颠倒）：

## 🎭 数学小剧场
讲一个与本题知识点相关的数学家故事或趣味历史（约150字，生动有趣，一般不需要公式）。

## 🔍 教练透视眼
用要点列表总结本题核心知识点和考点。涉及公式时用 $...$ 包起来。

## 🧩 逻辑拆解步
分步骤、引导式讲解解题逻辑，要求：
- 语言幽默接地气，像朋友聊天
- 所有算式一律使用 LaTeX（按上述规则）
- 用生动比喻
- 包含 1~2 个冷笑话或鼓励语
- 引导思维，不只给答案
- 最后明确给出正确答案，格式：**答案：(选项) 数值**

## 🎙️ 朗读稿
这是专门用来做语音合成的纯中文口语版本，必须严格符合以下要求：
- 完全不含任何 LaTeX 代码、反斜杠、美元符号、花括号、上下标字符
- 完全不含 "!" "^" "_" "×" "÷" "√" "π" "∠" "°" 等任何数学符号
- 所有数学表达式必须改写成中文口语：
  - "3!" 读作 "3 的阶乘"
  - "a^2" 读作 "a 的平方"，"a^3" 读作 "a 的立方"，"a^n" 读作 "a 的 n 次方"
  - "\sqrt{16}" 读作 "根号 16"
  - "\frac{a}{b}" 读作 "b 分之 a"
  - "a \times b" 读作 "a 乘以 b"
  - "50%" 读作 "百分之 50"
  - "π" 读作 "派"，"∠ABC" 读作 "角 ABC"，"90°" 读作 "90 度"
  - "≥" 读作 "大于等于"，"≤" 读作 "小于等于"，"≠" 读作 "不等于"
- 内容要包含「数学小剧场」的故事精华 +「逻辑拆解步」的完整推理过程 + 最终答案
- 语气自然亲切，像老师在给学生讲课，可以有适当的语气词（"好的同学们"、"注意看"、"所以呀"）
- 长度控制在 400~700 字
- 不要使用 Markdown 标题、列表符号、加粗等标记，写成普通段落即可

朗读稿示例（仅供参考格式和语气）：
今天我们来看一道排列组合题。想象一下，你手里有 7 个字母要排队，其中有 2 个字母一模一样，还有 3 个字母也完全相同。那怎么数排列方法呢？第一步，如果 7 个字母都不一样，排法就是 7 的阶乘，也就是 7 乘以 6 乘以 5 一直乘到 1，等于 5040。第二步……最后我们算出答案是 420 种。答对了就给自己鼓鼓掌。
"""


def analyze_question(api_key: str, parts: list) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content([TUTOR_PROMPT] + parts)
    return response.text


def extract_questions_from_pdf(api_key: str, images: list) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = (
        "请从这些PDF页面中提取所有数学题目，以纯JSON格式返回（不要加```代码块标记）。\n"
        '格式：{"questions":[{"id":1,"title":"编号或标题","content":"完整题目含选项",'
        '"topic":"几何/代数/数论/组合/概率","difficulty":"简单/中等/困难"}]}\n'
        "题目中的数学公式请尽量使用 LaTeX，用 $...$ 包裹。\n"
        "只返回JSON，不要其他内容。"
    )
    response = model.generate_content([prompt] + images[:8])
    text = response.text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


# ─── TTS ─────────────────────────────────────────────────────────────────────────
def _latex_to_speech(s: str) -> str:
    """把常见 LaTeX 命令/数学符号转成便于朗读的中文。"""
    # 分数 \frac{a}{b} / \dfrac / \tfrac
    s = re.sub(r"\\[dt]?frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\2 分之 \1", s)
    # 根号
    s = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"根号 \1 ", s)
    # 组合数
    s = re.sub(r"\\binom\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\1 选 \2", s)

    # 上标
    s = re.sub(r"\^\{\s*2\s*\}", " 的平方 ", s)
    s = re.sub(r"\^\{\s*3\s*\}", " 的立方 ", s)
    s = re.sub(r"\^\{([^{}]+)\}", r" 的 \1 次方 ", s)
    s = re.sub(r"\^\s*2\b", " 的平方 ", s)
    s = re.sub(r"\^\s*3\b", " 的立方 ", s)
    s = re.sub(r"\^([0-9a-zA-Z])", r" 的 \1 次方 ", s)
    # 下标
    s = re.sub(r"_\{([^{}]+)\}", r" 下标 \1 ", s)
    s = re.sub(r"_([0-9a-zA-Z])", r" 下标 \1 ", s)

    # 阶乘
    s = re.sub(r"(\))\s*!", r"\1 的阶乘 ", s)
    s = re.sub(r"(\d+)\s*!", r"\1 的阶乘 ", s)
    s = re.sub(r"([a-zA-Z])\s*!", r"\1 的阶乘 ", s)

    # 常见 LaTeX 命令
    replacements = {
        r"\\times": " 乘以 ",
        r"\\cdot": " 乘以 ",
        r"\\div": " 除以 ",
        r"\\pm": " 正负 ",
        r"\\mp": " 负正 ",
        r"\\le(?:q)?\b": " 小于等于 ",
        r"\\ge(?:q)?\b": " 大于等于 ",
        r"\\ne(?:q)?\b": " 不等于 ",
        r"\\approx": " 约等于 ",
        r"\\infty": " 无穷 ",
        r"\\pi\b": " 派 ",
        r"\\alpha": " 阿尔法 ",
        r"\\beta": " 贝塔 ",
        r"\\gamma": " 伽马 ",
        r"\\theta": " 西塔 ",
        r"\\angle": " 角 ",
        r"\\triangle": " 三角形 ",
        r"\\circ": " 度 ",
        r"\\left": "",
        r"\\right": "",
        r"\\quad": " ",
        r"\\,": " ",
        r"\\;": " ",
        r"\\!": "",
        r"\\%": " 百分号 ",
    }
    for pat, rep in replacements.items():
        s = re.sub(pat, rep, s)

    # 剩余所有 \xxx 命令去掉
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    # 去符号
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\\", "").replace("$", "")
    s = s.replace("^", "").replace("_", "")
    return s


def _clean_tts(text: str) -> str:
    """把 Markdown + LaTeX + Unicode 数学符号清洗成纯中文朗读文本。"""
    if not text:
        return ""

    # 先处理 $...$ 和 $$...$$ 公式
    text = re.sub(r"\$\$(.+?)\$\$", lambda m: _latex_to_speech(m.group(1)), text, flags=re.S)
    text = re.sub(r"\$(.+?)\$", lambda m: _latex_to_speech(m.group(1)), text, flags=re.S)

    # Unicode 数学符号兜底替换
    unicode_map = {
        "×": " 乘以 ",
        "÷": " 除以 ",
        "·": " 乘以 ",
        "√": " 根号 ",
        "π": " 派 ",
        "∠": " 角 ",
        "°": " 度 ",
        "≥": " 大于等于 ",
        "≤": " 小于等于 ",
        "≠": " 不等于 ",
        "≈": " 约等于 ",
        "∞": " 无穷 ",
        "±": " 正负 ",
        "△": " 三角形 ",
        "∴": " 所以 ",
        "∵": " 因为 ",
        "→": " 到 ",
        "²": " 的平方 ",
        "³": " 的立方 ",
        "½": " 二分之一 ",
        "⅓": " 三分之一 ",
        "¼": " 四分之一 ",
        "¾": " 四分之三 ",
    }
    for k, v in unicode_map.items():
        text = text.replace(k, v)

    # 阶乘兜底（公式外可能还有裸露的 "3!"）
    text = re.sub(r"(\d+)\s*!", r"\1 的阶乘 ", text)
    text = re.sub(r"([a-zA-Z])\s*!(?!\w)", r"\1 的阶乘 ", text)

    # 百分号
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"百分之 \1 ", text)

    # 去 Markdown 标题/加粗/斜体/代码/引用符号
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*{1,3}", "", text)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"^[\->\s]+", "", text, flags=re.M)

    # emoji
    text = re.sub(r"[🎭🔍🧩🎙️🚀✨🏆📚📄🤖🎯🔊⚠️✅❌【】\[\]]", "", text)

    # 残余反斜杠/花括号
    text = text.replace("\\", "").replace("{", "").replace("}", "")

    # 连续空行 → 句号
    text = re.sub(r"\n{2,}", "。 ", text)
    text = re.sub(r"[ \t]+", " ", text)

    # 只保留中英文、数字、常见标点
    text = re.sub(r"[^\u4e00-\u9fff\w\s，。！？；：、,\.\!\?\;\:\-\+=/%\(\)（）]", "", text)

    return text.strip()[:2500]


def generate_audio(text: str):
    """Convert text to MP3 bytes via edge-tts，带重试和详细错误提示。"""
    import threading

    clean = _clean_tts(text)
    if not clean or len(clean) < 2:
        st.warning("⚠️ 清洗后的文本为空，无法生成语音")
        return None

    st.session_state["_tts_debug_text"] = clean

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        path = tmp.name

    result = {"ok": False, "error": ""}

    def _run():
        try:
            import edge_tts
        except ImportError:
            result["error"] = "未安装 edge-tts，请运行: pip install edge-tts"
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            last_err = None
            for attempt in range(3):
                try:
                    comm = edge_tts.Communicate(
                        clean,
                        voice="zh-CN-YunxiNeural",
                        rate="+0%",
                        volume="+0%",
                    )
                    loop.run_until_complete(comm.save(path))
                    if os.path.exists(path) and os.path.getsize(path) > 100:
                        result["ok"] = True
                        return
                    last_err = "生成的音频文件为空"
                except Exception as e:
                    last_err = str(e)
            result["error"] = f"重试 3 次仍失败: {last_err}"
        except Exception as e:
            result["error"] = str(e)
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=90)

    if result["ok"] and os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        try:
            os.unlink(path)
        except Exception:
            pass
        return data

    if result["error"]:
        st.error(f"语音生成失败: {result['error']}")
        with st.expander("🔧 查看清洗后的 TTS 文本（用于排查）"):
            st.code(clean[:800], language="text")
    return None


# ─── Parse AI response ────────────────────────────────────────────────────────────
def parse_sections(text: str) -> dict:
    markers = {
        "theater": "数学小剧场",
        "coach": "教练透视眼",
        "logic": "逻辑拆解步",
        "speech": "朗读稿",
    }
    positions = {}
    for key, kw in markers.items():
        idx = text.find(kw)
        if idx != -1:
            positions[key] = idx

    if not positions:
        return {"theater": "", "coach": "", "logic": "", "speech": "", "raw": text}

    sorted_keys = sorted(positions, key=lambda k: positions[k])
    sections = {}
    for i, k in enumerate(sorted_keys):
        nl = text.find("\n", positions[k])
        start = nl + 1 if nl != -1 else positions[k]
        if i + 1 < len(sorted_keys):
            nk = sorted_keys[i + 1]
            end = text.rfind("\n", 0, positions[nk])
            sections[k] = text[start:end if end > start else positions[nk]].strip()
        else:
            sections[k] = text[start:].strip()

    for k in ("theater", "coach", "logic", "speech"):
        sections.setdefault(k, "")
    sections["raw"] = text
    return sections


def _sanitize_latex(md: str) -> str:
    """兜底：若有孤立的 LaTeX 命令没被 $...$ 包裹，自动包裹。"""
    def wrap_line(line: str) -> str:
        if "$" in line:
            return line
        if re.search(r"\\(frac|dfrac|sqrt|times|cdot|sum|int|binom|pi)\b", line):
            stripped = line.strip()
            if stripped:
                return line.replace(stripped, f"$${stripped}$$")
        return line
    return "\n".join(wrap_line(ln) for ln in md.splitlines())


# ─── Render result ────────────────────────────────────────────────────────────────
def _render_section(title_html_class: str, title_text: str, body_md: str):
    st.markdown(
        f'<div class="sec-header {title_html_class}"><p>{title_text}</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sec-body-wrap">', unsafe_allow_html=True)
    st.markdown(_sanitize_latex(body_md))
    st.markdown('</div>', unsafe_allow_html=True)


def render_result(result_text: str, key_suffix: str = "default"):
    """Render AI answer cards with proper LaTeX support."""
    sec = parse_sections(result_text)

    if sec.get("theater"):
        _render_section("sh-t", "🎭 数学小剧场", sec["theater"])

    # ── Voice button：优先用 AI 生成的朗读稿 ─────────────────────────────────
    tts_src = sec.get("speech", "").strip()
    if not tts_src:
        tts_src = (sec.get("theater", "") + "\n\n" + sec.get("logic", "")).strip()

    audio_key = f"tts_audio_{key_suffix}"
    error_key = f"tts_error_{key_suffix}"
    btn_key = f"voice_play_{key_suffix}"

    if tts_src:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("🔊 听听教练怎么说", key=btn_key, use_container_width=True):
                st.session_state.pop(audio_key, None)
                with st.spinner("🎙️ 云希老师正在录音，稍等..."):
                    audio_bytes = generate_audio(tts_src)
                if audio_bytes:
                    st.session_state[audio_key] = audio_bytes
                else:
                    st.session_state[error_key] = True

        if st.session_state.get(audio_key):
            st.audio(st.session_state[audio_key], format="audio/mp3")
        if st.session_state.pop(error_key, False):
            st.error("语音生成失败，请确保已安装 edge-tts（pip install edge-tts）")

    if sec.get("coach"):
        _render_section("sh-c", "🔍 教练透视眼", sec["coach"])

    if sec.get("logic"):
        _render_section("sh-l", "🧩 逻辑拆解步", sec["logic"])

    if not any(sec.get(k) for k in ("theater", "coach", "logic")):
        st.markdown(_sanitize_latex(result_text))


def _clear_tts_cache():
    for k in list(st.session_state.keys()):
        if k.startswith("tts_audio_") or k.startswith("tts_error_"):
            st.session_state.pop(k, None)


# ─── Sidebar ─────────────────────────────────────────────────────────────────────
def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("""
<div style="text-align:center;padding:.8rem 0 .4rem;">
  <div style="font-size:2.6rem;">🏆</div>
  <p style="color:#F5C842;font-family:'ZCOOL XiaoWei',serif;
            font-size:1.15rem;margin:.25rem 0 .1rem;letter-spacing:.05em;">
    AMC 8 智学助手</p>
  <p style="color:#4A5F80;font-size:.75rem;margin:0;">AI 趣味竞赛辅导平台</p>
</div>""", unsafe_allow_html=True)
        st.divider()

        st.markdown('<p class="sb-label">🔑 API 设置</p>', unsafe_allow_html=True)
        api_key = st.text_input(
            "请输入您的 Gemini API Key",
            type="password",
            placeholder="AIzaSy...",
            help="前往 https://aistudio.google.com 免费获取"
        )

        st.divider()

        bank = load_bank()
        st.markdown(
            f'<p class="sb-label">📚 题库 '
            f'<span style="color:#4A5F80;font-size:.75rem;font-family:\'Noto Sans SC\',sans-serif;">'
            f'({len(bank)} 题)</span></p>',
            unsafe_allow_html=True
        )

        if bank:
            for i, q in enumerate(bank):
                label = f"#{q.get('id', i+1)} [{q.get('topic','?')}] {q.get('title', '题目')[:16]}"
                if st.button(label, key=f"qb_{i}"):
                    st.session_state["qbank_selected"] = q
                    st.session_state["ai_result"] = None
                    _clear_tts_cache()
        else:
            st.markdown(
                '<p style="color:#4A5F80;font-size:.8rem;margin:.3rem 0;">'
                '题库为空，管理员可上传 PDF 导入</p>',
                unsafe_allow_html=True
            )

        st.divider()

        st.markdown('<p class="sb-label">⚙️ 管理后台</p>', unsafe_allow_html=True)
        with st.expander("🔐 管理员登录", expanded=False):
            pwd = st.text_input("管理员密码", type="password", key="admin_pwd_input")
            if pwd == get_admin_password():
                st.success("✅ 已登录管理后台")
                st.markdown("**上传题库 PDF**")
                pdf_file = st.file_uploader("选择 PDF", type=["pdf"], key="admin_pdf")
                if pdf_file:
                    if not api_key:
                        st.warning("请先输入 API Key")
                    elif st.button("📥 AI 提取并存入题库", key="admin_extract"):
                        with st.spinner("AI 正在智能提取题目..."):
                            try:
                                imgs = pdf_to_pil(pdf_file.read(), max_pages=12)
                                result = extract_questions_from_pdf(api_key, imgs)
                                new_qs = result.get("questions", [])
                                existing = load_bank()
                                max_id = max((q.get("id", 0) for q in existing), default=0)
                                for j, q in enumerate(new_qs):
                                    q["id"] = max_id + j + 1
                                existing.extend(new_qs)
                                save_bank(existing)
                                st.success(f"✅ 成功导入 {len(new_qs)} 道题！")
                                st.rerun()
                            except json.JSONDecodeError:
                                st.error("JSON 解析失败，请重试")
                            except Exception as e:
                                st.error(f"提取失败: {e}")

                if bank and st.button("🗑️ 清空全部题库", key="admin_clear"):
                    save_bank([])
                    st.success("题库已清空")
                    st.rerun()
            elif pwd:
                st.error("密码错误")

        st.markdown("""
<div style="text-align:center;padding:.8rem 0 0;color:#1E2D45;font-size:.7rem;line-height:2;">
  <p>📄 PDF · JPG · PNG</p>
  <p>🤖 Gemini 2.5 Flash</p>
  <p>🎙️ zh-CN-YunxiNeural (云希)</p>
</div>""", unsafe_allow_html=True)

    return api_key


# ─── Main ─────────────────────────────────────────────────────────────────────────
def main():
    for k in ("qbank_selected", "ai_result", "last_source"):
        if k not in st.session_state:
            st.session_state[k] = None

    api_key = render_sidebar()

    st.markdown("""
<div class="hero-wrap">
  <div class="hero-icon">🏆</div>
  <h1 class="hero-title">AMC 8 智学助手</h1>
  <p class="hero-sub">AI · 竞赛数学 · 趣味解题</p>
  <span class="hero-badge">✨ 幽默教练 AI 驱动 · 让每道题都有故事</span>
</div>""", unsafe_allow_html=True)

    # 题库题目分支
    if st.session_state.get("qbank_selected"):
        q = st.session_state.pop("qbank_selected")
        st.markdown(
            f'<div class="sec-header" style="border-color:rgba(99,102,241,.4);border-radius:14px;border-bottom:1px solid rgba(99,102,241,.4);">'
            f'<p style="color:#818CF8;font-size:.9rem;">📚 题库题目 #{q.get("id","?")} · '
            f'{q.get("topic","—")} · {q.get("difficulty","—")}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sec-body-wrap">', unsafe_allow_html=True)
        st.markdown(_sanitize_latex(q.get("content", "")))
        st.markdown('</div>', unsafe_allow_html=True)

        if not api_key:
            st.warning("请在左侧边栏输入 Gemini API Key")
        else:
            _clear_tts_cache()
            with st.spinner("🧠 AI 教练正在认真读题中..."):
                try:
                    qbank_result = analyze_question(
                        api_key,
                        [f"请分析以下AMC 8题目：\n\n{q.get('content','')}"]
                    )
                    st.session_state["ai_result"] = qbank_result
                    st.session_state["last_source"] = "qbank"
                    render_result(qbank_result, key_suffix="qbank")
                except Exception as e:
                    st.error(f"分析出错: {e}")
        st.markdown(
            '<div class="footer"><p>🏆 AMC 8 智学助手 · Powered by Gemini 2.5 Flash & Edge-TTS</p></div>',
            unsafe_allow_html=True
        )
        return

    # 输入 Tab
    tab_img, tab_txt = st.tabs(["📤 上传图片 / PDF", "✏️ 手动输入题目"])

    with tab_img:
        st.markdown(
            '<p style="color:#8899BB;font-size:.875rem;margin-bottom:.8rem;">'
            '支持上传 AMC 8 题目截图、扫描件或 PDF 文件（PDF 最多识别前 5 页）</p>',
            unsafe_allow_html=True
        )
        uploaded = st.file_uploader(
            "拖拽或点击上传",
            type=["jpg", "jpeg", "png", "pdf"],
            label_visibility="collapsed"
        )

        if uploaded:
            content_parts = []
            preview_imgs = []

            if uploaded.type == "application/pdf":
                with st.spinner("📄 解析 PDF 中..."):
                    imgs = pdf_to_pil(uploaded.read(), max_pages=5)
                preview_imgs = imgs[:3]
                content_parts = imgs
                st.info(f"PDF 共 {len(imgs)} 页已加载，将分析全部内容")
            else:
                img = Image.open(uploaded)
                preview_imgs = [img]
                content_parts = [img]

            if preview_imgs:
                cols = st.columns(min(len(preview_imgs), 3))
                for i, im in enumerate(preview_imgs[:3]):
                    with cols[i]:
                        st.image(
                            im,
                            caption=f"第 {i+1} 页" if len(preview_imgs) > 1 else "上传图片",
                            use_container_width=True
                        )

            st.markdown("<br>", unsafe_allow_html=True)

            if not api_key:
                st.warning("⚠️ 请先在左侧边栏填写 Gemini API Key")
            else:
                c1, c2, c3 = st.columns([1, 2, 1])
                with c2:
                    go = st.button("🚀 开始智能解题", use_container_width=True, key="go_img")
                if go:
                    _clear_tts_cache()
                    with st.spinner("🧠 AI 教练正在认真读题，好题值得细品..."):
                        try:
                            st.session_state["ai_result"] = analyze_question(
                                api_key,
                                ["请分析图片中的数学题目，按格式详细解答："] + content_parts
                            )
                            st.session_state["last_source"] = "img"
                        except Exception as e:
                            st.error(f"解析失败: {e}")
                            st.session_state["ai_result"] = None

    with tab_txt:
        st.markdown(
            '<p style="color:#8899BB;font-size:.875rem;margin-bottom:.5rem;">'
            '直接粘贴或手打题目，AI 教练立刻为你讲解</p>',
            unsafe_allow_html=True
        )
        q_text = st.text_area(
            "题目内容",
            placeholder=(
                "例如：\n\n"
                "If a + b = 10 and ab = 24, what is a² + b²?\n\n"
                "(A) 4   (B) 28   (C) 52   (D) 76   (E) 100"
            ),
            height=190,
            label_visibility="collapsed"
        )

        if not api_key:
            st.warning("⚠️ 请先在左侧边栏填写 Gemini API Key")
        else:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                go_t = st.button("🚀 开始智能解题", use_container_width=True, key="go_txt")
            if go_t:
                if not q_text.strip():
                    st.warning("请输入题目内容")
                else:
                    _clear_tts_cache()
                    with st.spinner("🧠 AI 教练正在思考中，冷笑话准备就绪..."):
                        try:
                            st.session_state["ai_result"] = analyze_question(
                                api_key,
                                [f"请分析以下AMC 8题目：\n\n{q_text}"]
                            )
                            st.session_state["last_source"] = "txt"
                        except Exception as e:
                            st.error(f"解析失败: {e}")
                            st.session_state["ai_result"] = None

    # 统一渲染结果
    if st.session_state.get("ai_result"):
        st.divider()
        render_result(st.session_state["ai_result"], key_suffix="main")

    st.markdown("""
<div class="footer">
  <p>🏆 AMC 8 智学助手 · AI 趣味竞赛辅导 · 让每个孩子爱上数学</p>
  <p>Powered by Gemini 2.5 Flash &nbsp;·&nbsp; TTS by Edge-TTS (云希) &nbsp;·&nbsp; Built with Streamlit</p>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
