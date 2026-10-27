import logging
from typing import Dict, Any, AsyncGenerator, Optional
from pydantic import Field
from langchain_core.messages import SystemMessage, HumanMessage

from backend.core.state import app_state
from backend.services.llm import get_vlm_model
from backend.prompts.vlm import VLM_REWRITE_SYSTEM_PROMPT
from backend.tools.schemas import SubscriptableBaseModel

logger = logging.getLogger(__name__)


class VLMResponse(SubscriptableBaseModel):
    """Schema chuẩn hóa cho đầu ra phân tích hình ảnh và viết lại câu hỏi của VLM."""
    description: str = Field(
        ...,
        description="Miêu tả chi tiết, trung thực và chính xác các thông tin, văn bản, tiêu đề, nút bấm, số liệu hoặc lỗi hiển thị trên hình ảnh."
    )
    rewritten_query: str = Field(
        ...,
        description="Câu hỏi tra cứu hoàn chỉnh đã được viết lại, kết hợp đầy đủ ngữ cảnh từ ảnh và ý định ban đầu của người dùng để đưa vào pipeline xử lý."
    )


class VLMService:
    def __init__(self):
        self._model = None
        self._structured_model = None
        self._cached_underlying_model = None

    def get_model(self):
        if hasattr(app_state, "vlm") and app_state.vlm is not None:
            return app_state.vlm
        if self._model is None:
            self._model = get_vlm_model()
        return self._model

    def get_structured_model(self):
        current_model = self.get_model()
        if self._structured_model is None or self._cached_underlying_model is not current_model:
            self._structured_model = current_model.with_structured_output(VLMResponse)
            self._cached_underlying_model = current_model
        return self._structured_model

    async def stream_describe_and_rewrite(
        self,
        query: str,
        image_data: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream kết quả phân tích hình ảnh và viết lại câu hỏi trực tiếp qua Structured Output của VLM.
        Yields các dict dạng {"token": text_chunk, "done": False} phục vụ UI.
        Khi kết thúc yields {"done": True, "result": {"description": ..., "rewritten_query": ...}}.
        """
        structured_vlm = self.get_structured_model()

        # Đảm bảo format image_data đúng chuẩn data URL
        formatted_image_url = image_data.strip()
        if not formatted_image_url.startswith("data:") and not formatted_image_url.startswith("http"):
            formatted_image_url = f"data:image/jpeg;base64,{formatted_image_url}"

        effective_user_text = query.strip() if query and query.strip() else "Hãy quan sát hình ảnh và miêu tả nội dung, sau đó tạo câu hỏi tra cứu thích hợp."
        user_prompt = f"Câu hỏi gốc của người dùng: {effective_user_text}\n\nHãy quan sát hình ảnh và phân tích theo schema."

        messages = [
            SystemMessage(content=VLM_REWRITE_SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": formatted_image_url}}
            ])
        ]

        header_desc_emitted = False
        header_query_emitted = False
        prev_desc = ""
        prev_query = ""
        final_obj: Optional[VLMResponse] = None

        try:
            async for chunk in structured_vlm.astream(messages):
                final_obj = chunk
                curr_desc = getattr(chunk, "description", "") or ""
                curr_query = getattr(chunk, "rewritten_query", "") or ""

                if curr_desc and not header_desc_emitted:
                    yield {"token": "### MIÊU TẢ HÌNH ẢNH\n", "done": False}
                    header_desc_emitted = True

                if len(curr_desc) > len(prev_desc):
                    delta = curr_desc[len(prev_desc):]
                    yield {"token": delta, "done": False}
                    prev_desc = curr_desc

                if curr_query and not header_query_emitted:
                    prefix = "\n\n### CÂU HỎI VIẾT LẠI\n" if header_desc_emitted else "### CÂU HỎI VIẾT LẠI\n"
                    yield {"token": prefix, "done": False}
                    header_query_emitted = True

                if len(curr_query) > len(prev_query):
                    delta = curr_query[len(prev_query):]
                    yield {"token": delta, "done": False}
                    prev_query = curr_query
        except Exception as e:
            logger.warning(f"Warning during VLM stream processing: {e}")

        if final_obj is None or not getattr(final_obj, "rewritten_query", None):
            final_obj = await structured_vlm.ainvoke(messages)

        yield {
            "done": True,
            "result": {
                "description": final_obj.description,
                "rewritten_query": final_obj.rewritten_query
            }
        }


vlm_service = VLMService()
