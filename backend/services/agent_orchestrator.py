import logging
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional, List, Tuple
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, ToolMessage

from backend.core.state import app_state, session_manager
from backend.prompts import TOOL_ROUTING_SYSTEM_PROMPT, FINAL_RESPONSE_SYSTEM_PROMPT
from backend.tools.factory import AgentToolContext, create_agent_tools
from backend.services.history_scorer import get_history_scorer
from backend.services.vlm import vlm_service
from backend.utils.metrics import StreamMetricsTracker

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Service điều phối Agent 2 lần gọi (Two-Stage Agent Orchestration):
    - Lần 1: Agent phân tích câu hỏi, đánh giá ngữ cảnh và điều phối Tool tra cứu / Intent Resolver.
    - Lần 2: LLM tổng hợp dữ liệu tra cứu theo các ràng buộc nghiêm ngặt (không suy diễn, bảo toàn format).
    """

    @staticmethod
    def _split_thinking_and_answer(text: str, in_thinking: bool) -> Tuple[List[Tuple[str, str]], bool]:
        """
        Tách các thẻ <think>...</think> lồng trong nội dung chunk thành danh sách sự kiện ('thinking' | 'token', text)
        và trả về trạng thái in_thinking kế tiếp.
        """
        events: List[Tuple[str, str]] = []
        remaining = text

        while remaining:
            if in_thinking:
                end_idx = remaining.find("</think>")
                if end_idx != -1:
                    before = remaining[:end_idx]
                    if before:
                        events.append(("thinking", before))
                    in_thinking = False
                    remaining = remaining[end_idx + len("</think>"):]
                else:
                    events.append(("thinking", remaining))
                    remaining = ""
            else:
                start_idx = remaining.find("<think>")
                if start_idx != -1:
                    before = remaining[:start_idx]
                    if before:
                        events.append(("token", before))
                    in_thinking = True
                    remaining = remaining[start_idx + len("<think>"):]
                else:
                    events.append(("token", remaining))
                    remaining = ""

        return events, in_thinking

    async def stream_query(self, query: str, session_id: str = "default_session", image: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            # 1. Đảm bảo mô hình AI đã nạp hoàn tất
            if hasattr(app_state, "load_task") and app_state.load_task and not app_state.load_task.done():
                yield {"event": "status", "data": json.dumps({"step": "loading", "status": "info", "text": "Loading models..."})}
                await app_state.load_task

            llm = app_state.llm
            if llm is None:
                yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": "Lỗi: Chưa load được LLM."})}
                return

            # 1.5. Xử lý VLM nếu câu hỏi có đính kèm ảnh
            if image and isinstance(image, str) and image.strip():
                yield {"event": "thinking", "data": json.dumps({"text": "[VLM] Đang kích hoạt mô hình Vision-Language để phân tích hình ảnh và viết lại câu hỏi...\n\n"})}

                vlm_res = None
                async for item in vlm_service.stream_describe_and_rewrite(query, image):
                    if item.get("done"):
                        vlm_res = item.get("result")
                    else:
                        token_text = item.get("token", "")
                        if token_text:
                            yield {"event": "thinking", "data": json.dumps({"text": token_text})}

                if vlm_res and vlm_res.get("rewritten_query"):
                    query = vlm_res["rewritten_query"]
                    yield {"event": "thinking", "data": json.dumps({"text": f"\n\n[Query Rewrite hoàn tất]: Câu hỏi đưa vào pipeline: \"{query}\"\n\n"})}

            # 2. Đánh giá tương đồng lịch sử qua TypeSafe Jev & Harmonic Bridge
            recent_turns = session_manager.get_recent_turns(session_id, limit=10)
            r_matrix = session_manager.get_relevance_matrix(session_id)
            history_scorer = get_history_scorer()
            eval_result = await asyncio.to_thread(
                history_scorer.evaluate_recent_history,
                current_query=query,
                recent_turns=recent_turns,
                r_matrix=r_matrix,
                a=0.5,
                threshold=0.7
            )

            # In kết quả đánh giá tương đồng ra frontend khối thinking
            debug_text = eval_result["debug_text"]
            yield {"event": "thinking", "data": json.dumps({"text": f"{debug_text}\n"})}

            history_context_text = eval_result.get("context_text", "")
            if history_context_text:
                user_prompt_content = f"[NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN (Độ tương đồng >= 0.7)]:\n{history_context_text}\n\nCâu hỏi hiện tại của người dùng: {query}"
            else:
                user_prompt_content = query

            # 3. Khởi tạo Context và Tool Calling cho lượt truy vấn
            tool_context = AgentToolContext(
                app_state=app_state,
                llm=llm,
                session_id=session_id,
                history_context_text=history_context_text
            )
            tools = create_agent_tools(tool_context)
            tool_logs = tool_context.tool_logs

            agent = create_agent(llm, tools)

            metrics = StreamMetricsTracker()
            metrics.start()
            messages = [("system", TOOL_ROUTING_SYSTEM_PROMPT), ("user", user_prompt_content)]
            inputs = {"messages": messages}

            # --- LẦN GỌI LLM 1: Agent phân tích và điều phối Tool ---
            async for chunk, metadata in agent.astream(inputs, stream_mode="messages"):
                if isinstance(chunk, AIMessageChunk) and metadata.get("langgraph_node") == "model":
                    reasoning = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                    chunk_content = chunk.content if hasattr(chunk, "content") else str(chunk)
                    usage = chunk.usage_metadata if hasattr(chunk, "usage_metadata") else None
                    tool_calls = getattr(chunk, "tool_calls", None)

                    metrics.on_token(has_content=bool(chunk_content or reasoning))
                    if usage:
                        metrics.update_usage(usage)
                    if tool_calls:
                        metrics.on_tool_start()

                    if reasoning:
                        clean_reasoning = reasoning.replace("<think>", "").replace("</think>", "")
                        if clean_reasoning:
                            yield {"event": "thinking", "data": json.dumps({"text": clean_reasoning})}

                    if isinstance(chunk_content, str) and chunk_content:
                        cleaned = chunk_content.replace("<think>", "").replace("</think>", "")
                        if cleaned.strip():
                            yield {"event": "thinking", "data": json.dumps({"text": cleaned})}

                elif isinstance(chunk, ToolMessage):
                    metrics.on_tool_end()
                    if tool_logs:
                        log_text = "\n\n" + tool_logs.pop(0) + "\n\n"
                        yield {"event": "thinking", "data": json.dumps({"text": log_text})}

            # --- LẦN GỌI LLM 2: Tổng hợp kết quả từ các Tool (mỗi tool tự format context_block) ---
            context_blocks = []
            if history_context_text:
                context_blocks.append(f"[NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN]:\n{history_context_text}")

            for item in tool_context.retrieved_context:
                if item.context_block:
                    context_blocks.append(item.context_block)

            if context_blocks:
                full_context_text = "\n\n".join(context_blocks)
            else:
                full_context_text = "(Không có dữ liệu tra cứu từ công cụ hay lịch sử trước đó)"

            call2_messages = [
                ("system", FINAL_RESPONSE_SYSTEM_PROMPT),
                ("user", f"Câu hỏi của người dùng: {query}\n\n[DỮ LIỆU ĐÃ TRA CỨU ĐƯỢC TỪ HỆ THỐNG VÀ LỊCH SỬ]:\n{full_context_text}")
            ]

            full_answer = ""
            in_call2_thinking = False

            async for chunk in llm.astream(call2_messages):
                reasoning = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                chunk_content = chunk.content if hasattr(chunk, "content") else str(chunk)
                usage = chunk.usage_metadata if hasattr(chunk, "usage_metadata") else None

                metrics.on_token(has_content=bool(chunk_content or reasoning))
                if usage:
                    metrics.update_usage(usage)

                if reasoning:
                    clean_reasoning = reasoning.replace("<think>", "").replace("</think>", "")
                    if clean_reasoning:
                        yield {"event": "thinking", "data": json.dumps({"text": clean_reasoning})}

                if isinstance(chunk_content, str) and chunk_content:
                    parsed_events, in_call2_thinking = self._split_thinking_and_answer(
                        chunk_content, in_call2_thinking
                    )
                    for ev_type, ev_text in parsed_events:
                        if ev_type == "token":
                            full_answer += ev_text
                        yield {"event": ev_type, "data": json.dumps({"text": ev_text})}

            metrics.stop()
            stats_msg = metrics.get_stats_message()
            yield {"event": "stats", "data": json.dumps({"text": stats_msg})}

            if tool_context.transaction_history_consent:
                yield {"event": "consent_required", "data": json.dumps({"action": "transaction_history", "session_id": session_id})}

            # Lưu lượt hội thoại và cập nhật ma trận r_ij (hoàn toàn không lưu tool_output)
            session_manager.save_turn(
                session_id=session_id,
                user_query=query,
                agent_output=full_answer,
                scored_messages=eval_result.get("scored_messages", [])
            )

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": f"Error: {str(e)}"})}


orchestrator = AgentOrchestrator()
