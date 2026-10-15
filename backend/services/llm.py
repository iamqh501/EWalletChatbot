import os
import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
import warnings
from langchain_deepseek import ChatDeepSeek
import json
from backend.core.config import BASE_DIR

warnings.filterwarnings('ignore')

config_path = os.path.join(BASE_DIR, "local_paths.json")
try:
    with open(config_path, "r", encoding="utf-8") as f:
        PATHS_CONFIG = json.load(f)
except FileNotFoundError:
    PATHS_CONFIG = {}

def get_llm_model(temperature=0.0, **kwargs):
    max_tokens = kwargs.get("num_predict", kwargs.get("max_tokens", None))
    if "num_predict" in kwargs:
        del kwargs["num_predict"]
    if "max_tokens" in kwargs:
        del kwargs["max_tokens"]

    hf_token = os.getenv("HF_TOKEN") or PATHS_CONFIG.get("HF_TOKEN")
    if not hf_token:
        raise ValueError("Chưa cấu hình HF_TOKEN trong local_paths.json hoặc biến môi trường.")

    hf_model = PATHS_CONFIG.get("HF_MODEL_NAME", "Qwen/Qwen3.5-9B:fastest")
    hf_base_url = PATHS_CONFIG.get("HF_BASE_URL", "https://router.huggingface.co/v1")
    print(f"[LLM] Đang sử dụng model Hugging Face Router: {hf_model}")
    return ChatDeepSeek(
        api_base=hf_base_url,
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

