import os
import sys
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')

try:
    import google.generativeai as genai
except ImportError:
    print("正在安装 google-generativeai...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "google-generativeai"])
    import google.generativeai as genai

genai.configure(api_key=api_key)

print("尝试多个可能的模型列表:\n")

models_to_try = [
    'gemini-2.0-flash-exp',
    'gemini-2.0-flash',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-1.5-flash-8b',
    'gemini-1.0-pro-vision',
    'gemini-pro-vision',
]

for model_name in models_to_try:
    try:
        model = genai.GenerativeModel(model_name)
        print(f"✓ {model_name} - 可能可用")
    except Exception as e:
        print(f"✗ {model_name} - 不可用: {e}")

print("\n\n列出所有可用的模型:\n")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"获取模型列表失败: {e}")
