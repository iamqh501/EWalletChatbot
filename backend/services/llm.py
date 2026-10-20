import os
import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
import warnings
from langchain_deepseek import ChatDeepSeek
import backend.core.env

warnings.filterwarnings('ignore')

HF_BASE_URL = "https://router.huggingface.co/v1"

def get_llm_model(temperature=0.0, **kwargs):
    max_tokens = kwargs.get("num_predict", kwargs.get("max_tokens", None))
    if "num_predict" in kwargs:
        del kwargs["num_predict"]
    if "max_tokens" in kwargs:
        del kwargs["max_tokens"]

    hf_token = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
    if not hf_token:
        raise ValueError("Chưa cấu hình HF_API_KEY hoặc HF_TOKEN trong biến môi trường hoặc file .env.")

    hf_model = os.getenv("HF_MODEL_NAME", "inclusionAI/Ling-3.0-flash:fastest")
    print(f"[LLM] Đang sử dụng model Hugging Face Router: {hf_model}")
    return ChatDeepSeek(
        api_base=HF_BASE_URL,
        api_key=hf_token,
        model=hf_model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream_usage=True,
        timeout=60.0,
        max_retries=3,
        **kwargs,
    )

# Alias cho backward compatibility
get_model = get_llm_model
get_llama_cpp_model = get_llm_model

