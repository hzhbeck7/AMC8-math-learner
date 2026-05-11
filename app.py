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

import uuid
import quota
from quota import (
    QuotaError, can_call, record_usage, make_user_hash,
    get_user_today, get_global_today, is_circuit_broken,
    QUOTA_PER_USER, COST_LIMIT_USD, SOFT_WARN_RATIO,
)

try:
    from streamlit_cookies_controller import CookieController
    _COOKIES_AVAILABLE = True
except Exception:
    CookieController = None
    _COOKIES_AVAILABLE = False


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

/* Secondary (inactive nav) button */
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.07) !important;
    color: #BCC8E0 !important;
    font-weight: 500 !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    box-shadow: none !important;
}
.stButton > button[kind="secondary"]:hover {
    background: rgba(245,200,66,0.12) !important;
    color: var(--gold) !important;
    border-color: rgba(245,200,66,0.4) !important;
    transform: none !important;
    box-shadow: none !important;
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

/* ── Radio buttons — ensure text is always visible on dark background ── */
[data-testid="stRadio"] label {
    color: var(--text) !important;
    font-family: 'Noto Sans SC', sans-serif !important;
    font-size: .92rem !important;
    padding: .35rem .75rem !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    background: rgba(255,255,255,0.05) !important;
    transition: all .2s !important;
    cursor: pointer !important;
}
[data-testid="stRadio"] label:hover {
    border-color: rgba(245,200,66,0.5) !important;
    background: rgba(245,200,66,0.1) !important;
    color: #FFFFFF !important;
}
[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child,
[data-testid="stRadio"] [aria-checked="true"] ~ div {
    color: var(--gold) !important;
}
/* Selected state */
[data-testid="stRadio"] [data-checked="true"] label,
[data-testid="stRadio"] label:has(input:checked) {
    border-color: var(--gold) !important;
    background: rgba(245,200,66,0.15) !important;
    color: var(--gold) !important;
    font-weight: 600 !important;
}
/* The radio dot itself */
[data-testid="stRadio"] [role="radio"][aria-checked="true"] {
    background-color: var(--gold) !important;
    border-color: var(--gold) !important;
}
/* Text span next to radio dot */
[data-testid="stRadio"] p,
[data-testid="stRadio"] span,
[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p {
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
}

@media (max-width:768px) {
    .sc-md-wrap { padding:1rem 1.1rem; }
    .hero-wrap { padding:1.2rem .5rem .8rem; }
    .sc-deco { display:none; }
}
.footer { text-align:center; padding:2rem 0 1rem; color:#1E2D45; font-size:.72rem; line-height:1.9; }

/* ── Question Bank ── */
.qbank-chapter-btn {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(245,200,66,0.2) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    font-size: .85rem !important;
    text-align: left !important;
    padding: .65rem 1rem !important;
    transition: all .2s !important;
}
.qbank-chapter-btn:hover {
    border-color: var(--gold) !important;
    background: rgba(245,200,66,0.08) !important;
}
.qbank-page-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: all .2s;
    margin-bottom: .75rem;
}
.qbank-page-card:hover {
    border-color: rgba(245,200,66,0.45);
    background: rgba(245,200,66,0.05);
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(245,200,66,0.12);
}
.qbank-page-tag {
    display: inline-block;
    font-size: .72rem;
    padding: .15rem .55rem;
    border-radius: 10px;
    margin: .25rem .2rem 0 0;
    font-weight: 600;
    letter-spacing: .03em;
}
.tag-lecture  { background:rgba(96,165,250,.15);  color:#93C5FD; border:1px solid rgba(96,165,250,.3); }
.tag-example  { background:rgba(74,222,128,.15);  color:#86EFAC; border:1px solid rgba(74,222,128,.3); }
.tag-homework { background:rgba(245,200,66,.15);  color:#FDE68A; border:1px solid rgba(245,200,66,.3); }

/* ── Quota bar ── */
.quota-bar {
    display: flex; align-items: center; gap: 1rem;
    background: rgba(34,211,238,0.08);
    border: 1px solid rgba(34,211,238,0.3);
    border-radius: 12px;
    padding: .65rem 1.1rem;
    margin: .6rem 0 1.2rem;
    font-size: .85rem;
    color: #BFF;
}
.quota-bar.using-own {
    background: rgba(74,222,128,0.08);
    border-color: rgba(74,222,128,0.3);
    color: #BBF7D0;
}
.quota-bar.warning {
    background: rgba(245,158,11,0.1);
    border-color: rgba(245,158,11,0.4);
    color: #FCD34D;
}
.quota-bar.exhausted {
    background: rgba(239,68,68,0.1);
    border-color: rgba(239,68,68,0.4);
    color: #FCA5A5;
}
.quota-pct {
    font-weight: 700;
    font-size: 1rem;
    color: #F5C842;
}
.quota-progress {
    flex: 1;
    height: 6px;
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    overflow: hidden;
}
.quota-progress > div {
    height: 100%;
    background: linear-gradient(90deg, #22D3EE, #60A5FA);
    transition: width .3s;
}
.quota-bar.warning  .quota-progress > div { background: linear-gradient(90deg,#F59E0B,#FBBF24); }
.quota-bar.exhausted .quota-progress > div { background: linear-gradient(90deg,#EF4444,#F87171); }

/* ── Admin panel ── */
.admin-stat {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(245,200,66,0.2);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.admin-stat-num {
    font-family: 'ZCOOL XiaoWei', serif;
    font-size: 1.7rem;
    color: #F5C842;
    margin: 0; line-height: 1;
}
.admin-stat-lbl {
    color: #8899BB;
    font-size: .75rem;
    margin: .35rem 0 0;
}
.breaker-badge-on {
    display: inline-block;
    padding: .3rem .8rem;
    background: rgba(239,68,68,.2);
    border: 1px solid rgba(239,68,68,.5);
    color: #FCA5A5;
    border-radius: 16px;
    font-size: .8rem;
    font-weight: 700;
}
.breaker-badge-off {
    display: inline-block;
    padding: .3rem .8rem;
    background: rgba(34,197,94,.15);
    border: 1px solid rgba(34,197,94,.4);
    color: #86EFAC;
    border-radius: 16px;
    font-size: .8rem;
}

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


def _get_platform_key() -> str | None:
    """Read the platform-provided API key from Streamlit Secrets."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY")


def _resolve_api_key(user_key: str | None) -> tuple[str | None, bool]:
    """Decide which key to use.
    Returns (api_key, using_platform_key)."""
    if user_key and user_key.strip():
        return user_key.strip(), False
    pk = _get_platform_key()
    if pk:
        return pk, True
    return None, False


def _safe_generate(parts: list, action: str, user_key: str | None,
                   user_hash: str, est_in: int = 2000, est_out: int = 1000):
    """Wrapper around generate_content with quota enforcement.

    - If user_key is provided: use it directly, bypass all quotas.
    - Else: use platform key, but check & record quota.
    Returns the raw Gemini response object.
    Raises QuotaError on quota / breaker / no-key conditions.
    """
    api_key, using_platform = _resolve_api_key(user_key)

    if api_key is None:
        raise QuotaError(
            "尚未配置任何 Gemini API Key。请在左侧边栏填入您的 Key。",
            kind="generic",
        )

    if using_platform:
        ok, reason = can_call(user_hash, est_input_tokens=est_in,
                              est_output_tokens=est_out)
        if not ok:
            raise QuotaError(reason, kind="user")

    response = _model(api_key).generate_content(parts)

    if using_platform:
        try:
            meta = getattr(response, "usage_metadata", None)
            in_tokens = getattr(meta, "prompt_token_count", 0) or 0
            out_tokens = getattr(meta, "candidates_token_count", 0) or 0
            record_usage(user_hash, action, in_tokens, out_tokens)
        except Exception as e:
            print(f"[quota] record failed: {e}")

    return response


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

【⚠️ 最重要的硬性规则 — 违反会导致渲染失败】
1. **任何 primitive 中提到的点名（from, to, at, vertex, a, c, from_a, from_c,
   center, through, vertices, to_side），必须先在 points 数组中定义**
2. 如果题目涉及"两线相交产生的交点"（如五角星里 5 条线的交点），你必须：
   - 自己估算这些交点的坐标，加入 points
   - 或者用 midpoint primitive 创建（带 name 字段）
   - **绝对不能直接引用一个未定义的点名**
3. 点名只能用单个大写字母 A-Z（如 A, B, C, P, Q, R）
4. primitive 的 id 用小写字母/下划线（如 tri, seg_ab, alt_a），不能和点名冲突
5. 如果不确定某个角度怎么用 angle_arc 标，宁可省略，也不要写错引用

【点的坐标规则】
- 用合理的整数或简单小数构造一个能凸显题意的图
- 范围一般在 -10 到 10 之间
- 例：等边三角形可用 A(0,0)、B(4,0)、C(2,3.46)
- **复杂图形（如五角星）建议只画核心轮廓 + 标注题目给出的角度数值，
  不必精确还原所有交点。简洁的示意图比精确但出错更有价值。**

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
                              user_hash: str, image_parts: list = None) -> dict:
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
    response = _safe_generate(parts, "evaluate_thinking", api_key, user_hash,
                              est_in=1500, est_out=600)
    raw = response.text.strip()
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


def analyze_question(api_key: str, parts: list, user_hash: str) -> str:
    response = _safe_generate([TUTOR_PROMPT] + parts, "analyze_question",
                              api_key, user_hash, est_in=2500, est_out=1500)
    return response.text


def get_next_hint(api_key: str, question_text: str, hints_given: list,
                  user_hash: str, image_parts: list = None) -> str:
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
    response = _safe_generate(parts, "get_next_hint", api_key, user_hash,
                              est_in=600, est_out=200)
    return response.text.strip()


def get_geometry_spec(api_key: str, question_text: str, user_hash: str,
                      image_parts: list = None) -> dict | None:
    """Ask AI to return geometry JSON. Returns None if not a geometry question."""
    parts = [GEO_SPEC_PROMPT, f"题目：\n{question_text or '(见图片)'}"]
    if image_parts:
        parts.extend(image_parts)
    response = _safe_generate(parts, "geometry_spec", api_key, user_hash,
                              est_in=1500, est_out=600)
    raw = response.text.strip()
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


def render_hint_mode(api_key: str, question_text: str, user_hash: str):
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
                        nh = get_next_hint(api_key, question_text, hints,
                                           user_hash, image_parts=img_parts)
                        hints.append(nh)
                        st.session_state["hints_given"] = hints
                        st.rerun()
                    except QuotaError as qe:
                        st.warning(f"⏸️ {qe}")
                    except Exception as e:
                        st.error(f"提示生成失败: {e}")
        else:
            st.info("✨ 已给完所有提示，下面看完整解析吧！")

    if hints and st.button("🗑️ 重置提示", key="hint_reset"):
        st.session_state["hints_given"] = []
        st.rerun()


def render_geometry_panel(api_key: str, question_text: str, user_hash: str):
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
                spec = get_geometry_spec(api_key, question_text, user_hash,
                                         image_parts=img_parts)
                st.session_state["geo_spec"] = spec
                st.session_state["geo_for"] = question_text
            except QuotaError as qe:
                st.warning(f"⏸️ {qe}")
                st.session_state["geo_spec"] = None
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


def render_dialog_panel(api_key: str, question_text: str, user_hash: str):
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
                            api_key, question_text, student_text,
                            user_hash, image_parts=img_parts,
                        )
                        st.session_state["eval_verdict"] = verdict
                    except QuotaError as qe:
                        st.warning(f"⏸️ {qe}")
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


# ─── Question Bank loader ────────────────────────────────────────────────────
QBANK_BASE_URL = "https://raw.githubusercontent.com/{owner}/{repo}/main/qbank"
# Fallback to local path when running locally
QBANK_LOCAL    = "qbank"


def _qbank_url_base() -> str:
    """Detect whether we're on Streamlit Cloud and return the appropriate base."""
    # When deployed on Streamlit Cloud, load from GitHub raw URLs.
    # Locally, load from the qbank/ directory.
    try:
        owner = st.secrets.get("GITHUB_OWNER", "")
        repo  = st.secrets.get("GITHUB_REPO", "")
        if owner and repo:
            return QBANK_BASE_URL.format(owner=owner, repo=repo)
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_qbank_index() -> dict | None:
    """Load qbank_index.json — cached for 1 hour."""
    base = _qbank_url_base()
    try:
        if base:
            import urllib.request
            url = f"{base}/qbank_index.json"
            with urllib.request.urlopen(url, timeout=10) as r:
                return json.loads(r.read().decode())
        else:
            local = os.path.join(QBANK_LOCAL, "qbank_index.json")
            if os.path.exists(local):
                with open(local, encoding="utf-8") as f:
                    return json.load(f)
    except Exception as e:
        st.warning(f"题库索引加载失败: {e}")
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_qbank_chapter(filename: str) -> dict | None:
    """Load a single chapter JSON — cached for 1 hour."""
    base = _qbank_url_base()
    try:
        if base:
            import urllib.request
            url = f"{base}/{filename}"
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode())
        else:
            local = os.path.join(QBANK_LOCAL, filename)
            if os.path.exists(local):
                with open(local, encoding="utf-8") as f:
                    return json.load(f)
    except Exception as e:
        st.warning(f"章节数据加载失败 ({filename}): {e}")
    return None


def b64_to_pil(b64_str: str) -> Image.Image:
    """Decode a base64 JPEG string to a PIL Image."""
    import base64
    data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(data))


# ─── Question Bank UI ─────────────────────────────────────────────────────────
def render_qbank(api_key: str, user_hash: str, can_use_ai: bool):
    """Full question bank browser and launch interface."""

    # ── State ──
    if "qb_chapter" not in st.session_state:
        st.session_state["qb_chapter"] = None   # selected chapter filename
    if "qb_page_idx" not in st.session_state:
        st.session_state["qb_page_idx"] = None  # selected page index within chapter

    index = load_qbank_index()
    if not index:
        st.info("📚 题库暂未配置。请在 Streamlit Secrets 中添加 GITHUB_OWNER 和 GITHUB_REPO，或在本地 qbank/ 目录放置题库文件。")
        return

    chapters = index.get("chapters", [])

    # ── Chapter picker (shown when no chapter selected) ──
    if not st.session_state["qb_chapter"]:
        st.markdown(
            '<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;'
            'font-size:1.25rem;margin:.5rem 0 1rem;">📚 选择章节</p>',
            unsafe_allow_html=True,
        )
        st.caption(f"共 {len(chapters)} 章 · {index.get('total_pages', '?')} 页题目与讲解")

        # Responsive grid: 2 columns
        rows = [chapters[i:i+2] for i in range(0, len(chapters), 2)]
        for row in rows:
            cols = st.columns(len(row))
            for col, ch in zip(cols, row):
                with col:
                    label = (
                        f"**{ch['cn_name']}**  \n\n"
                        f"{ch['en_name']}  ·  {ch['page_count']} 页"
                    )
                    if st.button(label, key=f"qb_ch_{ch['id']}", use_container_width=True):
                        st.session_state["qb_chapter"] = ch["file"]
                        st.session_state["qb_page_idx"] = None
                        st.rerun()
        return

    # ── Page browser (chapter selected, no page selected) ──
    ch_file = st.session_state["qb_chapter"]
    ch_meta = next((c for c in chapters if c["file"] == ch_file), None)

    # Back button
    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← 返回", key="qb_back_ch"):
            st.session_state["qb_chapter"] = None
            st.session_state["qb_page_idx"] = None
            st.rerun()
    with col_title:
        if ch_meta:
            st.markdown(
                f'<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;'
                f'font-size:1.2rem;margin:.4rem 0;">'
                f'📖 {ch_meta["cn_name"]}</p>',
                unsafe_allow_html=True,
            )

    if st.session_state["qb_page_idx"] is not None:
        # ── Single page view ──────────────────────────────────────────────
        with st.spinner("📄 加载页面..."):
            chapter_data = load_qbank_chapter(ch_file)

        if not chapter_data:
            st.error("加载失败，请重试")
            st.session_state["qb_page_idx"] = None
            return

        pages = chapter_data.get("pages", [])
        idx = st.session_state["qb_page_idx"]
        page = pages[idx]

        # Navigation row
        nav1, nav2, nav3, nav_info = st.columns([1, 1, 1, 4])
        with nav1:
            if st.button("← 上页", key="qb_prev", disabled=(idx == 0)):
                st.session_state["qb_page_idx"] = idx - 1
                st.rerun()
        with nav2:
            if st.button("下页 →", key="qb_next", disabled=(idx >= len(pages) - 1)):
                st.session_state["qb_page_idx"] = idx + 1
                st.rerun()
        with nav3:
            if st.button("📋 列表", key="qb_list"):
                st.session_state["qb_page_idx"] = None
                st.rerun()
        with nav_info:
            ptype_label = {"lecture": "知识讲解", "example": "例题", "homework": "作业练习"}.get(
                page.get("page_type", ""), "")
            st.markdown(
                f'<p style="color:#8899BB;font-size:.82rem;margin:.5rem 0;">'
                f'第 {idx+1} / {len(pages)} 页 · 书页 {page.get("book_page","?")} · {ptype_label}</p>',
                unsafe_allow_html=True,
            )

        # Show page image
        img = b64_to_pil(page["img_b64"])
        st.image(img, use_container_width=True)

        # Solve button
        if not can_use_ai:
            st.warning("⚠️ 请先在左侧输入 Gemini API Key 或等待免费额度恢复。")
        else:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                if st.button("🚀 AI 教练讲解这道题", use_container_width=True, key="qb_solve"):
                    handle_question(
                        api_key,
                        ["请分析图片中的AMC 8题目，按格式详细解答：", img],
                        f"题库：{ch_meta['cn_name'] if ch_meta else ''} 第{page.get('book_page','?')}页",
                        user_hash,
                        image_parts=[img],
                    )
                    # Scroll user to result — st.rerun not needed, handle_question sets session state
    else:
        # ── Page thumbnail grid ──────────────────────────────────────────
        with st.spinner("📚 加载章节..."):
            chapter_data = load_qbank_chapter(ch_file)

        if not chapter_data:
            st.error("加载失败，请重试")
            return

        pages = chapter_data.get("pages", [])
        st.caption(f"共 {len(pages)} 页 · 点击任意页面预览并解题")

        # Filter bar
        filter_col1, filter_col2 = st.columns([2, 1])
        with filter_col1:
            type_filter = st.radio(
                "筛选",
                ["全部", "知识讲解", "例题", "作业练习"],
                horizontal=True,
                key="qb_type_filter",
                label_visibility="collapsed",
            )
        type_map = {"全部": None, "知识讲解": "lecture", "例题": "example", "作业练习": "homework"}
        selected_type = type_map[type_filter]
        filtered = [p for p in pages if selected_type is None or p.get("page_type") == selected_type]

        st.caption(f"筛选结果：{len(filtered)} 页")

        # Thumbnail grid: 3 per row
        for row_start in range(0, len(filtered), 3):
            row_pages = filtered[row_start:row_start + 3]
            cols = st.columns(3)
            for col, page in zip(cols, row_pages):
                with col:
                    # Decode thumbnail image
                    img = b64_to_pil(page["img_b64"])
                    # Show small thumbnail
                    st.image(img, use_container_width=True)
                    # Tag + button row
                    ptype = page.get("page_type", "")
                    tag_class = {"lecture": "tag-lecture", "example": "tag-example", "homework": "tag-homework"}.get(ptype, "tag-lecture")
                    tag_label = {"lecture": "讲解", "example": "例题", "homework": "作业"}.get(ptype, "")
                    st.markdown(
                        f'<span class="qbank-page-tag {tag_class}">{tag_label}</span>'
                        f'<span style="color:#8899BB;font-size:.72rem;">书页 {page.get("book_page","?")}</span>',
                        unsafe_allow_html=True,
                    )
                    real_idx = pages.index(page)
                    if st.button("📖 选这页", key=f"qb_p_{page['id']}", use_container_width=True):
                        st.session_state["qb_page_idx"] = real_idx
                        st.rerun()


# ─── User identity & cookies ────────────────────────────────────────────────
def _get_or_set_cookie_uuid(controller) -> str | None:
    """Get a stable per-browser UUID; create one if missing.
    Returns None on the very first render before cookies have loaded."""
    if controller is None:
        return None
    try:
        existing = controller.get("amc8_uid")
    except Exception:
        return None
    if existing:
        return existing
    new_uid = uuid.uuid4().hex[:20]
    try:
        controller.set("amc8_uid", new_uid, max_age=60 * 60 * 24 * 30)  # 30 days
    except Exception:
        pass
    return new_uid


def _bootstrap_user_identity() -> tuple[str, bool]:
    """Resolve the current user's identity hash.
    Returns (user_hash, cookies_ready).
    cookies_ready=False on the first render — caller may show a brief loader."""
    if not _COOKIES_AVAILABLE:
        # Fallback: per-session uuid from session_state
        if "fallback_uid" not in st.session_state:
            st.session_state["fallback_uid"] = uuid.uuid4().hex[:20]
        cookie_uid = st.session_state["fallback_uid"]
        cookies_ready = True
    else:
        if "_cookie_ctrl" not in st.session_state:
            try:
                st.session_state["_cookie_ctrl"] = CookieController()
            except Exception:
                st.session_state["_cookie_ctrl"] = None
        ctrl = st.session_state.get("_cookie_ctrl")
        cookie_uid = _get_or_set_cookie_uuid(ctrl)
        cookies_ready = cookie_uid is not None
        if not cookies_ready:
            # Cookie not yet loaded — use temporary session id this render
            cookie_uid = st.session_state.setdefault("temp_uid", uuid.uuid4().hex[:20])

    # IP and User-Agent (best effort; Streamlit doesn't expose these directly)
    headers = {}
    try:
        headers = st.context.headers if hasattr(st, "context") else {}
    except Exception:
        headers = {}
    ip = headers.get("X-Forwarded-For", "").split(",")[0].strip() or headers.get("X-Real-Ip", "")
    ua = headers.get("User-Agent", "")

    return make_user_hash(cookie_uid, ip, ua), cookies_ready


# ─── Quota bar ──────────────────────────────────────────────────────────────
def render_quota_bar(user_hash: str, user_provided_key: bool):
    """Top-of-page quota status. Hidden when user provides own key."""
    if user_provided_key:
        st.markdown(
            '<div class="quota-bar using-own">'
            '<span style="font-size:1.1rem;">💎</span>'
            '<span><b>使用您自己的 API Key</b> · 不限次数</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Platform key path: show quota status
    if not _get_platform_key():
        st.markdown(
            '<div class="quota-bar exhausted">'
            '<span style="font-size:1.1rem;">⚠️</span>'
            '<span>系统未配置免费试用 Key。请在左侧填入您自己的 Gemini API Key 继续。</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    if is_circuit_broken():
        st.markdown(
            '<div class="quota-bar exhausted">'
            '<span style="font-size:1.1rem;">🌙</span>'
            '<span><b>今日免费层已暂停</b>（成本上限触发）。'
            '可填入您自己的 Gemini API Key 继续，或明天 0:00 (UTC) 自动恢复。</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    u = get_user_today(user_hash)
    pct = u["pct_used"]

    if pct >= 100:
        css = "exhausted"
        msg = (
            '🌙 <b>今日免费试用用完啦</b>。教练今天陪你聊了不少题，挺累的～ '
            '明天 0:00 (UTC) 自动重置。'
            '<br><span style="opacity:.7;font-size:.78rem;">想现在继续？'
            '可填入您自己的 Gemini API Key（免费、3 分钟搞定）。</span>'
        )
    elif pct >= int(SOFT_WARN_RATIO * 100):
        css = "warning"
        msg = (
            f'⏳ 今日免费额度已用 <span class="quota-pct">{pct}%</span>。'
            f'剩下不多，建议留给关键题目使用。'
            '<br><span style="opacity:.7;font-size:.78rem;">'
            '想敞开练？填入您自己的 Gemini API Key，无任何限制。</span>'
        )
    else:
        css = ""
        msg = (
            f'✨ <b>免费试用中</b> · 今日已用 <span class="quota-pct">{pct}%</span>'
        )

    st.markdown(
        f'<div class="quota-bar {css}">'
        f'<span style="font-size:1.1rem;">🎯</span>'
        f'<span style="flex:1;">{msg}</span>'
        f'<div class="quota-progress" title="{u["tokens_used"]} / {QUOTA_PER_USER} tokens">'
        f'<div style="width:{min(100,pct)}%"></div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── Admin panel ────────────────────────────────────────────────────────────
def _get_admin_password() -> str:
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return os.environ.get("ADMIN_PASSWORD", "amc8admin2025")


def render_admin_panel():
    st.markdown("""
<div style="text-align:center;padding:1rem 0 .5rem;">
  <p style="color:#F5C842;font-family:'ZCOOL XiaoWei',serif;
            font-size:1.5rem;margin:.3rem 0;">⚙️ 管理后台</p>
  <p style="color:#4A5F80;font-size:.8rem;margin:0;">配额监控 · 成本追踪 · 熔断控制</p>
</div>""", unsafe_allow_html=True)

    g = get_global_today()

    # ─ Today summary
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, f"{g['calls']}", "今日调用"),
        (c2, f"{g['tokens_used']/1000:.1f}K", f"Tokens / 4M ({100*g['tokens_used']//quota.QUOTA_GLOBAL}%)"),
        (c3, f"${g['cost_usd']:.4f}", f"成本 / $1.00 ({g['pct_cost']}%)"),
        (c4, "🔴 已熔断" if g["circuit_broken"] else "🟢 正常",
            "熔断状态"),
    ]
    for col, num, lbl in cards:
        with col:
            st.markdown(
                f'<div class="admin-stat">'
                f'<p class="admin-stat-num">{num}</p>'
                f'<p class="admin-stat-lbl">{lbl}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ─ Circuit breaker controls
    st.markdown("<br>", unsafe_allow_html=True)
    bcol1, bcol2, _ = st.columns([1, 1, 2])
    with bcol1:
        if not g["circuit_broken"]:
            if st.button("🔥 手动触发熔断", key="trip_breaker"):
                quota.admin_set_breaker(True)
                st.success("已熔断")
                st.rerun()
    with bcol2:
        if g["circuit_broken"]:
            if st.button("✅ 解除熔断", key="reset_breaker"):
                quota.admin_set_breaker(False)
                st.success("已解除")
                st.rerun()

    st.divider()

    # ─ Top users today
    st.markdown(
        '<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;'
        'font-size:1.1rem;margin:.5rem 0;">👥 今日 Top 用户</p>',
        unsafe_allow_html=True,
    )
    tops = quota.get_top_users_today(10)
    if tops:
        rows = [{
            "用户": r["user"],
            "Tokens": f"{r['tokens']/1000:.1f}K",
            "调用": r["calls"],
            "成本": f"${r['cost']:.4f}",
        } for r in tops]
        st.table(rows)
        # Reset action
        with st.expander("🔧 重置某用户额度"):
            uid = st.selectbox("选择用户", [r["user"] for r in tops], key="reset_uid_pick")
            if st.button("重置该用户今日额度", key="reset_uid_btn"):
                if quota.admin_reset_user(uid):
                    st.success(f"已重置 {uid}")
                    st.rerun()
    else:
        st.caption("暂无用户记录")

    st.divider()

    # ─ 7-day trend
    st.markdown(
        '<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;'
        'font-size:1.1rem;margin:.5rem 0;">📈 最近 7 天</p>',
        unsafe_allow_html=True,
    )
    days = quota.get_recent_days(7)
    if days:
        chart_rows = [{
            "日期": d["date"],
            "调用": d["calls"],
            "Tokens(K)": round(d["tokens"] / 1000, 1),
            "成本($)": round(d["cost"], 4),
        } for d in days]
        st.table(chart_rows)
        # Simple bar chart of cost
        import pandas as pd  # streamlit pulls it in
        df = pd.DataFrame({"日期": [d["date"] for d in days],
                           "成本($)": [d["cost"] for d in days]})
        st.bar_chart(df.set_index("日期"))
    else:
        st.caption("暂无历史数据")

    st.divider()

    # ─ Recent events
    st.markdown(
        '<p style="color:#F5C842;font-family:\'ZCOOL XiaoWei\',serif;'
        'font-size:1.1rem;margin:.5rem 0;">📋 最近调用记录</p>',
        unsafe_allow_html=True,
    )
    evs = quota.get_recent_events(20)
    if evs:
        ev_rows = [{
            "时间": e["ts"][11:19],
            "用户": e["user"][:10],
            "操作": e["action"],
            "Tokens": e["total_tokens"],
            "成本($)": f"${e['cost_usd']:.5f}",
        } for e in evs]
        st.table(ev_rows)
    else:
        st.caption("暂无调用记录")

    st.divider()

    # ─ Danger zone
    with st.expander("☢️ 危险操作", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ 清空今日记录", key="clr_today"):
                if st.session_state.get("_confirm_clr_today"):
                    quota.admin_clear_today()
                    st.session_state["_confirm_clr_today"] = False
                    st.success("已清空今日")
                    st.rerun()
                else:
                    st.session_state["_confirm_clr_today"] = True
                    st.warning("再点一次确认")
        with c2:
            if st.button("💣 清空全部记录", key="clr_all"):
                if st.session_state.get("_confirm_clr_all"):
                    quota.admin_clear_all()
                    st.session_state["_confirm_clr_all"] = False
                    st.success("已清空全部")
                    st.rerun()
                else:
                    st.session_state["_confirm_clr_all"] = True
                    st.warning("再点一次确认")


# ─── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar() -> tuple[str, bool]:
    """Returns (api_key, admin_mode)."""
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

        # API Key
        api_key = st.text_input(
            "🔑 Gemini API Key（可选）",
            type="password",
            placeholder="AIzaSy... · 留空使用免费试用额度",
            help="填入后将使用您自己的 Key，无任何限制。前往 https://aistudio.google.com 获取。"
        )

        if api_key:
            st.markdown(
                '<p style="color:#86EFAC;font-size:.78rem;margin:.3rem 0;">'
                '💎 已使用您自己的 Key · 无配额限制</p>',
                unsafe_allow_html=True,
            )
        elif _get_platform_key():
            st.markdown(
                '<p style="color:#22D3EE;font-size:.78rem;margin:.3rem 0;">'
                '✨ 当前使用免费试用额度</p>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown("""
<div style="color:#94A3B8;font-size:.85rem;line-height:2;">
<p style="color:#F5C842;font-family:'ZCOOL XiaoWei',serif;font-size:1rem;margin:.3rem 0;">📚 使用流程</p>
<p>① 选「自由解题」上传 / 粘贴</p>
<p>&nbsp;&nbsp;&nbsp;或选「内置题库」按章节练习</p>
<p>② AI 三段式讲解</p>
<p>③ 不会用「提示模式」</p>
<p>④ 几何题看「交互式图」</p>
<p>⑤ 听完试试「我讲思路」</p>
</div>
""", unsafe_allow_html=True)

        st.divider()

        # Admin login (collapsed by default)
        admin_mode = False
        with st.expander("🔐 管理员", expanded=False):
            admin_pwd = st.text_input("管理员密码", type="password", key="admin_pwd")
            if admin_pwd:
                if admin_pwd == _get_admin_password():
                    admin_mode = True
                    st.success("✓ 已登录")
                else:
                    st.error("密码错误")

        st.markdown("""
<div style="text-align:center;padding:1rem 0 0;color:#1E2D45;font-size:.7rem;line-height:2;">
  <p>🤖 Gemini 2.5 Flash</p>
  <p>📐 GeoGebra 几何引擎</p>
  <p>🎙️ Edge-TTS 云希</p>
</div>
""", unsafe_allow_html=True)

    return api_key, admin_mode


# ─── Question handler ──────────────────────────────────────────────────────
def handle_question(api_key: str, parts: list, question_text: str,
                    user_hash: str, image_parts: list = None):
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
            st.session_state["ai_result"] = analyze_question(api_key, parts, user_hash)
        except QuotaError as qe:
            st.warning(f"⏸️ {qe}")
            st.session_state["ai_result"] = None
        except Exception as e:
            st.error(f"解析失败: {e}")
            st.session_state["ai_result"] = None


# ─── Main ──────────────────────────────────────────────────────────────────
def main():
    for k in ("ai_result", "tts_audio", "hints_given",
              "geo_spec", "geo_for", "question_text", "question_images",
              "eval_verdict", "student_thought",
              "qb_chapter", "qb_page_idx"):
        if k not in st.session_state:
            st.session_state[k] = None
    if not isinstance(st.session_state["hints_given"], list):
        st.session_state["hints_given"] = []

    # ── Sidebar (returns api_key + admin_mode flag)
    api_key, admin_mode = render_sidebar()

    # ── Identity bootstrap (cookie + IP + UA hash)
    user_hash, _cookies_ready = _bootstrap_user_identity()

    # ── If admin mode, take over the page entirely
    if admin_mode:
        render_admin_panel()
        st.markdown("""
<div class="footer">
  <p>🏆 AMC 8 智学助手 — 管理后台</p>
</div>""", unsafe_allow_html=True)
        return

    # ── Hero
    st.markdown("""
<div class="hero-wrap">
  <div class="hero-icon">🏆</div>
  <h1 class="hero-title">AMC 8 智学助手</h1>
  <p class="hero-sub">AI · 趣味讲题 · 交互几何</p>
  <span class="hero-badge">✨ 让数学思维看得见、摸得着</span>
</div>""", unsafe_allow_html=True)

    # ── Quota status bar
    user_provided_key = bool(api_key and api_key.strip())
    render_quota_bar(user_hash, user_provided_key)
    can_use_ai = user_provided_key or bool(_get_platform_key())

    # ── Top-level navigation: 解题 / 题库
    # Use session_state to track mode (button-based, fully stylable)
    if "main_nav" not in st.session_state:
        st.session_state["main_nav"] = "free"

    nav_c1, nav_c2, nav_c3 = st.columns([2, 2, 6])
    with nav_c1:
        free_active = st.session_state["main_nav"] == "free"
        if st.button(
            "✏️ 自由解题",
            key="nav_free",
            use_container_width=True,
            type="primary" if free_active else "secondary",
        ):
            st.session_state["main_nav"] = "free"
            st.rerun()
    with nav_c2:
        qb_active = st.session_state["main_nav"] == "qbank"
        if st.button(
            "📚 内置题库",
            key="nav_qbank",
            use_container_width=True,
            type="primary" if qb_active else "secondary",
        ):
            st.session_state["main_nav"] = "qbank"
            st.rerun()

    st.markdown('<hr style="margin:.6rem 0 1.2rem;">', unsafe_allow_html=True)
    mode = st.session_state["main_nav"]

    # ════════════════════════════════════════════
    # 模式 1：自由解题（上传 / 手动输入）
    # ════════════════════════════════════════════
    if mode == "free":
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

                if not can_use_ai:
                    st.warning("⚠️ 当前没有可用的 API Key。请在左侧填入您自己的 Gemini API Key。")
                else:
                    c1, c2, c3 = st.columns([1, 2, 1])
                    with c2:
                        if st.button("🚀 开始智能解题", use_container_width=True, key="go_img"):
                            handle_question(
                                api_key,
                                ["请分析图片中的数学题目，按格式详细解答："] + content_parts,
                                "[图片题目]",
                                user_hash,
                                image_parts=content_parts,
                            )

        with tab_txt:
            st.caption("直接粘贴或输入题目文字")
            q_text = st.text_area(
                "题目内容",
                placeholder="例：在三角形 ABC 中，AB = AC = 5，BC = 6。求三角形 ABC 的面积。",
                height=180, label_visibility="collapsed", key="qtxt"
            )
            if not can_use_ai:
                st.warning("⚠️ 当前没有可用的 API Key。请在左侧填入您自己的 Gemini API Key。")
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
                                user_hash,
                            )

    # ════════════════════════════════════════════
    # 模式 2：内置题库
    # ════════════════════════════════════════════
    elif mode == "qbank":
        render_qbank(api_key, user_hash, can_use_ai)

    # ── Output panel (appears in both modes after solve) ──
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
            if can_use_ai and ready:
                render_hint_mode(api_key, question_text, user_hash)
            else:
                st.info("先解题，再用提示模式～")

        with sub_tabs[2]:
            if can_use_ai and ready:
                render_geometry_panel(api_key, question_text, user_hash)
            else:
                st.info("先解题，再看几何图～")

        with sub_tabs[3]:
            if can_use_ai and ready:
                render_dialog_panel(api_key, question_text, user_hash)
            else:
                st.info("先解题，再来讲思路～")

    st.markdown("""
<div class="footer">
  <p>🏆 AMC 8 智学助手 — MVP · 让每个孩子爱上数学</p>
  <p>Powered by Gemini 2.5 Flash · GeoGebra · Edge-TTS</p>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
