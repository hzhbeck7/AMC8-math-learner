"""
AMC 8 智学助手 — MVP 版
─────────────────────────────────────────────────
核心功能（仅此五项）:
  1. PDF / 图片上传识别题目
  2. AI 讲题（三段式：小剧场 / 透视眼 / 拆解步）
  3. 分步骤提示模式（脚手架式引导）
  4. 语音讲解（edge-tts 云希）
  5. 几何可视化（GeoGebra 交互式 + 步骤化辅助线）

刻意删除: 成就系统、复杂进度、管理后台、社交、复杂动画
"""

import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import asyncio
import threading
import tempfile
import os
import io
import re
import json
from PIL import Image
import fitz  # PyMuPDF

from geometry_engine import (
    build_geogebra_html,
    GEOMETRY_TYPES,
    PRIMITIVE_KINDS,
    validate_geometry_spec,
)


# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AMC 8 智学助手",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS（与之前保持一致的暗色金色主题）────────────────────────────────────
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

html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(150deg, #0C1829 0%, #101E38 60%, #0A1E40 100%) !important;
    color: var(--text) !important;
    font-family: 'Noto Sans SC', sans-serif !important;
}
[data-testid="stAppViewContainer"]::after {
    content: ''; position: fixed; inset: 0;
    background-image: radial-gradient(rgba(245,200,66,0.06) 1px, transparent 1px);
    background-size: 44px 44px; pointer-events: none; z-index: 0;
}
[data-testid="block-container"] { position: relative; z-index: 1; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#080F1D 0%,#0C1829 100%) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
[data-testid="stSidebar"] .stTextInput > div > div > input,
[data-testid="stSidebar"] .stTextArea  > div > div > textarea {
    background: #1C2E4A !important; color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important; caret-color: #F5C842 !important;
}
[data-testid="stSidebar"] input[type="password"] {
    color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;
}

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

.sc-md-wrap {
    background:var(--card-bg); border:1px solid var(--border);
    border-radius:16px; padding:1.4rem 1.6rem; margin:1rem 0;
    position:relative; overflow:hidden; backdrop-filter:blur(8px);
}
.sc-md-wrap::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    border-radius:16px 16px 0 0;
}
.sc-md-wrap.sc-t::before { background:linear-gradient(90deg,#F5C842,#FB923C); }
.sc-md-wrap.sc-c::before { background:linear-gradient(90deg,#3B82F6,#8B5CF6); }
.sc-md-wrap.sc-l::before { background:linear-gradient(90deg,#22C55E,#16A34A); }
.sc-md-wrap.sc-h::before { background:linear-gradient(90deg,#EC4899,#F43F5E); }
.sc-md-wrap.sc-g::before { background:linear-gradient(90deg,#06B6D4,#3B82F6); }

.sc-deco {
    position:absolute; right:1.2rem; bottom:.4rem; font-size:5.5rem;
    opacity:.04; pointer-events:none; user-select:none; line-height:1;
}
.sc-label {
    font-family:'ZCOOL XiaoWei',serif; font-size:1.22rem;
    margin:0 0 .85rem; display:flex; align-items:center; gap:.45rem;
}
.lbl-t { color:#F5C842; } .lbl-c { color:#60A5FA; } .lbl-g { color:#4ADE80; }
.lbl-h { color:#F472B6; } .lbl-geo { color:#22D3EE; }

.sc-md-wrap p, .sc-md-wrap li, .sc-md-wrap span,
.sc-md-wrap div, .sc-md-wrap strong, .sc-md-wrap em {
    color: var(--text) !important; font-size: .93rem; line-height: 1.95;
}
.sc-md-wrap .katex { color: #FFE580 !important; font-size: 1.05em !important; }
.sc-md-wrap .katex-display {
    background: rgba(245,200,66,.04); border-left: 2px solid rgba(245,200,66,.4);
    padding: .6rem 1rem; border-radius: 6px; margin: .6rem 0 !important;
}

.hint-step {
    background: rgba(244, 114, 182, 0.08);
    border-left: 3px solid #F472B6; border-radius: 8px;
    padding: .9rem 1.1rem; margin: .6rem 0; line-height: 1.85;
}
.hint-num {
    display: inline-block; background: linear-gradient(135deg,#EC4899,#F43F5E);
    color: white; width: 1.6rem; height: 1.6rem; border-radius: 50%;
    text-align: center; line-height: 1.6rem; font-weight: 700;
    margin-right: .5rem; font-size: .85rem;
}

.stButton > button {
    background:linear-gradient(135deg,#F5C842,#F59E0B) !important;
    color:#0C1829 !important; font-weight:700 !important;
    border:none !important; border-radius:10px !important;
    padding:.55rem 1.4rem !important;
    font-family:'Noto Sans SC',sans-serif !important;
    font-size:.92rem !important;
    box-shadow:0 4px 14px rgba(245,200,66,.28) !important;
    transition:all .2s ease !important;
}
.stButton > button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 7px 22px rgba(245,200,66,.42) !important;
}

.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background: #1C2E4A !important;
    border: 1px solid rgba(245,200,66,.35) !important;
    border-radius: 10px !important; color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    caret-color: #F5C842 !important;
}
[data-testid="stFileUploader"] {
    background:rgba(245,200,66,.03) !important;
    border:2px dashed rgba(245,200,66,.35) !important;
    border-radius:14px !important;
}
[data-testid="stFileUploader"] * { color:#D0DCF0 !important; }

.stTabs [data-baseweb="tab-list"] {
    background:rgba(0,0,0,.22) !important;
    border-radius:10px !important; padding:4px !important; gap:4px !important;
}
.stTabs [data-baseweb="tab"] {
    background:transparent !important; color:var(--muted) !important;
    border-radius:8px !important;
}
.stTabs [aria-selected="true"] {
    background:rgba(245,200,66,.18) !important; color:var(--gold) !important;
}
hr { border-color:var(--border) !important; }

@media (max-width:768px) {
    .sc-md-wrap { padding:1rem 1.1rem; }
    .hero-wrap { padding:1.2rem .5rem .8rem; }
    .sc-deco { display:none; }
}
.footer { text-align:center; padding:2rem 0 1rem; color:#1E2D45; font-size:.72rem; line-height:1.9; }

/* ── Dialog (孩子讲思路) ── */
.sc-md-wrap.sc-d::before { background:linear-gradient(90deg,#A855F7,#EC4899); }
.lbl-d { color:#C084FC; }

.verdict {
    border-radius: 12px; padding: 1rem 1.2rem;
    margin: .8rem 0; line-height: 1.85;
}
.verdict-correct { background: linear-gradient(90deg,rgba(34,197,94,.15),rgba(34,197,94,.04)); border:1px solid rgba(34,197,94,.45); }
.verdict-partial { background: linear-gradient(90deg,rgba(245,158,11,.15),rgba(245,158,11,.04)); border:1px solid rgba(245,158,11,.45); }
.verdict-wrong   { background: linear-gradient(90deg,rgba(239,68,68,.15),rgba(239,68,68,.04)); border:1px solid rgba(239,68,68,.45); }

.verdict-headline { font-weight: 700; font-size: 1rem; margin: 0 0 .5rem; }
.verdict-correct .verdict-headline { color: #86EFAC; }
.verdict-partial .verdict-headline { color: #FCD34D; }
.verdict-wrong   .verdict-headline { color: #FCA5A5; }

.eval-section {
    margin: .65rem 0;
    color: #E0E7FF; font-size: .9rem;
}
.eval-label {
    display: inline-block; font-weight: 700;
    color: #94A3B8; font-size: .78rem;
    margin-right: .5rem; letter-spacing: .03em;
}
.weak-tag {
    display: inline-block; background: rgba(168,85,247,.15);
    border: 1px solid rgba(168,85,247,.4);
    color: #DDD6FE; padding: .2rem .65rem;
    border-radius: 14px; font-size: .78rem;
    margin: .15rem .25rem .15rem 0;
}
.follow-up-box {
    background: rgba(168,85,247,.08); border-left: 3px solid #A855F7;
    padding: .7rem 1rem; border-radius: 6px;
    margin: .65rem 0; color: #EEF2FF;
    font-style: italic;
}
</style>
""", unsafe_allow_html=True)


# ─── Helper: Gemini ─────────────────────────────────────────────────────────
def _model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


# ── Tutor prompt（讲题）──
TUTOR_PROMPT = r"""你是一位风趣幽默、充满激情的奥数教练，专门辅导AMC 8竞赛。
风格：说话接地气、爱用比喻和段子、善于鼓励孩子。

请分析题目，严格按以下Markdown格式输出：

## 🎭 【数学小剧场】
讲一个与本题知识点相关的数学家故事或趣味历史（150字左右，生动有趣）。

## 🔍 【教练透视眼】
简洁总结本题核心知识点和考点（要点列表）。

## 🧩 【逻辑拆解步】
分步骤、引导式讲解解题逻辑。要求：
- 语言幽默接地气
- 用生动比喻
- 必须包含 1-2 个冷笑话或鼓励语
- 引导思维过程，不只给答案
- 最后给出正确答案

【数学公式格式 — 非常重要】
所有数学符号必须用 LaTeX 包裹：
- 行内公式用 $...$，例如 $3^5$、$a^2+b^2=c^2$
- 独立公式用 $$...$$
- 不要用 \( \) 或 \[ \]
- 用 \times 而不是 ×，\frac{a}{b} 而不是 a/b
"""


# ── Hint prompt（脚手架式提示）──
HINT_SYSTEM = """你是一位耐心的AMC 8教练，使用苏格拉底式提问启发孩子。
你会收到一道题目和当前提示进度。只给"下一步"的提示，让孩子自己想出解法。

规则：
1. 提示要简短（每条 1-3 句），重在启发，不直接给答案
2. 循序渐进：第1步识题型，第2步选方法，第3步关键技巧，第4步易错点，第5步揭晓答案
3. 用提问式语气
4. 加一句鼓励或冷笑话
5. 不要重复之前已给出的内容

只输出一段提示文本（不要标题、不要 markdown、不要"提示N："前缀）。"""


# ── Geometry spec prompt（几何题→结构化 JSON）──
GEO_SPEC_PROMPT = r"""你是一位几何题分析专家。我会给你一道 AMC 8 题目。
请判断题目是否为几何题（涉及三角形/圆/坐标/多边形/对称等图形）。
若是，输出可视化所需的**结构化 JSON**。若不是，输出 {"geometry_type": "none"}。

【非常重要：你只输出 JSON，不写任何绘图代码，不写其他文字】

JSON Schema：
{
  "geometry_type": "triangle | circle | coord | similar | area | symmetry | polygon | none",
  "title": "简短题目类型描述（不超过20字）",
  "points": [
    {"name": "A", "x": 0, "y": 0},
    {"name": "B", "x": 4, "y": 0}
  ],
  "primitives": [
    {"id": "唯一id", "kind": "图元类型", ...kind对应的字段}
  ],
  "auxiliary_steps": [
    {"step": 1, "show": ["要显示的id列表"], "highlight": ["可选高亮id"], "narration": "本步说明"}
  ]
}

【支持的图元 kind 及字段】
- point: name, x, y
- segment: from, to              （from/to 是已定义的点名）
- ray:     from, to
- line:    from, to
- polygon: vertices(数组)
- circle_through: center, through    （圆心 + 经过点）
- circle_radius:  center, radius     （圆心 + 半径数值）
- tangent:        from, circle       （from 是点名，circle 是已有圆的 id）
- perpendicular:  from, to_line      （过某点作某线的垂线）
- altitude:       from, to_side(两点名数组)
- median:         from, to_side
- angle_bisector: a, vertex, c       （∠a-vertex-c 的角平分线）
- midpoint:       from, to, name
- right_angle:    from_a, at, from_c  （在 at 处标记 ∠from_a-at-from_c 的直角）
- angle_arc:      a, vertex, c       （标注角度数值）
- label:          x, y, text

【点的坐标规则】
- 用合理的整数或简单小数构造一个能凸显题意的图
- 范围一般在 -10 到 10 之间
- 例：等边三角形可用 A(0,0)、B(4,0)、C(2,3.46)

【auxiliary_steps 规则】
- 至少 2 步，最多 5 步
- 第一步通常显示原始图形
- 后续步骤逐步加入辅助线（高/中线/角平分线/切线等）
- narration 要简短中文，告诉孩子"为什么画这条线"
- show 字段是**累积**的（前一步的元素继续可见）

【样例】（三角形作高）
{
  "geometry_type": "triangle",
  "title": "等腰三角形作高",
  "points": [
    {"name":"A","x":2,"y":4}, {"name":"B","x":0,"y":0}, {"name":"C","x":4,"y":0}
  ],
  "primitives": [
    {"id":"tri","kind":"polygon","vertices":["A","B","C"]},
    {"id":"alt","kind":"altitude","from":"A","to_side":["B","C"]}
  ],
  "auxiliary_steps": [
    {"step":1, "show":["tri"], "narration":"先观察三角形 ABC"},
    {"step":2, "show":["tri","alt"], "highlight":["alt"], "narration":"从顶点 A 作底边 BC 的高"}
  ]
}

请只输出 JSON 对象，不要包在 ```json``` 里，不要其他任何文字。
若题目并非几何题，仅输出 {"geometry_type": "none"}。
"""


# ── Student-thinking evaluation prompt（孩子讲思路 → AI 点评 + 知识点诊断）──
# 这是产品最有潜力的方向：从"AI 讲给孩子听"升级为"AI 听孩子讲"，
# 通过持续对话判断孩子哪些知识点不牢，未来可演进为个性化辅导引擎。
EVAL_PROMPT = r"""你是一位善于倾听、懂教育心理学的 AMC 8 奥数教练。
孩子刚刚用自己的话讲了一遍解题思路。请像一个真正的老师那样：
1. 先认真听完，找到孩子做对的部分（哪怕只是方向对）
2. 找出思路里的真问题（概念不清？方法不对？计算粗心？逻辑断层？）
3. 推断孩子可能在哪个知识点不牢
4. 用鼓励、不打击的方式给反馈
5. 提出**一个**针对性的追问问题，引导孩子自己发现问题

【严格按以下 JSON 格式输出，不要包代码块标记，不要其他文字】

{
  "verdict": "correct | partial | wrong",
  "praise": "肯定孩子做对的部分（1-2句，具体、真诚）",
  "issue": "指出问题（1-2句，温和但准确；若 verdict=correct 则填空字符串）",
  "weak_concepts": ["可能不牢的知识点1", "知识点2"],
  "follow_up": "一个引导性追问问题（必须是问号结尾，启发思考而非给答案）",
  "encouragement": "一句加油话，可以幽默"
}

【知识点标签词表（weak_concepts 字段必须从中选）】
"代数运算" "方程求解" "因式分解" "分数运算" "比例与百分比"
"几何基础" "三角形性质" "圆的性质" "面积公式" "勾股定理" "相似与全等"
"坐标几何" "数论基础" "因数与倍数" "质数" "模运算"
"组合计数" "排列" "概率" "容斥原理" "递推与规律" "逻辑推理"
"读题理解" "粗心计算"

【verdict 判断标准】
- correct = 思路完全正确，结论也对
- partial = 大方向对但有小错误（计算错、漏情况、概念偏差）
- wrong   = 思路有根本性错误

只输出 JSON，不要任何其他文字。"""


def evaluate_student_thinking(api_key: str, question_text: str, student_text: str,
                              image_parts: list = None) -> dict:
    """评估孩子的解题思路。返回结构化反馈。"""
    msg = (
        f"题目（{'见下方图片' if image_parts else '见下文文字'}）：\n"
        f"{question_text or '(图片中的题目)'}\n\n"
        f"孩子的口述思路：\n{student_text}\n\n"
        f"请评估并按规定 JSON 格式输出。"
    )
    parts = [EVAL_PROMPT, msg]
    if image_parts:
        parts.extend(image_parts)
    raw = _model(api_key).generate_content(parts).text.strip()
    # Strip code fences if present
    raw = re.sub(r"^```[a-z]*\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return a soft response
        return {
            "verdict": "partial",
            "praise": "你愿意把自己的思路讲出来，这本身就很棒！",
            "issue": "教练这次没完全听明白你的描述",
            "weak_concepts": [],
            "follow_up": "可以再讲一遍吗？这次试试一步一步说清楚？",
            "encouragement": "把思路说清楚是数学家最重要的本事之一！",
        }


def analyze_question(api_key: str, parts: list) -> str:
    return _model(api_key).generate_content([TUTOR_PROMPT] + parts).text


def get_next_hint(api_key: str, question_text: str, hints_given: list, image_parts: list = None) -> str:
    history = ""
    if hints_given:
        history = "\n\n已经给出的提示历史:\n" + "\n".join(
            f"提示 {i+1}: {h}" for i, h in enumerate(hints_given)
        )
    user_msg = (
        f"题目（{'见下方图片' if image_parts else '见下文文字'}）：\n"
        f"{question_text or '(图片中的题目)'}\n\n"
        f"现在请给出第 {len(hints_given)+1} 步提示。{history}"
    )
    parts = [HINT_SYSTEM, user_msg]
    if image_parts:
        parts.extend(image_parts)
    return _model(api_key).generate_content(parts).text.strip()


def get_geometry_spec(api_key: str, question_text: str, image_parts: list = None) -> dict | None:
    """Ask AI to return geometry JSON. Returns None if not a geometry question."""
    parts = [GEO_SPEC_PROMPT, f"题目：\n{question_text or '(见图片)'}"]
    if image_parts:
        parts.extend(image_parts)
    raw = _model(api_key).generate_content(parts).text.strip()
    # Strip code fences if AI ignored instruction
    raw = re.sub(r"^```[a-z]*\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if spec.get("geometry_type") == "none":
        return None
    return validate_geometry_spec(spec)


# ─── PDF helpers ────────────────────────────────────────────────────────────
def pdf_to_pil(pdf_bytes, max_pages=5):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    imgs = []
    for i, page in enumerate(doc):
        if i >= max_pages: break
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        imgs.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    doc.close()
    return imgs


# ─── TTS ────────────────────────────────────────────────────────────────────
def _clean_tts(text: str) -> str:
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\$+([^$]+)\$+", r"\1", text)  # strip $...$ wrappers
    text = re.sub(r"\\(times|cdot)", "乘", text)
    text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1分之\2", text)
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
    t.start(); t.join(timeout=60)

    if result["ok"] and os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data
    if result["error"]:
        st.error(f"语音生成失败: {result['error']}")
    return None


# ─── Parse AI response into sections ────────────────────────────────────────
def _normalize_latex(text: str) -> str:
    if not text: return text
    text = re.sub(r"\\\(", "$", text)
    text = re.sub(r"\\\)", "$", text)
    text = re.sub(r"\\\[", "$$", text)
    text = re.sub(r"\\\]", "$$", text)
    return text


def parse_sections(text: str) -> dict:
    markers = {"theater": "数学小剧场", "coach": "教练透视眼", "logic": "逻辑拆解步"}
    positions = {}
    for key, kw in markers.items():
        idx = text.find(kw)
        if idx != -1: positions[key] = idx
    sections = {"theater": "", "coach": "", "logic": "", "raw": text}
    if not positions: return sections
    sorted_keys = sorted(positions, key=lambda k: positions[k])
    for i, k in enumerate(sorted_keys):
        nl = text.find("\n", positions[k])
        start = nl + 1 if nl != -1 else positions[k]
        if i + 1 < len(sorted_keys):
            nk = sorted_keys[i + 1]
            end = text.rfind("\n", 0, positions[nk])
            sections[k] = text[start:end if end > start else positions[nk]].strip()
        else:
            sections[k] = text[start:].strip()
    return sections


# ─── UI helpers ─────────────────────────────────────────────────────────────
def render_card(emoji: str, label: str, label_class: str, klass: str, body: str):
    st.markdown(
        f'<div class="sc-md-wrap {klass}">'
        f'  <div class="sc-deco">{emoji}</div>'
        f'  <p class="sc-label {label_class}">{emoji} {label}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_normalize_latex(body))


def render_result(result_text: str):
    """Three-section AI explanation."""
    sec = parse_sections(result_text)
    if sec["theater"]:
        render_card("🎭", "数学小剧场", "lbl-t", "sc-t", sec["theater"])

    # Voice button
    tts_src = (sec["theater"] + "\n\n" + sec["logic"]).strip()
    if tts_src:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("🔊 听听教练怎么说", key="voice_play", use_container_width=True):
                st.session_state.pop("tts_audio", None)
                with st.spinner("🎙️ 云希老师正在录音..."):
                    ab = generate_audio(tts_src)
                if ab: st.session_state["tts_audio"] = ab
        if st.session_state.get("tts_audio"):
            st.audio(st.session_state["tts_audio"], format="audio/mp3")

    if sec["coach"]:
        render_card("🔍", "教练透视眼", "lbl-c", "sc-c", sec["coach"])
    if sec["logic"]:
        render_card("🧩", "逻辑拆解步", "lbl-g", "sc-l", sec["logic"])


def render_hint_mode(api_key: str, question_text: str):
    st.markdown(
        '<div class="sc-md-wrap sc-h">'
        '  <div class="sc-deco">💡</div>'
        '  <p class="sc-label lbl-h">💡 提示模式 · 一步步引导思考</p>'
        '</div>', unsafe_allow_html=True
    )
    st.caption("我先不告诉你答案，咱们慢慢来。每点一次按钮，AI 教练给一条新提示。")

    hints = st.session_state.get("hints_given", [])
    for i, h in enumerate(hints):
        st.markdown(
            f'<div class="hint-step"><span class="hint-num">{i+1}</span><span>{h}</span></div>',
            unsafe_allow_html=True,
        )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if len(hints) < 5:
            label = "💡 给点提示" if not hints else f"💡 再给一点提示（{len(hints)}/5）"
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
            st.info("✨ 已给完所有提示，下面看完整解析吧！")

    if hints and st.button("🗑️ 重置提示", key="hint_reset"):
        st.session_state["hints_given"] = []
        st.rerun()


def render_geometry_panel(api_key: str, question_text: str):
    """Geometry visualization tab — uses GeoGebra via geometry_engine."""
    st.markdown(
        '<div class="sc-md-wrap sc-g">'
        '  <div class="sc-deco">📐</div>'
        '  <p class="sc-label lbl-geo">📐 交互式几何图 · 拖动点试试</p>'
        '</div>', unsafe_allow_html=True
    )
    st.caption("AI 把题目结构化后，由 GeoGebra 渲染交互式几何图。点击「下一步」逐步显示辅助线。")

    # Fetch / cache spec
    cached_for = st.session_state.get("geo_for")
    if cached_for != question_text:
        with st.spinner("🎨 AI 正在分析几何结构..."):
            try:
                img_parts = st.session_state.get("question_images") or None
                spec = get_geometry_spec(api_key, question_text, image_parts=img_parts)
                st.session_state["geo_spec"] = spec
                st.session_state["geo_for"] = question_text
            except Exception as e:
                st.error(f"几何分析失败: {e}")
                st.session_state["geo_spec"] = None

    spec = st.session_state.get("geo_spec")
    if not spec:
        st.info("🤔 这道题不太需要几何图（或 AI 判断它不是几何题）。直接看完整解析就好！")
        return

    # Render GeoGebra applet inside an iframe-isolated component
    html_str = build_geogebra_html(spec, height=520)
    components.html(html_str, height=720, scrolling=False)

    # Show structured summary for transparency / debugging
    with st.expander("🔬 查看 AI 生成的结构化数据（开发者视图）"):
        st.json({
            "geometry_type": spec.get("geometry_type"),
            "title": spec.get("title"),
            "n_points": len(spec.get("points", [])),
            "n_primitives": len(spec.get("primitives", [])),
            "n_steps": len(spec.get("auxiliary_steps", [])),
        })
        if st.checkbox("显示完整 JSON"):
            st.code(json.dumps(spec, ensure_ascii=False, indent=2), language="json")


def render_dialog_panel(api_key: str, question_text: str):
    """孩子用文字讲解题思路 → AI 评估 + 知识点诊断 + 苏格拉底式追问。

    这是产品发展方向的核心：通过持续对话理解孩子的真实掌握情况。
    MVP 阶段先用文字输入（最稳定），未来可加语音录制。"""
    st.markdown(
        '<div class="sc-md-wrap sc-d">'
        '  <div class="sc-deco">🎤</div>'
        '  <p class="sc-label lbl-d">🎤 我来讲思路 · 教练听你说</p>'
        '</div>', unsafe_allow_html=True
    )
    st.caption(
        "用自己的话讲一遍：你是怎么想这道题的？教练会认真听，"
        "找出你做对的地方，也帮你看清还差哪一步。"
    )

    student_text = st.text_area(
        "你的思路",
        value=st.session_state.get("student_thought", ""),
        placeholder=(
            "举例：\n"
            "我看到三角形 ABC 是等腰的，AB = AC = 5，BC = 6。\n"
            "我想从 A 作 BC 边的高，把它分成两个直角三角形。\n"
            "底边一半是 3，斜边是 5，用勾股定理算出高是 4...\n"
        ),
        height=160,
        key="student_thought_input",
        label_visibility="collapsed",
    )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🧐 让教练听听我的思路", key="eval_btn", use_container_width=True):
            if not student_text.strip():
                st.warning("先把思路写下来吧～")
            else:
                st.session_state["student_thought"] = student_text
                with st.spinner("🤔 教练正在认真听你说..."):
                    try:
                        img_parts = st.session_state.get("question_images") or None
                        verdict = evaluate_student_thinking(
                            api_key, question_text, student_text, image_parts=img_parts
                        )
                        st.session_state["eval_verdict"] = verdict
                    except Exception as e:
                        st.error(f"评估失败: {e}")

    v = st.session_state.get("eval_verdict")
    if v:
        klass_map = {"correct": "verdict-correct", "partial": "verdict-partial", "wrong": "verdict-wrong"}
        emoji_map = {"correct": "🎉 完全正确！", "partial": "👍 方向对了，还差一点点", "wrong": "🤔 思路需要调整一下"}
        klass = klass_map.get(v.get("verdict"), "verdict-partial")
        emoji = emoji_map.get(v.get("verdict"), "📝 教练点评")

        praise        = v.get("praise", "").strip()
        issue         = v.get("issue", "").strip()
        weak_concepts = v.get("weak_concepts", []) or []
        follow_up     = v.get("follow_up", "").strip()
        encouragement = v.get("encouragement", "").strip()

        weak_html = "".join(f'<span class="weak-tag">{w}</span>' for w in weak_concepts)

        # Build the verdict card piece by piece (only show non-empty fields)
        sections_html = f'<p class="verdict-headline">{emoji}</p>'
        if praise:
            sections_html += f'<div class="eval-section"><span class="eval-label">✅ 做得好</span>{praise}</div>'
        if issue:
            sections_html += f'<div class="eval-section"><span class="eval-label">⚠️ 注意</span>{issue}</div>'
        if weak_concepts:
            sections_html += (
                f'<div class="eval-section"><span class="eval-label">📚 可能要再练</span>{weak_html}</div>'
            )
        if encouragement:
            sections_html += f'<div class="eval-section" style="color:#FCD34D;">💪 {encouragement}</div>'

        st.markdown(f'<div class="verdict {klass}">{sections_html}</div>', unsafe_allow_html=True)

        # Follow-up question (Socratic) — separate emphasized box
        if follow_up:
            st.markdown(
                f'<div class="follow-up-box">'
                f'<span style="color:#C084FC;font-weight:600;">🤔 教练想追问你：</span><br>'
                f'{follow_up}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Continue-dialog button
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("🔄 我再讲一遍 / 回答追问", key="reset_eval", use_container_width=True):
                st.session_state["eval_verdict"] = None
                # Keep student_thought so they can edit and resubmit
                st.rerun()


# ─── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("""
<div style="text-align:center;padding:.8rem 0 .4rem;">
  <div style="font-size:2.6rem;">🏆</div>
  <p style="color:#F5C842;font-family:'ZCOOL XiaoWei',serif;
            font-size:1.15rem;margin:.25rem 0 .1rem;letter-spacing:.05em;">
    AMC 8 智学助手</p>
  <p style="color:#4A5F80;font-size:.75rem;margin:0;">让数学变有趣</p>
</div>""", unsafe_allow_html=True)
        st.divider()

        api_key = st.text_input(
            "🔑 Gemini API Key", type="password", placeholder="AIzaSy...",
            help="前往 https://aistudio.google.com 免费获取"
        )

        st.divider()
        st.markdown("""
<div style="color:#94A3B8;font-size:.85rem;line-height:2;">
<p style="color:#F5C842;font-family:'ZCOOL XiaoWei',serif;font-size:1rem;margin:.3rem 0;">📚 使用流程</p>
<p>① 输入 API Key</p>
<p>② 上传题目或粘贴文字</p>
<p>③ AI 讲题三段式</p>
<p>④ 不会用「提示模式」逐步引导</p>
<p>⑤ 几何题看「交互式图」</p>
<p>⑥ 听完后试试「我讲思路」</p>
</div>
""", unsafe_allow_html=True)

        st.markdown("""
<div style="text-align:center;padding:1rem 0 0;color:#1E2D45;font-size:.7rem;line-height:2;">
  <p>🤖 Gemini 2.5 Flash</p>
  <p>📐 GeoGebra 几何引擎</p>
  <p>🎙️ Edge-TTS 云希</p>
</div>
""", unsafe_allow_html=True)

    return api_key


# ─── Question handler ──────────────────────────────────────────────────────
def handle_question(api_key: str, parts: list, question_text: str, image_parts: list = None):
    """Run analysis + reset interactive state."""
    st.session_state["question_text"] = question_text
    st.session_state["question_images"] = image_parts or []
    st.session_state["tts_audio"] = None
    st.session_state["hints_given"] = []
    st.session_state["geo_spec"] = None
    st.session_state["geo_for"] = None
    st.session_state["eval_verdict"] = None
    st.session_state["student_thought"] = ""

    with st.spinner("🧠 AI 教练正在认真读题..."):
        try:
            st.session_state["ai_result"] = analyze_question(api_key, parts)
        except Exception as e:
            st.error(f"解析失败: {e}")
            st.session_state["ai_result"] = None


# ─── Main ──────────────────────────────────────────────────────────────────
def main():
    for k in ("ai_result", "tts_audio", "hints_given",
              "geo_spec", "geo_for", "question_text", "question_images",
              "eval_verdict", "student_thought"):
        if k not in st.session_state:
            st.session_state[k] = None
    if not isinstance(st.session_state["hints_given"], list):
        st.session_state["hints_given"] = []

    api_key = render_sidebar()

    st.markdown("""
<div class="hero-wrap">
  <div class="hero-icon">🏆</div>
  <h1 class="hero-title">AMC 8 智学助手</h1>
  <p class="hero-sub">AI · 趣味讲题 · 交互几何</p>
  <span class="hero-badge">✨ 让数学思维看得见、摸得着</span>
</div>""", unsafe_allow_html=True)

    # ── Input
    tab_img, tab_txt = st.tabs(["📤 上传图片 / PDF", "✏️ 手动输入题目"])

    with tab_img:
        st.caption("支持 AMC 8 题目截图、扫描件或 PDF（识别前 5 页）")
        uploaded = st.file_uploader("拖拽或点击上传", type=["jpg", "jpeg", "png", "pdf"],
                                    label_visibility="collapsed", key="upl")
        if uploaded:
            content_parts, preview = [], []
            if uploaded.type == "application/pdf":
                with st.spinner("📄 解析 PDF..."):
                    imgs = pdf_to_pil(uploaded.read(), max_pages=5)
                preview = imgs[:3]; content_parts = imgs
                st.info(f"PDF {len(imgs)} 页已加载")
            else:
                img = Image.open(uploaded)
                preview = [img]; content_parts = [img]

            cols = st.columns(min(len(preview), 3))
            for i, im in enumerate(preview[:3]):
                with cols[i]:
                    st.image(im, caption=f"第 {i+1} 页" if len(preview) > 1 else "上传图片",
                             use_container_width=True)

            if not api_key:
                st.warning("⚠️ 请先在左侧输入 Gemini API Key")
            else:
                c1, c2, c3 = st.columns([1, 2, 1])
                with c2:
                    if st.button("🚀 开始智能解题", use_container_width=True, key="go_img"):
                        handle_question(
                            api_key,
                            ["请分析图片中的数学题目，按格式详细解答："] + content_parts,
                            "[图片题目]",
                            image_parts=content_parts,
                        )

    with tab_txt:
        st.caption("直接粘贴或输入题目文字")
        q_text = st.text_area(
            "题目内容",
            placeholder="例：在三角形 ABC 中，AB = AC = 5，BC = 6。求三角形 ABC 的面积。",
            height=180, label_visibility="collapsed", key="qtxt"
        )
        if not api_key:
            st.warning("⚠️ 请先在左侧输入 Gemini API Key")
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
                            q_text,
                        )

    # ── Output: 4 tabs (完整解析 / 提示 / 几何图 / 朗读)
    if st.session_state.get("ai_result"):
        st.divider()
        question_text = st.session_state.get("question_text") or ""
        ready = bool(question_text) or bool(st.session_state.get("question_images"))

        sub_tabs = st.tabs([
            "📖 完整解析",
            "💡 提示模式",
            "📐 交互几何图",
            "🎤 我讲思路",
        ])

        with sub_tabs[0]:
            render_result(st.session_state["ai_result"])

        with sub_tabs[1]:
            if api_key and ready:
                render_hint_mode(api_key, question_text)
            else:
                st.info("先解题，再用提示模式～")

        with sub_tabs[2]:
            if api_key and ready:
                render_geometry_panel(api_key, question_text)
            else:
                st.info("先解题，再看几何图～")

        with sub_tabs[3]:
            if api_key and ready:
                render_dialog_panel(api_key, question_text)
            else:
                st.info("先解题，再来讲思路～")

    st.markdown("""
<div class="footer">
  <p>🏆 AMC 8 智学助手 — MVP · 让每个孩子爱上数学</p>
  <p>Powered by Gemini 2.5 Flash · GeoGebra · Edge-TTS</p>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
