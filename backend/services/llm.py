import logging
import os
from langchain_deepseek import ChatDeepSeek
from backend.core.config import HF_ROUTER_BASE_URL, HF_LLM_MODEL, HF_VLM_MODEL

logger = logging.getLogger(__name__)


def get_llm_model(temperature: float = 0.0, max_tokens: int | None = None, **kwargs):
    logger.info("[LLM] Đang sử dụng model Hugging Face Router: %s", HF_LLM_MODEL)
    return ChatDeepSeek(
        api_base=HF_ROUTER_BASE_URL,
        api_key=os.getenv("HF_TOKEN"),
        model=HF_LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        stream_usage=True,
        timeout=60.0,
        max_retries=3,
        **kwargs,
    )


def get_vlm_model(temperature: float = 0.0, max_tokens: int | None = 1000, **kwargs):
    logger.info("[VLM] Đang sử dụng model Hugging Face Router: %s", HF_VLM_MODEL)
    return ChatDeepSeek(
        api_base=HF_ROUTER_BASE_URL,
        api_key=os.getenv("HF_TOKEN"),
        model=HF_VLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        stream_usage=True,
        timeout=90.0,
        max_retries=3,
        **kwargs,
    )
