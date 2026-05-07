import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')

if not api_key:
    print("请在 .env 文件中设置 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=api_key)

print("可用的 Gemini 模型:\n")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"- {model.name}")
        print(f"  描述: {model.description}")
        print()
