import logging
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from langchain_deepseek import ChatDeepSeek
from backend.core.config import HF_ROUTER_BASE_URL, HF_LLM_MODEL, HF_VLM_MODEL

logger = logging.getLogger(__name__)


def get_llm_model(temperature=0.0, **kwargs):
    max_tokens = kwargs.get("num_predict", kwargs.get("max_tokens", None))
    if "num_predict" in kwargs:
        del kwargs["num_predict"]
    if "max_tokens" in kwargs:
        del kwargs["max_tokens"]

    hf_token = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
    if not hf_token:
        raise ValueError("Chưa cấu hình HF_API_KEY hoặc HF_TOKEN trong biến môi trường hoặc file .env.")

    logger.info("[LLM] Đang sử dụng model Hugging Face Router: %s", HF_LLM_MODEL)
    return ChatDeepSeek(
        api_base=HF_ROUTER_BASE_URL,
        api_key=hf_token,
        model=HF_LLM_MODEL,
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

    logger.info("[VLM] Đang sử dụng model Hugging Face Router: %s", HF_VLM_MODEL)
    return ChatDeepSeek(
        api_base=HF_ROUTER_BASE_URL,
        api_key=hf_token,
        model=HF_VLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        stream_usage=True,
        timeout=90.0,
        max_retries=3,
        **kwargs,
    )
