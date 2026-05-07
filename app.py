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
.lbl-t { color:#F5C842; }
.lbl-c { color:#60A5FA; }
.lbl-g { color:#4ADE80; }

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
    background:rgba(255,255,255,.055) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important; color:var(--text) !important;
    font-family:'Noto Sans SC',sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
    border-color:var(--gold) !important;
    box-shadow:0 0 0 2px rgba(245,200,66,.2) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background:rgba(245,200,66,.025) !important;
    border:2px dashed rgba(245,200,66,.3) !important;
    border-radius:14px !important;
}

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

@media (max-width:768px) {
    .sc { padding:1rem 1.1rem; }
    .hero-wrap { padding:1.2rem .5rem .8rem; }
    .sc-deco { display:none; }
}

.footer { text-align:center; padding:2rem 0 1rem; color:#1E2D45; font-size:.72rem; line-height:1.9; }
</style>
""", unsafe_allow_html=True)


# ─── Constants ────────────────────────────────────────────────────────────────────
ADMIN_PASSWORD = "amc8admin2025"
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
TUTOR_PROMPT = """你是一位风趣幽默、充满激情的奥数教练，专门辅导AMC 8竞赛。
风格：说话接地气、爱用比喻和段子、善于鼓励孩子、把复杂数学变得有趣好玩。

请分析题目，严格按以下Markdown格式输出：

## 🎭 【数学小剧场】
讲一个与本题知识点相关的数学家故事或趣味历史（150字左右，生动有趣）。

## 🔍 【教练透视眼】
简洁总结本题核心知识点和考点（要点列表）。

## 🧩 【逻辑拆解步】
分步骤、引导式讲解解题逻辑。要求：
- 语言幽默接地气，像朋友聊天
- 用生动比喻（如把勾股定理比作三角形的"铁三角"关系）
- 必须包含1-2个冷笑话或鼓励语（如"这题你要是做对了，我看你离数学家高斯也就差两斤头发的距离了"）
- 引导思维过程，不只给答案
- 最后给出正确答案"""


def analyze_question(api_key: str, parts: list) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
    response = model.generate_content([TUTOR_PROMPT] + parts)
    return response.text


def extract_questions_from_pdf(api_key: str, images: list) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
    prompt = (
        "请从这些PDF页面中提取所有数学题目，以纯JSON格式返回（不要加```代码块标记）。\n"
        '格式：{"questions":[{"id":1,"title":"编号或标题","content":"完整题目含选项",'
        '"topic":"几何/代数/数论/组合/概率","difficulty":"简单/中等/困难"}]}\n'
        "只返回JSON，不要其他内容。"
    )
    response = model.generate_content([prompt] + images[:8])
    text = response.text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


# ─── TTS ─────────────────────────────────────────────────────────────────────────
def _clean_tts(text: str) -> str:
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"[🎭🔍🧩【】]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:3500]


async def _tts_async(text: str, path: str) -> bool:
    try:
        import edge_tts
        comm = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
        await comm.save(path)
        return True
    except Exception:
        return False


def generate_audio(text: str):
    clean = _clean_tts(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        path = tmp.name
    ok = asyncio.run(_tts_async(clean, path))
    if ok and os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data
    return None


# ─── Parse AI response ────────────────────────────────────────────────────────────
def parse_sections(text: str) -> dict:
    markers = {"theater": "数学小剧场", "coach": "教练透视眼", "logic": "逻辑拆解步"}
    positions = {}
    for key, kw in markers.items():
        idx = text.find(kw)
        if idx != -1:
            positions[key] = idx

    if not positions:
        return {"theater": "", "coach": "", "logic": "", "raw": text}

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

    for k in ("theater", "coach", "logic"):
        sections.setdefault(k, "")
    sections["raw"] = text
    return sections


# ─── Render result ────────────────────────────────────────────────────────────────
def render_result(result_text: str):
    sec = parse_sections(result_text)

    if sec.get("theater"):
        st.markdown(f"""
<div class="sc sc-t">
  <div class="sc-deco">🎭</div>
  <p class="sc-label lbl-t">🎭 数学小剧场</p>
  <div class="sc-body">{sec['theater'].replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)

    # Voice button
    tts_src = (sec.get("theater", "") + "\n\n" + sec.get("logic", "")).strip()
    if tts_src:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("🔊 听听教练怎么说", key="voice_play", use_container_width=True):
                with st.spinner("🎙️ 云希老师正在录音，稍等..."):
                    audio = generate_audio(tts_src)
                if audio:
                    st.audio(audio, format="audio/mp3")
                else:
                    st.error("语音生成失败，请确保已安装 edge-tts（pip install edge-tts）")

    if sec.get("coach"):
        st.markdown(f"""
<div class="sc sc-c">
  <div class="sc-deco">🔍</div>
  <p class="sc-label lbl-c">🔍 教练透视眼</p>
  <div class="sc-body">{sec['coach'].replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)

    if sec.get("logic"):
        st.markdown(f"""
<div class="sc sc-l">
  <div class="sc-deco">🧩</div>
  <p class="sc-label lbl-g">🧩 逻辑拆解步</p>
  <div class="sc-body">{sec['logic'].replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)

    if not any(sec.get(k) for k in ("theater", "coach", "logic")):
        st.markdown(f"""
<div class="sc" style="border-color:rgba(245,200,66,.35);">
  <div class="sc-body">{result_text.replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)


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

        # API Key
        st.markdown('<p class="sb-label">🔑 API 设置</p>', unsafe_allow_html=True)
        api_key = st.text_input(
            "请输入您的 Gemini API Key",
            type="password",
            placeholder="AIzaSy...",
            help="前往 https://aistudio.google.com 免费获取"
        )

        st.divider()

        # Question bank
        bank = load_bank()
        st.markdown(
            f'<p class="sb-label">📚 题库 '
            f'<span style="color:#4A5F80;font-size:.75rem;font-family:\'Noto Sans SC\',sans-serif;">'
            f'({len(bank)} 题)</span></p>',
            unsafe_allow_html=True
        )

        topic_colors = {
            "几何": "#60A5FA", "代数": "#F472B6",
            "数论": "#A78BFA", "组合": "#34D399", "概率": "#FB923C",
        }
        if bank:
            for i, q in enumerate(bank):
                tc = topic_colors.get(q.get("topic", ""), "#94A3B8")
                label = f"#{q.get('id', i+1)} [{q.get('topic','?')}] {q.get('title', '题目')[:16]}"
                if st.button(label, key=f"qb_{i}"):
                    st.session_state["qbank_selected"] = q
        else:
            st.markdown(
                '<p style="color:#4A5F80;font-size:.8rem;margin:.3rem 0;">'
                '题库为空，管理员可上传 PDF 导入</p>',
                unsafe_allow_html=True
            )

        st.divider()

        # Admin panel
        st.markdown('<p class="sb-label">⚙️ 管理后台</p>', unsafe_allow_html=True)
        with st.expander("🔐 管理员登录", expanded=False):
            pwd = st.text_input("管理员密码", type="password", key="admin_pwd_input")
            if pwd == ADMIN_PASSWORD:
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
    for k in ("qbank_selected",):
        if k not in st.session_state:
            st.session_state[k] = None

    api_key = render_sidebar()

    # Hero header
    st.markdown("""
<div class="hero-wrap">
  <div class="hero-icon">🏆</div>
  <h1 class="hero-title">AMC 8 智学助手</h1>
  <p class="hero-sub">AI · 竞赛数学 · 趣味解题</p>
  <span class="hero-badge">✨ 幽默教练 AI 驱动 · 让每道题都有故事</span>
</div>""", unsafe_allow_html=True)

    # Q-bank selected question
    if st.session_state.get("qbank_selected"):
        q = st.session_state.pop("qbank_selected")
        st.markdown(f"""
<div class="sc" style="border-color:rgba(99,102,241,.4);margin-bottom:1.2rem;">
  <p style="color:#818CF8;font-size:.82rem;margin:0 0 .6rem;">
    📚 题库题目 #{q.get('id','?')} ·
    <span style="color:#60A5FA;">{q.get('topic','—')}</span> ·
    {q.get('difficulty','—')}
  </p>
  <div class="sc-body">{q.get('content','').replace(chr(10),'<br>')}</div>
</div>""", unsafe_allow_html=True)

        if not api_key:
            st.warning("请在左侧边栏输入 Gemini API Key")
        else:
            with st.spinner("🧠 AI 教练正在认真读题中..."):
                try:
                    result = analyze_question(api_key, [f"请分析以下AMC 8题目：\n\n{q.get('content','')}"])
                    render_result(result)
                except Exception as e:
                    st.error(f"分析出错: {e}")
        st.markdown('<div class="footer"><p>🏆 AMC 8 智学助手 · Powered by Gemini 2.5 Flash & Edge-TTS</p></div>', unsafe_allow_html=True)
        return

    # Input tabs
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
                    with st.spinner("🧠 AI 教练正在认真读题，好题值得细品..."):
                        try:
                            result = analyze_question(
                                api_key,
                                ["请分析图片中的数学题目，按格式详细解答："] + content_parts
                            )
                        except Exception as e:
                            st.error(f"解析失败: {e}")
                            result = None
                    if result:
                        st.divider()
                        render_result(result)

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
                    with st.spinner("🧠 AI 教练正在思考中，冷笑话准备就绪..."):
                        try:
                            result = analyze_question(
                                api_key,
                                [f"请分析以下AMC 8题目：\n\n{q_text}"]
                            )
                        except Exception as e:
                            st.error(f"解析失败: {e}")
                            result = None
                    if result:
                        st.divider()
                        render_result(result)

    st.markdown("""
<div class="footer">
  <p>🏆 AMC 8 智学助手 · AI 趣味竞赛辅导 · 让每个孩子爱上数学</p>
  <p>Powered by Gemini 2.5 Flash &nbsp;·&nbsp; TTS by Edge-TTS (云希) &nbsp;·&nbsp; Built with Streamlit</p>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
