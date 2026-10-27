import logging
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from langchain_deepseek import ChatDeepSeek
import backend.core.env
from backend.core.config import HF_ROUTER_BASE_URL, DEFAULT_HF_LLM_MODEL, DEFAULT_HF_VLM_MODEL

logger = logging.getLogger(__name__)

HF_BASE_URL = HF_ROUTER_BASE_URL

def get_llm_model(temperature=0.0, **kwargs):
    max_tokens = kwargs.get("num_predict", kwargs.get("max_tokens", None))
    if "num_predict" in kwargs:
        del kwargs["num_predict"]
    if "max_tokens" in kwargs:
        del kwargs["max_tokens"]

    hf_token = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
    if not hf_token:
        raise ValueError("Chưa cấu hình HF_API_KEY hoặc HF_TOKEN trong biến môi trường hoặc file .env.")

    hf_model = os.getenv("HF_LLM_MODEL_NAME", os.getenv("HF_MODEL_NAME", DEFAULT_HF_LLM_MODEL))
    logger.info("[LLM] Đang sử dụng model Hugging Face Router: %s", hf_model)
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


def get_vlm_model(temperature=0.0, **kwargs):
    max_tokens = kwargs.get("num_predict", kwargs.get("max_tokens", 1000))
    if "num_predict" in kwargs:
        del kwargs["num_predict"]
    if "max_tokens" in kwargs:
        del kwargs["max_tokens"]

    hf_token = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
    if not hf_token:
        raise ValueError("Chưa cấu hình HF_API_KEY hoặc HF_TOKEN trong biến môi trường hoặc file .env.")

    hf_vlm_model = os.getenv("HF_VLM_MODEL_NAME", DEFAULT_HF_VLM_MODEL)
    if hf_vlm_model.startswith("iinclusionAI/"):
        hf_vlm_model = "inclusionAI/" + hf_vlm_model[len("iinclusionAI/"):]

    logger.info("[VLM] Đang sử dụng model Hugging Face Router: %s", hf_vlm_model)
    return ChatDeepSeek(
        api_base=HF_BASE_URL,
        api_key=hf_token,
        model=hf_vlm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream_usage=True,
        timeout=90.0,
        max_retries=3,
        **kwargs,
    )
