import json
import asyncio
from typing import AsyncGenerator, Dict, Any
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, ToolMessage

from backend.core.state import app_state, session_manager
from backend.prompts import TOOL_ROUTING_SYSTEM_PROMPT, FINAL_RESPONSE_SYSTEM_PROMPT
from backend.tools import AgentToolContext, create_agent_tools
from backend.services.history_scorer import get_history_scorer
from backend.utils.metrics import StreamMetricsTracker


class AgentOrchestrator:
    """
    Service điều phối Agent 2 lần gọi (Two-Stage Agent Orchestration):
    - Lần 1: Agent phân tích câu hỏi, đánh giá ngữ cảnh và điều phối Tool tra cứu / Intent Resolver.
    - Lần 2: LLM tổng hợp dữ liệu tra cứu theo các ràng buộc nghiêm ngặt (không suy diễn, bảo toàn format).
    """

    async def stream_query(self, query: str, session_id: str = "default_session") -> AsyncGenerator[Dict[str, Any], None]:
        try:
            # 1. Đảm bảo mô hình AI đã nạp hoàn tất
            if hasattr(app_state, "load_task") and app_state.load_task and not app_state.load_task.done():
                yield {"event": "status", "data": json.dumps({"step": "loading", "status": "info", "text": "Loading models..."})}
                await app_state.load_task

            llm = app_state.llm
            if llm is None:
                yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": "Lỗi: Chưa load được LLM."})}
                return

            session_manager.ensure_session(session_id)
            past_turns = session_manager.conversations[session_id]
            r_matrix = session_manager.relevance_matrices[session_id]

            # 2. Đánh giá tương đồng lịch sử qua TypeSafe Jev & Harmonic Bridge
            recent_turns = past_turns[-10:]
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
            yield {"event": "token", "data": json.dumps({"text": f"<think>\n{debug_text}\n"})}
            in_thinking = True

            history_context_text = eval_result.get("context_text", "")
            if history_context_text:
                user_prompt_content = f"[NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN (Độ tương đồng >= 0.7)]:\n{history_context_text}\n\nCâu hỏi hiện tại của người dùng: {query}"
            else:
                user_prompt_content = query

            # 3. Khởi tạo Context và Tool Calling cho lượt truy vấn
            tool_context = AgentToolContext(
                app_state=app_state,
                llm=llm,
                history_context_text=history_context_text
            )
            tools = create_agent_tools(tool_context)
            retrieved_context = tool_context.retrieved_context
            tool_logs = tool_context.tool_logs

            # Khởi tạo Agent chuẩn hóa với create_agent theo Rule 7
            agent = create_agent(llm, tools)

            metrics = StreamMetricsTracker()
            metrics.start()
            messages = [("system", TOOL_ROUTING_SYSTEM_PROMPT), ("user", user_prompt_content)]
            inputs = {"messages": messages}

            batch_text = ""
            full_answer = ""

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
                        reasoning = reasoning.replace("<think>", "").replace("</think>", "")
                        if not in_thinking:
                            batch_text += "<think>\n"
                            in_thinking = True
                        batch_text += reasoning

                    if isinstance(chunk_content, str) and chunk_content:
                        if "Execute Tool Call" in chunk_content or "Call tim_kiem_goi_cuoc" in chunk_content:
                            pass
                        else:
                            if in_thinking:
                                if "<think>" in chunk_content:
                                    chunk_content = chunk_content.replace("<think>", "")
                                if "</think>" in chunk_content:
                                    parts = chunk_content.split("</think>", 1)
                                    batch_text += parts[0] + "\n</think>\n"
                                    in_thinking = False
                                    after = parts[1]
                                    if after:
                                        batch_text += after
                                        full_answer += after
                                elif tool_calls or not chunk_content.strip():
                                    pass
                                else:
                                    batch_text += "\n</think>\n"
                                    in_thinking = False
                                    batch_text += chunk_content
                                    full_answer += chunk_content
                            else:
                                batch_text += chunk_content
                                full_answer += chunk_content

                    if batch_text:
                        yield {"event": "token", "data": json.dumps({"text": batch_text})}
                        batch_text = ""

                elif isinstance(chunk, ToolMessage):
                    metrics.on_tool_end()
                    if tool_logs:
                        log_text = "\n\n" + tool_logs.pop(0) + "\n\n"
                        if not in_thinking:
                            yield {"event": "token", "data": json.dumps({"text": "<think>" + log_text})}
                            in_thinking = True
                        else:
                            yield {"event": "token", "data": json.dumps({"text": log_text})}

            # --- LẦN GỌI LLM 2: Tổng hợp kết quả từ Tool với các constraint nghiêm ngặt ---
            has_search_context = any(item.get("tool") in ("search_general_knowledge", "search_telecom_packages") for item in retrieved_context)
            if has_search_context:
                context_blocks = []
                if history_context_text:
                    context_blocks.append(f"[NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN]:\n{history_context_text}")
                for item in retrieved_context:
                    if item["tool"] == "resolve_intent":
                        context_blocks.append(f"[KẾT QUẢ PHÂN TÍCH Ý ĐỊNH]:\n{item['data']}")
                    elif item["tool"] == "search_general_knowledge":
                        chunks = item["data"]
                        if not chunks:
                            context_blocks.append("Kết quả tra cứu kiến thức chung: Không tìm thấy tài liệu phù hợp.")
                        else:
                            doc_texts = []
                            for i, ch in enumerate(chunks, 1):
                                doc_texts.append(f"[Tài liệu {i} - Nguồn: {ch.get('source', '')}]\n{ch.get('content', '')}")
                            context_blocks.append("Kết quả tra cứu kiến thức chung:\n" + "\n\n".join(doc_texts))
                    elif item["tool"] == "search_telecom_packages":
                        context_blocks.append(f"Kết quả tra cứu gói cước viễn thông:\n{item['data']}")

                full_context_text = "\n\n".join(context_blocks)

                call2_messages = [
                    ("system", FINAL_RESPONSE_SYSTEM_PROMPT),
                    ("user", f"Câu hỏi của người dùng: {query}\n\n[DỮ LIỆU ĐÃ TRA CỨU ĐƯỢC TỪ HỆ THỐNG]:\n{full_context_text}")
                ]

                # Reset full_answer vì nội dung trả lời chính thức được sinh từ Lần 2
                full_answer = ""

                async for chunk in llm.astream(call2_messages):
                    reasoning = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                    chunk_content = chunk.content if hasattr(chunk, "content") else str(chunk)
                    usage = chunk.usage_metadata if hasattr(chunk, "usage_metadata") else None

                    metrics.on_token(has_content=bool(chunk_content or reasoning))
                    if usage:
                        metrics.update_usage(usage)

                    if reasoning:
                        reasoning = reasoning.replace("<think>", "").replace("</think>", "")
                        if not in_thinking:
                            batch_text += "<think>\n"
                            in_thinking = True
                        batch_text += reasoning

                    if isinstance(chunk_content, str) and chunk_content:
                        if in_thinking:
                            if "<think>" in chunk_content:
                                chunk_content = chunk_content.replace("<think>", "")
                            if "</think>" in chunk_content:
                                parts = chunk_content.split("</think>", 1)
                                batch_text += parts[0] + "\n</think>\n"
                                in_thinking = False
                                after = parts[1]
                                if after:
                                    batch_text += after
                                    full_answer += after
                            elif not chunk_content.strip():
                                pass
                            else:
                                batch_text += "\n</think>\n"
                                in_thinking = False
                                batch_text += chunk_content
                                full_answer += chunk_content
                        else:
                            batch_text += chunk_content
                            full_answer += chunk_content

                    if batch_text:
                        yield {"event": "token", "data": json.dumps({"text": batch_text})}
                        batch_text = ""

            if in_thinking:
                yield {"event": "token", "data": json.dumps({"text": "\n</think>\n"})}

            metrics.stop()
            stats_msg = metrics.get_stats_message()
            yield {"event": "stats", "data": json.dumps({"text": stats_msg})}

            # Format tool output của lượt này nếu có
            turn_tool_output_parts = []
            for item in retrieved_context:
                if item["tool"] == "resolve_intent":
                    turn_tool_output_parts.append(f"[Phân tích ý định]:\n{item.get('data', '')}")
                elif item["tool"] == "search_general_knowledge":
                    chunks = item.get("data", [])
                    for ch in chunks:
                        turn_tool_output_parts.append(f"[{ch.get('source', 'Tài liệu')}]\n{ch.get('content', '')}")
                elif item["tool"] == "search_telecom_packages":
                    turn_tool_output_parts.append(str(item.get("data", "")))
            turn_tool_output = "\n\n".join(turn_tool_output_parts) if turn_tool_output_parts else ""

            # Lưu lượt hội thoại và cập nhật ma trận r_ij
            session_manager.save_turn(
                session_id=session_id,
                user_query=query,
                agent_output=full_answer,
                tool_output=turn_tool_output,
                scored_messages=eval_result.get("scored_messages", [])
            )

        except Exception as e:
            import traceback
            with open("error.log", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": f"Error: {str(e)}"})}


orchestrator = AgentOrchestrator()
