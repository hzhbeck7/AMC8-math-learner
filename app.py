"""
AMC 8 智学助手 — app.py
技术栈: Streamlit + Google Gemini 2.5 Flash + Edge-TTS (云希)

功能:
  1. AI 解题（三段式：数学小剧场 / 教练透视眼 / 逻辑拆解步）
  2. 🌟 脚手架式提示（逐步给思路，引导思考）
  3. 🌟 自动生成可视化几何示意图（matplotlib SVG）
  4. 🌟 学习进度仪表盘（user_profile.json + 图表）
  5. 🌟 双向语音交互（孩子说思路，AI 评判）
  6. 题库管理后台（PDF 批量导入）
"""

import streamlit as st
import google.generativeai as genai
import asyncio
import threading
import tempfile
import os
import io
import re
import json
import time
from datetime import datetime
from PIL import Image
import fitz  # PyMuPDF
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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

/* Sidebar inputs override */
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

/* Section Cards */
.sc {
    background:var(--card-bg); border:1px solid var(--border);
    border-radius:16px; padding:1.4rem 1.6rem;
    margin:1rem 0; position:relative; overflow:hidden;
    backdrop-filter:blur(8px);
}
.sc::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    border-radius:16px 16px 0 0;
}
.sc-t::before { background:linear-gradient(90deg,#F5C842,#FB923C); }
.sc-c::before { background:linear-gradient(90deg,#3B82F6,#8B5CF6); }
.sc-l::before { background:linear-gradient(90deg,#22C55E,#16A34A); }
.sc-h::before { background:linear-gradient(90deg,#EC4899,#F43F5E); }
.sc-v::before { background:linear-gradient(90deg,#06B6D4,#3B82F6); }
.sc-r::before { background:linear-gradient(90deg,#A855F7,#EC4899); }

.sc-deco {
    position:absolute; right:1.2rem; bottom:.4rem;
    font-size:5.5rem; opacity:.04; pointer-events:none; user-select:none;
    line-height:1;
}
.sc-label {
    font-family:'ZCOOL XiaoWei',serif; font-size:1.22rem;
    margin:0 0 .85rem; display:flex; align-items:center; gap:.45rem;
}
.sc-body { line-height:1.95; font-size:.93rem; color:var(--text); }

/* Cards built via st.container — KaTeX/markdown lives in a stylable wrapper */
.sc-md-wrap {
    background:var(--card-bg); border:1px solid var(--border);
    border-radius:16px; padding:1.4rem 1.6rem 1.4rem 1.6rem;
    margin:1rem 0; position:relative; overflow:hidden;
    backdrop-filter:blur(8px);
}
.sc-md-wrap::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    border-radius:16px 16px 0 0;
}
.sc-md-wrap.sc-t::before { background:linear-gradient(90deg,#F5C842,#FB923C); }
.sc-md-wrap.sc-c::before { background:linear-gradient(90deg,#3B82F6,#8B5CF6); }
.sc-md-wrap.sc-l::before { background:linear-gradient(90deg,#22C55E,#16A34A); }
.sc-md-wrap p, .sc-md-wrap li, .sc-md-wrap span,
.sc-md-wrap div, .sc-md-wrap strong, .sc-md-wrap em {
    color: var(--text) !important;
    font-size: .93rem;
    line-height: 1.95;
}
.sc-md-wrap h1, .sc-md-wrap h2, .sc-md-wrap h3, .sc-md-wrap h4 {
    color: var(--text) !important;
    font-family: 'Noto Sans SC', sans-serif !important;
    font-weight: 600 !important;
    margin: .8rem 0 .4rem !important;
}
.sc-md-wrap code {
    background: rgba(245,200,66,.1) !important;
    color: #F5C842 !important;
    padding: .1rem .35rem !important;
    border-radius: 4px !important;
}
/* KaTeX color overrides for dark theme */
.sc-md-wrap .katex { color: #F5C842 !important; font-size: 1.05em !important; }
.sc-md-wrap .katex .mord, .sc-md-wrap .katex .mbin,
.sc-md-wrap .katex .mrel, .sc-md-wrap .katex .mopen,
.sc-md-wrap .katex .mclose, .sc-md-wrap .katex .mpunct,
.sc-md-wrap .katex .minner, .sc-md-wrap .katex .mop,
.sc-md-wrap .katex .mathnormal, .sc-md-wrap .katex .mathit,
.sc-md-wrap .katex .mathbf {
    color: #FFE580 !important;
}
.sc-md-wrap .katex-display {
    background: rgba(245,200,66,.04);
    border-left: 2px solid rgba(245,200,66,.4);
    padding: .6rem 1rem;
    border-radius: 6px;
    margin: .6rem 0 !important;
}
.lbl-t { color:#F5C842; }
.lbl-c { color:#60A5FA; }
.lbl-g { color:#4ADE80; }
.lbl-h { color:#F472B6; }
.lbl-v { color:#22D3EE; }
.lbl-r { color:#C084FC; }

/* Hint chips */
.hint-step {
    background: rgba(244, 114, 182, 0.08);
    border-left: 3px solid #F472B6;
    border-radius: 8px;
    padding: .9rem 1.1rem;
    margin: .6rem 0;
    line-height: 1.85;
}
.hint-num {
    display: inline-block;
    background: linear-gradient(135deg,#EC4899,#F43F5E);
    color: white;
    width: 1.6rem; height: 1.6rem;
    border-radius: 50%;
    text-align: center;
    line-height: 1.6rem;
    font-weight: 700;
    margin-right: .5rem;
    font-size: .85rem;
}

/* Stats cards */
.stat-card {
    background: linear-gradient(135deg, rgba(245,200,66,.08), rgba(245,200,66,.02));
    border: 1px solid rgba(245,200,66,.25);
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
}
.stat-num {
    font-family: 'ZCOOL XiaoWei', serif;
    font-size: 2.2rem;
    color: #F5C842;
    line-height: 1;
    margin: 0;
}
.stat-label {
    color: #8899BB;
    font-size: .78rem;
    margin: .35rem 0 0;
    letter-spacing: .05em;
}

/* Achievement badges */
.badge {
    display: inline-block;
    margin: .25rem;
    padding: .35rem .75rem;
    border-radius: 20px;
    font-size: .8rem;
    border: 1px solid rgba(245,200,66,.4);
    background: rgba(245,200,66,.1);
    color: #FCD34D;
}
.badge-locked {
    border-color: rgba(255,255,255,.1);
    background: rgba(255,255,255,.03);
    color: #4A5F80;
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
}

[data-testid="stFileUploader"] {
    background:rgba(245,200,66,.03) !important;
    border:2px dashed rgba(245,200,66,.35) !important;
    border-radius:14px !important;
}
[data-testid="stFileUploader"] * { color:#D0DCF0 !important; }

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

hr { border-color:var(--border) !important; margin:1.4rem 0 !important; }
.stSpinner > div { border-top-color:var(--gold) !important; }
.stSuccess,.stInfo,.stWarning,.stError { border-radius:10px !important; }

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

/* Feedback verdict bar */
.verdict {
    border-radius: 10px; padding: .9rem 1.2rem;
    margin: .8rem 0; font-weight: 600;
}
.verdict-correct { background: linear-gradient(90deg,rgba(34,197,94,.15),rgba(34,197,94,.05)); border:1px solid rgba(34,197,94,.4); color:#86EFAC; }
.verdict-partial { background: linear-gradient(90deg,rgba(245,158,11,.15),rgba(245,158,11,.05)); border:1px solid rgba(245,158,11,.4); color:#FCD34D; }
.verdict-wrong   { background: linear-gradient(90deg,rgba(239,68,68,.15),rgba(239,68,68,.05)); border:1px solid rgba(239,68,68,.4); color:#FCA5A5; }

@media (max-width:768px) {
    .sc { padding:1rem 1.1rem; }
    .hero-wrap { padding:1.2rem .5rem .8rem; }
    .sc-deco { display:none; }
    .stat-num { font-size:1.7rem; }
}

.footer { text-align:center; padding:2rem 0 1rem; color:#1E2D45; font-size:.72rem; line-height:1.9; }
</style>
""", unsafe_allow_html=True)


# ─── Constants & Files ───────────────────────────────────────────────────────────
QUESTION_BANK_FILE = "question_bank.json"
USER_PROFILE_FILE  = "user_profile.json"


def get_admin_password() -> str:
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return os.environ.get("ADMIN_PASSWORD", "amc8admin2025")


# ─── JSON helpers ────────────────────────────────────────────────────────────────
def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_bank():        return _load_json(QUESTION_BANK_FILE, [])
def save_bank(d):       _save_json(QUESTION_BANK_FILE, d)
def load_profile():
    return _load_json(USER_PROFILE_FILE, {
        "total_solved": 0,
        "by_topic": {},          # {topic: {"count": int, "total_seconds": float}}
        "by_difficulty": {},     # {"简单"/"中等"/"困难": int}
        "history": [],           # list of {ts, topic, difficulty, seconds}
        "achievements": [],      # list of unlocked badge ids
        "first_solved_at": None,
    })
def save_profile(p):    _save_json(USER_PROFILE_FILE, p)


# ─── Achievement system ──────────────────────────────────────────────────────────
ACHIEVEMENTS = [
    {"id": "first_step",   "name": "🌱 初出茅庐",     "desc": "完成第 1 道题",  "check": lambda p: p["total_solved"] >= 1},
    {"id": "ten_streak",   "name": "🔥 渐入佳境",     "desc": "完成 10 道题",  "check": lambda p: p["total_solved"] >= 10},
    {"id": "fifty_master", "name": "⚡ 久经沙场",     "desc": "完成 50 道题",  "check": lambda p: p["total_solved"] >= 50},
    {"id": "hundred_hero", "name": "🏆 百题斩",       "desc": "完成 100 道题", "check": lambda p: p["total_solved"] >= 100},
    {"id": "geo_lover",    "name": "📐 几何小达人",   "desc": "几何题做满 5 道", "check": lambda p: p["by_topic"].get("几何", {}).get("count", 0) >= 5},
    {"id": "algebra_lover","name": "🔢 代数小达人",   "desc": "代数题做满 5 道", "check": lambda p: p["by_topic"].get("代数", {}).get("count", 0) >= 5},
    {"id": "all_topics",   "name": "🌈 全能选手",     "desc": "5 大领域均涉猎", "check": lambda p: len([t for t in ["几何","代数","数论","组合","概率"] if p["by_topic"].get(t,{}).get("count",0) >= 1]) >= 5},
    {"id": "hard_solver",  "name": "💎 硬骨头",       "desc": "完成 3 道困难题", "check": lambda p: p["by_difficulty"].get("困难", 0) >= 3},
]

def check_achievements(profile):
    new_unlocks = []
    for a in ACHIEVEMENTS:
        if a["id"] not in profile["achievements"] and a["check"](profile):
            profile["achievements"].append(a["id"])
            new_unlocks.append(a)
    return new_unlocks


def record_solved(topic: str, difficulty: str, seconds: float):
    profile = load_profile()
    profile["total_solved"] += 1
    if profile["first_solved_at"] is None:
        profile["first_solved_at"] = datetime.now().isoformat()

    t = profile["by_topic"].setdefault(topic, {"count": 0, "total_seconds": 0.0})
    t["count"] += 1
    t["total_seconds"] += float(seconds)

    profile["by_difficulty"][difficulty] = profile["by_difficulty"].get(difficulty, 0) + 1
    profile["history"].append({
        "ts": datetime.now().isoformat(),
        "topic": topic,
        "difficulty": difficulty,
        "seconds": float(seconds),
    })
    if len(profile["history"]) > 500:
        profile["history"] = profile["history"][-500:]

    new_unlocks = check_achievements(profile)
    save_profile(profile)
    return new_unlocks


# ─── PDF / image helpers ─────────────────────────────────────────────────────────
def pdf_to_pil(pdf_bytes, max_pages=10):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    imgs = []
    for i, page in enumerate(doc):
        if i >= max_pages: break
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        imgs.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    doc.close()
    return imgs


# ─── Gemini ───────────────────────────────────────────────────────────────────────
def _model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


TUTOR_PROMPT = r"""你是一位风趣幽默、充满激情的奥数教练，专门辅导AMC 8竞赛。
风格：说话接地气、爱用比喻和段子、善于鼓励孩子。

请分析题目，严格按以下Markdown格式输出：

## 🎭 【数学小剧场】
讲一个与本题知识点相关的数学家故事或趣味历史（150字左右，生动有趣）。

## 🔍 【教练透视眼】
简洁总结本题核心知识点和考点（要点列表）。

## 🧩 【逻辑拆解步】
分步骤、引导式讲解解题逻辑。要求：
- 语言幽默接地气，像朋友聊天
- 用生动比喻（如把勾股定理比作三角形的"铁三角"关系）
- 必须包含1-2个冷笑话或鼓励语
- 引导思维过程，不只给答案
- 最后给出正确答案

【数学公式格式 — 非常重要】
所有数学符号、公式、表达式 **必须** 用 LaTeX 包裹起来，规则如下：
- 行内公式用单美元符号：$3^5$、$C(3,1) 	imes 2^5$、$a^2+b^2=c^2$
- 独立成行的公式用双美元符号：$$	ext{总方案数} = 3^5 - C(3,1)\cdot 2^5 + C(3,2)\cdot 1^5$$
- **不要**用 \( \) 或 \[ \]，只用 $ 和 $$
- 一定要写 	imes 而不是 ×（让 KaTeX 渲染），\cdot 而不是 ·
- 分数写作 rac{a}{b}，根号写作 \sqrt{x}，求和写作 \sum
- 中文文字和数学符号交替时，确保数学部分都包在 $...$ 里
- 反例（错误）：总方案数 = 3^5 - C(3,1) 	imes 2^5
- 正例（正确）：总方案数 $= 3^5 - C(3,1) 	imes 2^5$

## 🏷️ 【元数据】
- 知识点分类：从"几何/代数/数论/组合/概率"中选一个
- 难度：从"简单/中等/困难"中选一个
- 是否需要图形：是/否

输出元数据时严格按以下格式（一定要在最后）：
META_TOPIC: 几何
META_DIFFICULTY: 中等
META_NEED_FIG: 是
"""


def analyze_question(api_key: str, parts: list) -> str:
    response = _model(api_key).generate_content([TUTOR_PROMPT] + parts)
    return response.text


# ─── Hint mode (scaffolded prompts) ──────────────────────────────────────────────
HINT_SYSTEM = """你是一位耐心的AMC 8奥数教练，使用"苏格拉底式提问"启发孩子。
你会收到一道题目和当前进度（已经给了几个提示）。
你的任务是只给"下一步"的提示，让孩子自己想出解法。

规则：
1. 提示要简短（每条 1-3 句话），重在启发，不直接给答案
2. 提示要循序渐进：第1步通常是"识别题型/找关键信息"，第2步是"想到核心方法/公式"，
   第3步是"具体执行的关键技巧"，第4步是"算到一半时容易卡住的地方"，第5步才揭晓答案
3. 用提问式语气（"你能想到...吗？""注意到了吗，这里..."）
4. 加一句鼓励或冷笑话
5. 每条提示**不要重复**之前已经给出的内容

请只输出一段提示文本（不要标题、不要markdown、不要"提示N："前缀），结尾加 1 句话的小鼓励。"""

def get_next_hint(api_key: str, question_text: str, hints_given: list, image_parts: list = None) -> str:
    """Return the next progressive hint. image_parts is an optional list of PIL Images."""
    history = ""
    if hints_given:
        history = "\n\n已经给出的提示历史:\n" + "\n".join(
            f"提示 {i+1}: {h}" for i, h in enumerate(hints_given)
        )
    user_msg = (
        f"题目（请仔细阅读，{'见下方图片' if image_parts else '见下文文字'}）：\n"
        f"{question_text or '(图片中的题目)'}\n\n"
        f"现在请给出第 {len(hints_given)+1} 步提示。{history}"
    )
    parts = [HINT_SYSTEM, user_msg]
    if image_parts:
        parts.extend(image_parts)
    response = _model(api_key).generate_content(parts)
    return response.text.strip()


# ─── Visualization (geometry SVG via matplotlib) ─────────────────────────────────
VIZ_PROMPT = """你是一位数学教学可视化专家。我会给你一道AMC 8数学题。
如果题目涉及几何图形（三角形、圆、矩形、坐标系、函数图像等）或可以用图示帮助理解，
请生成 Python matplotlib 代码画出示意图。

要求：
1. 代码必须可以直接运行，**不要**任何解释文字、注释外的话
2. 代码以 ```python 开头，以 ``` 结尾
3. 使用 fig, ax = plt.subplots(figsize=(7,5))
4. 用 ax.set_aspect('equal') （几何题）或合适的布局
5. 颜色友好：使用 #F5C842（金）、#60A5FA（蓝）、#F472B6（粉）、#4ADE80（绿）等
6. 必须包含 plt.tight_layout() 以及标注关键点/边长
7. 不要 plt.show() 或 plt.savefig()，main 程序会自己保存
8. 背景色用 fig.patch.set_facecolor('#0C1829')，文字白色 ax.tick_params(colors='white')
9. 如果题目完全无法可视化（纯抽象代数/数论），输出 ```python\n# NO_VIZ\n```

只输出代码块，不要其他任何文字。"""


def generate_viz_code(api_key: str, question_text: str, image_parts: list = None) -> str | None:
    """Ask Gemini to write matplotlib code for the question."""
    parts = [VIZ_PROMPT, f"题目:\n{question_text or '(图片中的题目)'}"]
    if image_parts:
        parts.extend(image_parts)
    response = _model(api_key).generate_content(parts)
    code_text = response.text.strip()
    m = re.search(r"```python\s*\n(.*?)```", code_text, re.DOTALL)
    if not m:
        return None
    code = m.group(1).strip()
    if "NO_VIZ" in code:
        return None
    return code


def execute_viz_code(code: str) -> bytes | None:
    """Run code in a sandboxed namespace, capture the figure as SVG bytes."""
    try:
        # Safety: only allow plt / np
        local_ns = {"plt": plt, "np": np, "matplotlib": matplotlib}
        plt.close("all")
        exec(code, local_ns)
        fig = plt.gcf()
        # Force dark theme adjustments if not set
        if not fig.patch.get_facecolor() or fig.patch.get_facecolor()[3] == 0:
            fig.patch.set_facecolor("#0C1829")
        for ax in fig.get_axes():
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#8899BB")
            if ax.get_title():
                ax.title.set_color("white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        plt.close("all")
        st.warning(f"图形渲染失败: {e}")
        return None


# ─── Voice feedback (孩子说思路 → AI 评判) ──────────────────────────────────────
VOICE_FEEDBACK_PROMPT = """你是一位善于倾听、鼓励孩子的奥数教练。
孩子用语音口述了自己的解题思路（已转成文字）。请评估这个思路。

输出格式（严格遵守）：
VERDICT: correct / partial / wrong
COMMENT: 一段 100-150 字的反馈，要：
- 先肯定孩子做对的部分（哪怕只是方向对）
- 然后指出问题或不严谨之处（如有）
- 最后给一句下一步建议或鼓励
- 风格幽默接地气、像朋友聊天，可以加个冷笑话

注意：
- correct = 思路完全正确
- partial = 大方向对但有小错误或漏洞
- wrong   = 思路有根本性错误"""

def evaluate_student_thinking(api_key: str, question_text: str, student_text: str, image_parts: list = None) -> dict:
    msg = (
        f"题目（{'见下方图片' if image_parts else '见下文文字'}）：\n"
        f"{question_text or '(图片中的题目)'}\n\n"
        f"孩子的口述思路：\n{student_text}\n\n"
        f"请评估并按规定格式输出。"
    )
    parts = [VOICE_FEEDBACK_PROMPT, msg]
    if image_parts:
        parts.extend(image_parts)
    response = _model(api_key).generate_content(parts)
    text = response.text.strip()
    verdict_m = re.search(r"VERDICT:\s*(\w+)", text)
    comment_m = re.search(r"COMMENT:\s*(.+)", text, re.DOTALL)
    return {
        "verdict": (verdict_m.group(1).lower() if verdict_m else "partial"),
        "comment": (comment_m.group(1).strip() if comment_m else text),
    }


# ─── Speech recognition (audio bytes → text) ────────────────────────────────────
def transcribe_audio(audio_bytes: bytes) -> str | None:
    """Convert recorded audio bytes (wav/webm) to Chinese text via Google Web API."""
    try:
        import speech_recognition as sr
    except Exception as e:
        st.error(f"未安装 SpeechRecognition: {e}")
        return None

    # Save to temp WAV (SpeechRecognition needs WAV/AIFF/FLAC)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_in:
        tmp_in.write(audio_bytes)
        in_path = tmp_in.name

    out_path = in_path  # try in-place first
    # If audio_recorder returns webm/ogg, ffmpeg (via pydub) is needed.
    # We try directly first.
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(out_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="zh-CN")
        return text
    except sr.UnknownValueError:
        st.warning("没听清呢，请再说一遍～")
        return None
    except Exception as e:
        # Try ffmpeg conversion
        try:
            import subprocess
            converted = in_path.replace(".wav", "_conv.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", in_path, "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", converted],
                check=True, capture_output=True
            )
            recognizer = sr.Recognizer()
            with sr.AudioFile(converted) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="zh-CN")
            os.unlink(converted)
            return text
        except Exception as e2:
            st.error(f"语音识别失败: {e2}")
            return None
    finally:
        try: os.unlink(in_path)
        except: pass


# ─── TTS (edge-tts → MP3 bytes) ─────────────────────────────────────────────────
def _clean_tts(text: str) -> str:
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"[🎭🔍🧩【】]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:3500]

def generate_audio(text: str):
    clean = _clean_tts(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        path = tmp.name
    result = {"ok": False, "error": ""}

    def _run():
        import edge_tts
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            comm = edge_tts.Communicate(clean, "zh-CN-YunxiNeural")
            loop.run_until_complete(comm.save(path))
            result["ok"] = True
        except Exception as e:
            result["error"] = str(e)
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=60)

    if result["ok"] and os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data
    if result["error"]:
        st.error(f"语音生成失败: {result['error']}")
    return None


# ─── Parse AI response ──────────────────────────────────────────────────────────
def parse_sections(text: str) -> dict:
    markers = {"theater": "数学小剧场", "coach": "教练透视眼", "logic": "逻辑拆解步"}
    positions = {}
    for key, kw in markers.items():
        idx = text.find(kw)
        if idx != -1:
            positions[key] = idx

    sections = {"theater": "", "coach": "", "logic": "", "raw": text}

    if positions:
        sorted_keys = sorted(positions, key=lambda k: positions[k])
        for i, k in enumerate(sorted_keys):
            nl = text.find("\n", positions[k])
            start = nl + 1 if nl != -1 else positions[k]
            if i + 1 < len(sorted_keys):
                nk = sorted_keys[i + 1]
                end = text.rfind("\n", 0, positions[nk])
                sections[k] = text[start:end if end > start else positions[nk]].strip()
            else:
                # Cut off META section
                end_m = re.search(r"META_TOPIC", text[start:])
                if end_m:
                    sections[k] = text[start:start + end_m.start()].strip()
                    # Clean up trailing markdown header for META
                    sections[k] = re.sub(r"##.*$", "", sections[k]).strip()
                else:
                    sections[k] = text[start:].strip()

    # Parse meta
    topic_m = re.search(r"META_TOPIC:\s*(\S+)", text)
    diff_m  = re.search(r"META_DIFFICULTY:\s*(\S+)", text)
    fig_m   = re.search(r"META_NEED_FIG:\s*(\S+)", text)
    sections["topic"] = topic_m.group(1) if topic_m else "未分类"
    sections["difficulty"] = diff_m.group(1) if diff_m else "中等"
    sections["need_fig"] = (fig_m.group(1).strip() == "是") if fig_m else False

    # Strip META block from logic display
    for k in ("theater", "coach", "logic"):
        sections[k] = re.sub(r"##\s*🏷️.*?(?=$)", "", sections[k], flags=re.DOTALL).strip()
        sections[k] = re.sub(r"META_\w+:.*", "", sections[k]).strip()

    return sections


def extract_questions_from_pdf(api_key: str, images: list) -> dict:
    prompt = (
        "请从这些PDF页面中提取所有数学题目，以纯JSON格式返回（不要加```代码块标记）。\n"
        '格式：{"questions":[{"id":1,"title":"编号或标题","content":"完整题目含选项",'
        '"topic":"几何/代数/数论/组合/概率","difficulty":"简单/中等/困难"}]}\n'
        "只返回JSON，不要其他内容。"
    )
    response = _model(api_key).generate_content([prompt] + images[:8])
    text = response.text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


# ─── Render result ──────────────────────────────────────────────────────────────
def _render_card(emoji: str, label: str, label_class: str, klass: str, body: str):
    """Render a styled card whose body is markdown (so LaTeX $...$ renders).
    Streamlit's st.markdown supports KaTeX natively; using a container with a
    custom CSS class lets us keep the gradient bar / glass effect."""
    body = _normalize_latex(body)
    with st.container():
        st.markdown(
            f'''<div class="sc-md-wrap {klass}">
  <div class="sc-deco">{emoji}</div>
  <p class="sc-label {label_class}">{emoji} {label}</p>
</div>''',
            unsafe_allow_html=True,
        )
        # Body with proper markdown + LaTeX rendering
        st.markdown(body)


def _normalize_latex(text: str) -> str:
    r"""Convert AI-generated LaTeX wrappers into Streamlit-friendly form.

    The model often emits forms that Streamlit's KaTeX won't render:
      - \( ... \)  → $...$
      - \[ ... \]  → $$...$$
      - bare \times / \frac outside any $...$  → wrap the line's math expr
    """
    if not text:
        return text
    # 1. \( \) → $ $
    text = re.sub(r"\\\(", "$", text)
    text = re.sub(r"\\\)", "$", text)
    text = re.sub(r"\\\[", "$$", text)
    text = re.sub(r"\\\]", "$$", text)

    # 2. Some models output e.g. "3^5 \\times 2^5" in plain text.
    #    Wrap obvious bare-LaTeX commands in $...$ so KaTeX renders them.
    #    Heuristic: lines that contain \command but no $ get auto-wrapped.
    def wrap_line(line):
        if "$" in line:                       # already has math delimiters
            return line
        if re.search(r"\\(times|frac|sqrt|cdot|div|pm|leq|geq|neq|approx)", line):
            # Wrap the segment containing math: simple approach — entire line
            # after a common Chinese punctuation or ":" / "=" if present.
            return f"${line}$" if len(line) < 200 else line
        return line

    # Operate line-by-line
    text = "\n".join(wrap_line(l) for l in text.split("\n"))
    return text


def render_result(result_text: str, question_text: str = "", api_key: str = ""):
    sec = parse_sections(result_text)

    # ── 数学小剧场
    if sec.get("theater"):
        _render_card("🎭", "数学小剧场", "lbl-t", "sc-t", sec["theater"])

    # ── Voice button
    tts_src = (sec.get("theater", "") + "\n\n" + sec.get("logic", "")).strip()
    if tts_src:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("🔊 听听教练怎么说", key="voice_play", use_container_width=True):
                st.session_state.pop("tts_audio", None)
                with st.spinner("🎙️ 云希老师正在录音，稍等..."):
                    ab = generate_audio(tts_src)
                if ab: st.session_state["tts_audio"] = ab
                else:  st.session_state["tts_error"] = True
        if st.session_state.get("tts_audio"):
            st.audio(st.session_state["tts_audio"], format="audio/mp3")
        if st.session_state.pop("tts_error", False):
            st.error("语音生成失败，请确保已安装 edge-tts")

    # ── 教练透视眼
    if sec.get("coach"):
        _render_card("🔍", "教练透视眼", "lbl-c", "sc-c", sec["coach"])

    # ── 可视化示意图 (新功能)
    if sec.get("need_fig") and api_key and question_text:
        with st.expander("📐 看看示意图（点击展开）", expanded=True):
            if "viz_svg" not in st.session_state or st.session_state.get("viz_for") != question_text:
                with st.spinner("🎨 正在生成几何示意图..."):
                    img_parts = st.session_state.get("question_images") or None
                    code = generate_viz_code(api_key, question_text, image_parts=img_parts)
                    if code:
                        svg_bytes = execute_viz_code(code)
                        if svg_bytes:
                            st.session_state["viz_svg"] = svg_bytes
                            st.session_state["viz_for"] = question_text
                        else:
                            st.session_state["viz_svg"] = None
                    else:
                        st.session_state["viz_svg"] = None

            if st.session_state.get("viz_svg"):
                st.markdown(
                    f'<div style="background:#0C1829;border:1px solid var(--border);border-radius:12px;padding:1rem;text-align:center;">'
                    f'{st.session_state["viz_svg"].decode("utf-8")}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.info("这道题不太好画图，咱们直接看文字解析吧 👀")

    # ── 逻辑拆解步
    if sec.get("logic"):
        _render_card("🧩", "逻辑拆解步", "lbl-g", "sc-l", sec["logic"])

    if not any(sec.get(k) for k in ("theater", "coach", "logic")):
        st.markdown(_normalize_latex(result_text))

    return sec  # caller may use topic/difficulty/etc


# ─── Hint Mode UI ────────────────────────────────────────────────────────────────
def render_hint_mode(api_key: str, question_text: str):
    """Scaffolded hint mode: progressive Socratic prompts."""
    st.markdown("""
<div class="sc sc-h">
  <div class="sc-deco">💡</div>
  <p class="sc-label lbl-h">💡 提示模式 · 一步步引导你思考</p>
  <p class="sc-body" style="color:#C0CCE0;font-size:.88rem;margin-bottom:.6rem;">
    我先不告诉你答案，咱们慢慢来。点下面的按钮，每点一次给一条提示～
  </p>
</div>""", unsafe_allow_html=True)

    hints = st.session_state.get("hints_given", [])

    # Display existing hints
    for i, h in enumerate(hints):
        st.markdown(f"""
<div class="hint-step">
  <span class="hint-num">{i+1}</span>
  <span>{h}</span>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if len(hints) < 5:
            label = "💡 给点提示" if not hints else f"💡 再给一点提示（已用 {len(hints)}/5）"
            if st.button(label, key="hint_btn", use_container_width=True):
                with st.spinner("🤔 教练在想怎么不剧透..."):
                    try:
                        img_parts = st.session_state.get("question_images") or None
                        nh = get_next_hint(api_key, question_text, hints, image_parts=img_parts)
                        hints.append(nh)
                        st.session_state["hints_given"] = hints
                        st.rerun()
                    except Exception as e:
                        st.error(f"提示生成失败: {e}")
        else:
            st.info("✨ 已经给完所有提示啦，下面看完整解析吧！")

    if hints:
        if st.button("🗑️ 重置提示", key="hint_reset"):
            st.session_state["hints_given"] = []
            st.rerun()


# ─── Voice feedback UI (孩子说思路) ──────────────────────────────────────────────
def render_voice_feedback(api_key: str, question_text: str):
    """Let the student record/type their thinking and get AI feedback."""
    st.markdown("""
<div class="sc sc-v">
  <div class="sc-deco">🎤</div>
  <p class="sc-label lbl-v">🎤 说说你的思路 · 教练给你点评</p>
  <p class="sc-body" style="color:#C0CCE0;font-size:.88rem;">
    用语音录音，或直接打字。把你怎么想这道题告诉教练，教练会判断你的思路对不对！
  </p>
</div>""", unsafe_allow_html=True)

    # Try audio_recorder_streamlit; fall back to text-only
    audio_bytes = None
    try:
        from audio_recorder_streamlit import audio_recorder
        st.markdown('<p style="color:#8899BB;font-size:.85rem;margin:.5rem 0 .3rem;">🎙️ 点击麦克风开始/停止录音：</p>', unsafe_allow_html=True)
        audio_bytes = audio_recorder(
            text="",
            recording_color="#F5C842",
            neutral_color="#60A5FA",
            icon_name="microphone",
            icon_size="2x",
            key="voice_recorder"
        )
    except ImportError:
        st.info("💡 提示：如想启用语音录制，请在 requirements.txt 添加 `audio-recorder-streamlit`")
    except Exception as e:
        st.warning(f"录音器加载失败: {e}")

    transcribed = ""
    if audio_bytes:
        st.audio(audio_bytes, format="audio/wav")
        if st.button("🔍 转换语音为文字", key="transcribe_btn"):
            with st.spinner("正在听你说..."):
                transcribed = transcribe_audio(audio_bytes) or ""
                if transcribed:
                    st.session_state["student_thought"] = transcribed

    student_thought = st.text_area(
        "或者直接打字（推荐，更稳定）：",
        value=st.session_state.get("student_thought", ""),
        placeholder="比如：我觉得这道题应该用勾股定理，先求出 AC 边的长度...",
        height=120,
        key="thought_input"
    )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🧐 让教练评判我的思路", key="eval_btn", use_container_width=True):
            if not student_thought.strip():
                st.warning("请先说出或写出你的思路～")
            else:
                with st.spinner("🤔 教练正在认真听你说..."):
                    try:
                        img_parts = st.session_state.get("question_images") or None
                        verdict = evaluate_student_thinking(api_key, question_text, student_thought, image_parts=img_parts)
                        st.session_state["eval_verdict"] = verdict
                    except Exception as e:
                        st.error(f"评判失败: {e}")

    v = st.session_state.get("eval_verdict")
    if v:
        klass = {"correct": "verdict-correct", "partial": "verdict-partial", "wrong": "verdict-wrong"}.get(v["verdict"], "verdict-partial")
        emoji = {"correct": "🎉 完全正确！", "partial": "👍 方向对了，还差一点点", "wrong": "🤔 思路需要调整一下"}.get(v["verdict"], "📝")
        st.markdown(f"""
<div class="verdict {klass}">
  <p style="margin:0 0 .5rem;font-size:1.05rem;">{emoji}</p>
  <p style="margin:0;line-height:1.85;font-weight:400;">{v['comment']}</p>
</div>""", unsafe_allow_html=True)


# ─── Progress dashboard ─────────────────────────────────────────────────────────
def render_progress_dashboard():
    profile = load_profile()

    st.markdown("""
<div class="sc sc-r">
  <div class="sc-deco">📊</div>
  <p class="sc-label lbl-r">📊 我的学习成就</p>
</div>""", unsafe_allow_html=True)

    total = profile["total_solved"]

    # Stat cards
    c1, c2, c3, c4 = st.columns(4)
    avg_seconds = (
        sum(h["seconds"] for h in profile["history"]) / len(profile["history"])
        if profile["history"] else 0
    )
    n_topics = len([t for t in profile["by_topic"].values() if t["count"] > 0])
    n_badges = len(profile["achievements"])

    for col, num, label in [
        (c1, total, "总题数"),
        (c2, n_topics, "涉猎领域"),
        (c3, f"{int(avg_seconds)}s", "平均用时"),
        (c4, n_badges, "成就徽章"),
    ]:
        with col:
            st.markdown(f"""
<div class="stat-card">
  <p class="stat-num">{num}</p>
  <p class="stat-label">{label}</p>
</div>""", unsafe_allow_html=True)

    if total == 0:
        st.info("📚 还没有学习记录哦，去做几道题吧！")
        return

    st.markdown("<br>", unsafe_allow_html=True)

    # Topic breakdown chart
    topics = list(profile["by_topic"].keys())
    if topics:
        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown('<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;font-size:1.1rem;margin:.5rem 0;">📚 各领域题量</p>', unsafe_allow_html=True)
            counts = [profile["by_topic"][t]["count"] for t in topics]
            fig, ax = plt.subplots(figsize=(6, 4), facecolor="#0C1829")
            ax.set_facecolor("#0C1829")
            colors = ["#60A5FA", "#F472B6", "#A78BFA", "#34D399", "#FB923C", "#F5C842"]
            bars = ax.bar(topics, counts, color=colors[:len(topics)])
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#8899BB")
            ax.set_ylabel("题数", color="white")
            for b, c in zip(bars, counts):
                ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.1,
                        str(c), ha="center", color="white", fontsize=10)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        with col_r:
            st.markdown('<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;font-size:1.1rem;margin:.5rem 0;">⏱️ 各领域平均用时（秒）</p>', unsafe_allow_html=True)
            avg_times = [
                profile["by_topic"][t]["total_seconds"] / max(1, profile["by_topic"][t]["count"])
                for t in topics
            ]
            fig, ax = plt.subplots(figsize=(6, 4), facecolor="#0C1829")
            ax.set_facecolor("#0C1829")
            bars = ax.barh(topics, avg_times, color=colors[:len(topics)])
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#8899BB")
            ax.set_xlabel("秒", color="white")
            for b, t in zip(bars, avg_times):
                ax.text(b.get_width() + 0.5, b.get_y() + b.get_height()/2,
                        f"{int(t)}s", va="center", color="white", fontsize=9)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        # Hint: longest topic
        if avg_times:
            slowest_idx = max(range(len(avg_times)), key=lambda i: avg_times[i])
            st.info(
                f"📌 教练观察：你在 **{topics[slowest_idx]}** 上花的时间最久（平均 "
                f"{int(avg_times[slowest_idx])} 秒）。多练几道这类题，你会越来越快！"
            )

    # Difficulty breakdown
    if profile["by_difficulty"]:
        st.markdown('<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;font-size:1.1rem;margin:1rem 0 .5rem;">🎯 难度分布</p>', unsafe_allow_html=True)
        diffs = ["简单", "中等", "困难"]
        diff_counts = [profile["by_difficulty"].get(d, 0) for d in diffs]
        if sum(diff_counts) > 0:
            fig, ax = plt.subplots(figsize=(6, 4), facecolor="#0C1829")
            ax.set_facecolor("#0C1829")
            colors_d = ["#4ADE80", "#F5C842", "#F87171"]
            present = [(d, c, col) for d, c, col in zip(diffs, diff_counts, colors_d) if c > 0]
            if present:
                wedges, texts, autotexts = ax.pie(
                    [p[1] for p in present],
                    labels=[p[0] for p in present],
                    colors=[p[2] for p in present],
                    autopct="%1.0f%%",
                    textprops={"color": "white", "fontsize": 11}
                )
                for at in autotexts:
                    at.set_color("#0C1829")
                    at.set_fontweight("bold")
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

    # Achievements
    st.markdown('<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;font-size:1.1rem;margin:1rem 0 .5rem;">🏅 成就徽章</p>', unsafe_allow_html=True)
    badges_html = ""
    for a in ACHIEVEMENTS:
        unlocked = a["id"] in profile["achievements"]
        klass = "badge" if unlocked else "badge badge-locked"
        title = a["name"] if unlocked else "🔒 ???"
        badges_html += f'<span class="{klass}" title="{a["desc"]}">{title}</span> '
    st.markdown(f'<div style="line-height:2.4;">{badges_html}</div>', unsafe_allow_html=True)

    if st.button("🗑️ 清空我的学习记录", key="clear_profile"):
        if st.session_state.get("confirm_clear"):
            save_profile({
                "total_solved": 0, "by_topic": {}, "by_difficulty": {},
                "history": [], "achievements": [], "first_solved_at": None
            })
            st.session_state["confirm_clear"] = False
            st.success("已清空！")
            st.rerun()
        else:
            st.session_state["confirm_clear"] = True
            st.warning("再点一次确认清空。")


# ─── Sidebar ────────────────────────────────────────────────────────────────────
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
            type="password", placeholder="AIzaSy...",
            help="前往 https://aistudio.google.com 免费获取"
        )

        # Quick stats in sidebar
        profile = load_profile()
        if profile["total_solved"] > 0:
            st.markdown(
                f'<p style="color:#94A3B8;font-size:.78rem;margin:.6rem 0 0;">'
                f'📊 已完成 <span style="color:#F5C842;font-weight:700;">'
                f'{profile["total_solved"]}</span> 道 · 解锁 '
                f'<span style="color:#F5C842;font-weight:700;">'
                f'{len(profile["achievements"])}</span> 枚徽章</p>',
                unsafe_allow_html=True
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
                    # reset hints/audio when new question loaded
                    st.session_state["hints_given"] = []
                    st.session_state["tts_audio"] = None
                    st.session_state["viz_svg"] = None
                    st.session_state["eval_verdict"] = None
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


# ─── Question handling helper ───────────────────────────────────────────────────
def handle_question(api_key: str, parts: list, question_text: str, image_parts: list = None):
    """Run full analysis pipeline + record progress.
    image_parts: list of PIL.Image objects when the question came from an image/PDF.
    These get re-used by hint mode / viz / voice feedback so AI sees the real question."""
    st.session_state["question_text"] = question_text
    st.session_state["question_images"] = image_parts or []
    st.session_state["tts_audio"] = None
    st.session_state["viz_svg"] = None
    st.session_state["hints_given"] = []
    st.session_state["eval_verdict"] = None

    start = time.time()
    with st.spinner("🧠 AI 教练正在认真读题，好题值得细品..."):
        try:
            st.session_state["ai_result"] = analyze_question(api_key, parts)
            st.session_state["solve_seconds"] = time.time() - start
            st.session_state["recorded"] = False  # not yet recorded
        except Exception as e:
            st.error(f"解析失败: {e}")
            st.session_state["ai_result"] = None


def maybe_record_progress(parsed_sec: dict):
    """Record solving stats once per result."""
    if st.session_state.get("recorded"):
        return
    if not st.session_state.get("ai_result"):
        return
    seconds = st.session_state.get("solve_seconds", 0)
    topic = parsed_sec.get("topic", "未分类")
    diff  = parsed_sec.get("difficulty", "中等")
    new_unlocks = record_solved(topic, diff, seconds)
    st.session_state["recorded"] = True
    if new_unlocks:
        for a in new_unlocks:
            st.success(f"🎉 解锁新成就：{a['name']} — {a['desc']}")
            st.balloons()


# ─── Main ───────────────────────────────────────────────────────────────────────
def main():
    # init state
    for k in ("qbank_selected", "ai_result", "tts_audio", "hints_given",
              "viz_svg", "viz_for", "question_text", "question_images",
              "solve_seconds", "recorded", "eval_verdict", "student_thought"):
        if k not in st.session_state:
            st.session_state[k] = None
    if not isinstance(st.session_state.get("hints_given"), list):
        st.session_state["hints_given"] = []

    api_key = render_sidebar()

    st.markdown("""
<div class="hero-wrap">
  <div class="hero-icon">🏆</div>
  <h1 class="hero-title">AMC 8 智学助手</h1>
  <p class="hero-sub">AI · 竞赛数学 · 趣味解题</p>
  <span class="hero-badge">✨ 幽默教练 AI 驱动 · 让每道题都有故事</span>
</div>""", unsafe_allow_html=True)

    # Top-level navigation: solve mode vs progress dashboard
    nav = st.radio(
        "导航",
        ["📝 解题练习", "📊 我的进度"],
        horizontal=True,
        label_visibility="collapsed",
        key="nav"
    )

    if nav == "📊 我的进度":
        render_progress_dashboard()
        st.markdown("""<div class="footer">
          <p>🏆 AMC 8 智学助手 · Built with Streamlit</p>
        </div>""", unsafe_allow_html=True)
        return

    # ── Q-bank quick load
    if st.session_state.get("qbank_selected"):
        q = st.session_state.pop("qbank_selected")
        question_text = q.get("content", "")
        st.markdown(f"""
<div class="sc" style="border-color:rgba(99,102,241,.4);margin-bottom:1.2rem;">
  <p style="color:#818CF8;font-size:.82rem;margin:0 0 .6rem;">
    📚 题库题目 #{q.get('id','?')} ·
    <span style="color:#60A5FA;">{q.get('topic','—')}</span> ·
    {q.get('difficulty','—')}
  </p>
  <div class="sc-body">{question_text.replace(chr(10),'<br>')}</div>
</div>""", unsafe_allow_html=True)

        if not api_key:
            st.warning("请在左侧边栏输入 Gemini API Key")
        else:
            handle_question(api_key, [f"请分析以下AMC 8题目：\n\n{question_text}"], question_text)

    # ── Input tabs
    tab_img, tab_txt = st.tabs(["📤 上传图片 / PDF", "✏️ 手动输入题目"])

    with tab_img:
        st.markdown(
            '<p style="color:#8899BB;font-size:.875rem;margin-bottom:.8rem;">'
            '支持上传 AMC 8 题目截图、扫描件或 PDF（最多识别前 5 页）</p>',
            unsafe_allow_html=True
        )
        uploaded = st.file_uploader("拖拽或点击上传", type=["jpg", "jpeg", "png", "pdf"],
                                    label_visibility="collapsed", key="upl_main")
        if uploaded:
            content_parts, preview_imgs, qtxt_for_record = [], [], "[图片题目]"

            if uploaded.type == "application/pdf":
                with st.spinner("📄 解析 PDF 中..."):
                    imgs = pdf_to_pil(uploaded.read(), max_pages=5)
                preview_imgs = imgs[:3]
                content_parts = imgs
                st.info(f"PDF 共 {len(imgs)} 页已加载")
            else:
                img = Image.open(uploaded)
                preview_imgs = [img]
                content_parts = [img]

            if preview_imgs:
                cols = st.columns(min(len(preview_imgs), 3))
                for i, im in enumerate(preview_imgs[:3]):
                    with cols[i]:
                        st.image(im, caption=f"第 {i+1} 页" if len(preview_imgs) > 1 else "上传图片",
                                 use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if not api_key:
                st.warning("⚠️ 请先在左侧边栏填写 Gemini API Key")
            else:
                c1, c2, c3 = st.columns([1, 2, 1])
                with c2:
                    if st.button("🚀 开始智能解题", use_container_width=True, key="go_img"):
                        handle_question(
                            api_key,
                            ["请分析图片中的数学题目，按格式详细解答："] + content_parts,
                            qtxt_for_record,
                            image_parts=content_parts,
                        )

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
            label_visibility="collapsed",
            key="qtxt_main"
        )

        if not api_key:
            st.warning("⚠️ 请先在左侧边栏填写 Gemini API Key")
        else:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                if st.button("🚀 开始智能解题", use_container_width=True, key="go_txt"):
                    if not q_text.strip():
                        st.warning("请输入题目内容")
                    else:
                        handle_question(
                            api_key,
                            [f"请分析以下AMC 8题目：\n\n{q_text}"],
                            q_text
                        )

    # ── Show result + scaffolded interactive panels
    if st.session_state.get("ai_result"):
        st.divider()
        question_text = st.session_state.get("question_text", "")

        # Sub-tabs: 完整解析 / 提示模式 / 我说思路
        sub_tabs = st.tabs(["📖 完整解析", "💡 提示模式（先别看答案）", "🎤 我来说思路"])

        with sub_tabs[0]:
            sec = render_result(
                st.session_state["ai_result"],
                question_text=question_text,
                api_key=api_key
            )
            maybe_record_progress(sec)

        # Question is "ready" if we have either text content or stored image parts
        question_ready = bool(question_text) or bool(st.session_state.get("question_images"))

        with sub_tabs[1]:
            if api_key and question_ready:
                render_hint_mode(api_key, question_text)
            else:
                st.info("等加载完题目和 API Key 就能用提示模式啦")

        with sub_tabs[2]:
            if api_key and question_ready:
                render_voice_feedback(api_key, question_text)
            else:
                st.info("等加载完题目和 API Key 就能说思路啦")

    st.markdown("""
<div class="footer">
  <p>🏆 AMC 8 智学助手 · AI 趣味竞赛辅导 · 让每个孩子爱上数学</p>
  <p>Powered by Gemini 2.5 Flash &nbsp;·&nbsp; TTS by Edge-TTS (云希) &nbsp;·&nbsp; Built with Streamlit</p>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
