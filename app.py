"""
AMC 8 智学助手 — app.py (已修复 Duplicate Key 报错)
技术栈: Streamlit + Google Gemini 2.0 Flash + Edge-TTS (云希)
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
import requests

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

html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(150deg, #0C1829 0%, #1A2B45 100%);
    color: var(--text);
    font-family: 'Noto Sans SC', sans-serif;
}

.stButton > button {
    background: linear-gradient(90deg, #F5C842 0%, #E5B721 100%);
    color: #0C1829 !important;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    padding: 0.6rem 1.2rem;
    transition: all 0.3s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(245,200,66,0.4);
}

.card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# ─── Utils ──────────────────────────────────────────────────────────────────────
def analyze_question(api_key, content_list):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = """
    你是一位风趣幽默的AMC 8金牌教练。请按以下结构分析题目：
    1. 【数学小剧场】：讲一个与该题考点相关的数学家故事或趣味历史背景。
    2. 【教练透视眼】：分析考点和难度。
    3. 【逻辑拆解步】：用接地气、段子手风格分步骤讲解逻辑。
    使用Markdown格式，数学公式请务必使用 LaTeX 格式 (例如 $E=mc^2$)。
    """
    
    response = model.generate_content([prompt] + content_list)
    return response.text

async def text_to_speech(text):
    import edge_tts
    communicate = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        await communicate.save(tmp_file.name)
        return tmp_file.name

# ─── UI Rendering ────────────────────────────────────────────────────────────────
def render_result(result_text, key_prefix="default"):
    """
    增加了 key_prefix 参数，确保页面上多个结果区域的按钮 ID 不冲突。
    """
    st.markdown(f'<div class="card">{result_text}</div>', unsafe_allow_html=True)
    
    # 使用动态 Key 修复 Duplicate Key 报错
    btn_key = f"{key_prefix}_voice_play"
    
    if st.button("🔊 听听教练怎么说", key=btn_key, use_container_width=True):
        clean_text = re.sub(r'[*#_`]', '', result_text)
        with st.spinner("🎵 云希教练正在开嗓..."):
            audio_path = asyncio.run(text_to_speech(clean_text))
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/mp3")
            os.unlink(audio_path)

# ─── Main App ────────────────────────────────────────────────────────────────────
def main():
    st.title("🏆 AMC 8 智学助手")
    st.markdown("---")

    # Sidebar: Config
    with st.sidebar:
        st.header("⚙️ 设置")
        user_api_key = st.text_input("Gemini API Key", type="password")
        api_key = user_api_key if user_api_key else st.secrets.get("GEMINI_API_KEY")
        
        mode = st.radio("模式选择", ["📚 官方题库", "📸 拍照/上传", "✍️ 手动输入"])
        
        st.divider()
        with st.expander("🔒 管理员入口"):
            admin_pwd = st.text_input("管理密码", type="password")
            if admin_pwd == st.secrets.get("ADMIN_PASSWORD"):
                st.success("已解锁上传权限")
                st.file_uploader("上传新PDF入库", type="pdf")

    # Logic Flows
    if mode == "📚 官方题库":
        st.subheader("选择题库进行练习")
        # 假设数据从 GitHub 读取
        repo_url = "https://raw.githubusercontent.com/hzbeck7/AMC8-math-learner/main/data"
        lessons = [f"L{str(i).zfill(2)}" for i in range(1, 14)]
        selected_l = st.selectbox("选择课程模块", lessons)
        
        # 模拟展示该模块下的题目（实际可从 JSON 读取）
        st.info(f"正在加载 {selected_l} 题库...")
        
        if st.session_state.get("ai_result_bank"):
            render_result(st.session_state["ai_result_bank"], key_prefix="bank")

    elif mode == "📸 拍照/上传":
        st.subheader("上传题目图片或截图")
        up_file = st.file_uploader("选择文件", type=["png", "jpg", "jpeg", "pdf"])
        
        if up_file and api_key:
            if st.button("🚀 开始智能解析", key="btn_upload"):
                with st.spinner("AI 正在扫描图纸..."):
                    # 模拟处理
                    res = analyze_question(api_key, ["请分析这张图片中的题目"])
                    st.session_state["ai_result_upload"] = res
        
        if st.session_state.get("ai_result_upload"):
            render_result(st.session_state["ai_result_upload"], key_prefix="upload")

    elif mode == "✍️ 手动输入":
        st.subheader("输入题目文字内容")
        q_text = st.text_area("在此输入题目描述...", height=150)
        
        if q_text and api_key:
            if st.button("🚀 开始智能解析", key="btn_manual"):
                with st.spinner("AI 正在思考逻辑..."):
                    res = analyze_question(api_key, [f"分析题目: {q_text}"])
                    st.session_state["ai_result_manual"] = res
        
        if st.session_state.get("ai_result_manual"):
            render_result(st.session_state["ai_result_manual"], key_prefix="manual")

    # Footer
    st.markdown("---")
    st.caption("由 Gemini 2.0 Flash 驱动 | 云希语音提供技术支持")

if __name__ == "__main__":
    if "ai_result_bank" not in st.session_state: st.session_state["ai_result_bank"] = None
    if "ai_result_upload" not in st.session_state: st.session_state["ai_result_upload"] = None
    if "ai_result_manual" not in st.session_state: st.session_state["ai_result_manual"] = None
    main()
