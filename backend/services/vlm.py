import re
from typing import Dict, Any, AsyncGenerator
from langchain_core.messages import SystemMessage, HumanMessage

from backend.core.state import app_state
from backend.services.llm import get_vlm_model
from backend.prompts.vlm import VLM_REWRITE_SYSTEM_PROMPT


def parse_vlm_response(raw_text: str, original_query: str) -> Dict[str, str]:
    """Tách phần miêu tả hình ảnh và câu hỏi viết lại từ đầu ra của VLM."""
    pattern = r'(?:^|\n)\s*(?:###|##|\*\*|#)?\s*CÂU HỎI VIẾT LẠI\s*(?:\*\*|:)?\s*\n*(.*)'
    match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
    if match:
        rewritten = match.group(1).strip()
        desc = raw_text[:match.start()].strip()
    else:
        rewritten = original_query or raw_text.strip()
        desc = raw_text.strip()

    desc = re.sub(r'^\s*(?:###|##|\*\*|#)?\s*MIÊU TẢ HÌNH ẢNH\s*(?:\*\*|:)?\s*\n*', '', desc, flags=re.IGNORECASE).strip()
    rewritten = re.sub(r'^\*+\s*', '', rewritten).strip()
    desc = re.sub(r'^\*+\s*', '', desc).strip()

    if not rewritten:
        rewritten = original_query or desc

    return {
        "raw_text": raw_text,
        "description": desc,
        "rewritten_query": rewritten
    }


class VLMService:
    def __init__(self):
        self._model = None

    def get_model(self):
        if hasattr(app_state, "vlm") and app_state.vlm is not None:
            return app_state.vlm
        if self._model is None:
            self._model = get_vlm_model()
        return self._model

    async def stream_describe_and_rewrite(
        self,
        query: str,
        image_data: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream kết quả phân tích hình ảnh và viết lại câu hỏi từ VLM.
        Yields các dict dạng {"token": text_chunk, "done": False}.
        Khi kết thúc yields {"done": True, "result": {...}}.
        """
        vlm = self.get_model()

        # Đảm bảo format image_data đúng chuẩn data URL
        formatted_image_url = image_data.strip()
        if not formatted_image_url.startswith("data:") and not formatted_image_url.startswith("http"):
            formatted_image_url = f"data:image/jpeg;base64,{formatted_image_url}"

        effective_user_text = query.strip() if query and query.strip() else "Hãy quan sát hình ảnh và miêu tả nội dung, sau đó tạo câu hỏi tra cứu thích hợp."
        user_prompt = f"Câu hỏi gốc của người dùng: {effective_user_text}\n\nHãy quan sát hình ảnh và thực hiện theo đúng định dạng được hướng dẫn."

        messages = [
            SystemMessage(content=VLM_REWRITE_SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": formatted_image_url}}
            ])
        ]

        full_raw_text = ""
        async for chunk in vlm.astream(messages):
            reasoning = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
            content = chunk.content if hasattr(chunk, "content") else str(chunk)

            token_to_emit = ""
            if reasoning:
                token_to_emit += reasoning
            if content and isinstance(content, str):
                token_to_emit += content

            if token_to_emit:
                full_raw_text += token_to_emit
                yield {"token": token_to_emit, "done": False}

        parsed = parse_vlm_response(full_raw_text, query)
        yield {"done": True, "result": parsed}


vlm_service = VLMService()
