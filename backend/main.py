import os
import sys
import re
import time
import json
import asyncio
from typing import Optional, List, Dict, Any

# Ensure UTF-8 output on Windows CMD
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from langchain_huggingface import HuggingFaceEmbeddings
from fastembed import SparseTextEmbedding
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, ToolMessage
from backend.core.config import QDRANT_PATH, STORE_PATH, DOCS_DIR
from backend.services.retrieval import search_and_rerank
from backend.services.llm import get_llama_cpp_model

# ==========================================
# 1. APP STATE
# ==========================================
class AppState:
    dense_model = None
    sparse_model = None
    qdrant_client = None
    store = None
    histories: Dict[str, List[Any]] = {}
    llm = None
    load_task = None

app_state = AppState()

# Global task for tracking async model loading


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def load_package_data() -> List[Dict[str, Any]]:
    package_data = []
    try:
        json_path = os.path.join(DOCS_DIR, "goi_cuoc.json")
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        for item in raw_data:
            meta = item.get("metadata", {})
            try:
                price = meta.get("gia_vnd", 0)
                cycle = meta.get("chu_ky_d", 0)
                data_gb = meta.get("trung_binh_ngay", 0)
                package_data.append({
                    "package_name": str(meta.get("ten_goi", "")),
                    "price_vnd": float(price) if price != "" else 0.0,
                    "cycle_days": int(cycle) if cycle != "" else 0,
                    "data_gb_per_day": float(data_gb) if data_gb != "" else 0.0
                })
            except (ValueError, TypeError):
                pass
    except Exception as e:
        print(f"Error reading package file: {e}")
    return package_data

# ==========================================
# 3. PYDANTIC SCHEMAS FOR TOOLS & API
# ==========================================
class SearchGeneralKnowledgeArgs(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc từ khóa cần tìm kiếm về hướng dẫn sử dụng, chính sách chung về ví điện tử.")
#     Tham số đầu của Field() "..." có nghĩa là trường này bát buộc, không có giá trị mặc định.

class SearchTelecomPackagesArgs(BaseModel):
    package_name: Optional[str] = Field(None, description="Tên gói cước điện thoại (ví dụ: YOLO90_12T, BIG, D169G).")
    # Option[str] cho phép biến nhận kiểu str or None.
    price_min: Optional[float] = Field(None, description="Giá tiền tối thiểu (VNĐ).")
    price_max: Optional[float] = Field(None, description="Giá tiền tối đa (VNĐ).")
    cycle_days_min: Optional[int] = Field(None, description="Chu kỳ tối thiểu (tính bằng ngày). QUY ĐỔI BẮT BUỘC: 1 tuần = 7 ngày, 1 tháng = 30 ngày, 1 năm = 360 ngày.")
    cycle_days_max: Optional[int] = Field(None, description="Chu kỳ tối đa (tính bằng ngày). QUY ĐỔI BẮT BUỘC: 1 tuần = 7 ngày, 1 tháng = 30 ngày, 1 năm = 360 ngày.")
    data_gb_per_day_min: Optional[float] = Field(None, description="Dung lượng data tối thiểu mỗi ngày (GB).")
    data_gb_per_day_max: Optional[float] = Field(None, description="Dung lượng data tối đa mỗi ngày (GB).")

class RewriteQueryArgs(BaseModel):
    query_to_rewrite: str = Field(..., description="Câu hỏi hiện tại cần được viết lại để bổ sung ngữ cảnh.")
    reason: str = Field(..., description="Lý do chi tiết vì sao bạn cho rằng câu hỏi này cần được viết lại.")
    retrieved_info: Optional[str] = Field(None, description="Trích xuất thông tin bạn vừa nhận được từ tool tra cứu trước đó (nếu có).")

class QueryRequest(BaseModel):
    query: str
    session_id: str = "default_session"

# ==========================================
# 4. GLOBAL TOOLS (Core Logic)
# ==========================================
@tool(args_schema=SearchGeneralKnowledgeArgs)
def global_search_general_knowledge(query: str) -> str:
    """Tìm kiếm thông tin hướng dẫn sử dụng, chính sách chung về ví điện tử."""
    results = search_and_rerank(
        query=query,
        dense_model=app_state.dense_model,
        sparse_model=app_state.sparse_model,
        client=app_state.qdrant_client,
        store=app_state.store,
        collection_name="knowledge"
    )
    context_parts = []
    total_len = 0
    for i, res in enumerate(results, 1):
        chunk_text = f"[Nguồn {i} - File: {res['source']}]\n{res['content']}"
        if total_len + len(chunk_text) > 30000:
            context_parts.append(chunk_text[:30000 - total_len] + "... (đã cắt bớt do quá dài)")
            break
        context_parts.append(chunk_text)
        total_len += len(chunk_text)
    return "\n\n---\n\n".join(context_parts) if context_parts else "Không tìm thấy thông tin chung nào."

@tool(args_schema=SearchTelecomPackagesArgs)
def global_search_telecom_packages(
    package_name: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    cycle_days_min: Optional[int] = None,
    cycle_days_max: Optional[int] = None,
    data_gb_per_day_min: Optional[float] = None,
    data_gb_per_day_max: Optional[float] = None,
) -> str:
    """
    Tìm kiếm và đề xuất các gói cước điện thoại dựa trên các tiêu chí.
    NGUYÊN TẮC TÌM KIẾM THEO KHOẢNG: Nếu người dùng nói "khoảng", "tầm", "xấp xỉ" cho BẤT KỲ đại lượng nào (tiền, ngày, dung lượng), bắt buộc phải truyền CẢ 2 tham số min và max.
    NGUYÊN TẮC CHU KỲ: Bắt buộc tự quy đổi thời gian ra ngày trước khi điền: 1 tuần = 7 ngày, 1 tháng = 30 ngày, 1 năm = 360 ngày.
    """
    data = load_package_data()
    results = []
    for item in data:
        if package_name and package_name.upper() not in item["package_name"].upper(): continue
        if price_min is not None and item["price_vnd"] < price_min: continue
        if price_max is not None and item["price_vnd"] > price_max: continue
        if cycle_days_min is not None and item["cycle_days"] < cycle_days_min: continue
        if cycle_days_max is not None and item["cycle_days"] > cycle_days_max: continue
        if data_gb_per_day_min is not None and item["data_gb_per_day"] < data_gb_per_day_min: continue
        if data_gb_per_day_max is not None and item["data_gb_per_day"] > data_gb_per_day_max: continue
        
        formatted = {
            "Package Name": item["package_name"],
            "Price (VND)": item["price_vnd"],
            "Cycle (days)": item["cycle_days"],
            "Data per day (GB)": item["data_gb_per_day"]
        }
        results.append((formatted, item["cycle_days"], item["price_vnd"]))
    
    if not results:
        return json.dumps({"error": "Không tìm thấy gói cước nào thoả mãn."}, ensure_ascii=False)
        
    target = sum(v) / len(v) if (v:= {cycle_days_min, cycle_days_max} - {None}) else None
    if target:
        results = sorted(results, key=lambda x: (abs(x[1] - target), x[2]))
    else:
        results = sorted(results, key=lambda x: x[2])

    return json.dumps({"matched_plans": [x[0] for x in results]}, ensure_ascii=False)


# ==========================================
# 5. APP SETUP & STREAMING
# ==========================================
async def load_models_background():
    print("Loading AI Models into memory...")
    try:
        app_state.dense_model = await asyncio.to_thread(
            HuggingFaceEmbeddings, 
            model_name="sentence-transformers/all-MiniLM-L12-v2", 
            model_kwargs={'device': 'cpu'}
        )
        app_state.sparse_model = await asyncio.to_thread(
            SparseTextEmbedding, 
            model_name="Qdrant/bm25"
        )
        from backend.services.retrieval import get_reranker
        await asyncio.to_thread(get_reranker)
        
        if not hasattr(app_state, "llm") or app_state.llm is None:
            app_state.llm = await asyncio.to_thread(get_llama_cpp_model)
        print("All models loaded successfully!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"CRITICAL ERROR: Failed to load models: {e}")
        raise e

@asynccontextmanager
async def lifespan(app: FastAPI):
    t0_start = time.time()
    # Retry loop to handle Qdrant local file lock during Uvicorn hot-reload
    for attempt in range(10):
        try:
            app_state.qdrant_client = QdrantClient(path=QDRANT_PATH)
            break
        except Exception as e:
            if "already accessed by another instance" in str(e) or "Permission denied" in str(e):
                await asyncio.sleep(1)
            else:
                raise e
    
    fs = LocalFileStore(STORE_PATH)
    app_state.store = EncoderBackedStore(
        store=fs,
        key_encoder=lambda x: x,
        value_serializer=lambda doc: json.dumps(doc.model_dump()).encode("utf-8"),
        value_deserializer=lambda bytes_data: Document(**json.loads(bytes_data.decode("utf-8")))
    )
    
    # Start models loading in the background without blocking HTTP server startup
    app_state.load_task = asyncio.create_task(load_models_background())
    print(f"Hệ thống khởi động HTTP server hoàn tất trong {time.time() - t0_start:.2f}s. Đang nạp mô hình AI dưới nền...")
    
    yield
    if app_state.qdrant_client:
        app_state.qdrant_client.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def stream_query(query: str, session_id: str):
    try:
        if hasattr(app_state, "load_task") and not app_state.load_task.done():
            yield {"event": "status", "data": json.dumps({"step": "loading", "status": "info", "text": "Đang nạp mô hình AI vào bộ nhớ, vui lòng chờ trong giây lát (khoảng 15-30s)..."})}
            await app_state.load_task
            
        llm = app_state.llm
        if llm is None:
            yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": "Lỗi: Chưa load được LLM."})}
            return
            
        if session_id not in app_state.histories:
            app_state.histories[session_id] = []
        history = app_state.histories[session_id]
        
        current_query = query
        
        # ==========================================
        # 6. LOCAL TOOLS WITH STATE MANAGEMENT
        # ==========================================
        tool_logs = []
        tool_call_limits = {
            "search_general_knowledge": 1,
            "search_telecom_packages": 1,
            "rewrite_query": 1
        }
        
        @tool(args_schema=SearchGeneralKnowledgeArgs)
        def search_general_knowledge(query: str) -> str:
            """Tìm kiếm thông tin hướng dẫn sử dụng, chính sách chung về ví điện tử."""
            if tool_call_limits["search_general_knowledge"] <= 0:
                return "[HỆ THỐNG] Bạn đã hết lượt gọi tool này. Hãy sử dụng thông tin hiện có để trả lời."
            tool_call_limits["search_general_knowledge"] = 0
            res = global_search_general_knowledge.invoke({"query": query})
            short_res = res[:1500] + "..." if len(res) > 1500 else res
            tool_logs.append(f"**[GỌI TOOL]**\n\n`search_general_knowledge(query=\"{query}\")`\n\n```\n{short_res}\n```\n")
            return res

        @tool(args_schema=SearchTelecomPackagesArgs)
        def search_telecom_packages(
            package_name: Optional[str] = None,
            price_min: Optional[float] = None,
            price_max: Optional[float] = None,
            cycle_days_min: Optional[int] = None,
            cycle_days_max: Optional[int] = None,
            data_gb_per_day_min: Optional[float] = None,
            data_gb_per_day_max: Optional[float] = None,
        ) -> str:
            """
            Tìm kiếm và đề xuất các gói cước điện thoại dựa trên các tiêu chí.
            NGUYÊN TẮC: Bắt buộc tự quy đổi thời gian ra ngày trước khi điền: 1 tuần = 7 ngày, 1 tháng = 30 ngày, 1 năm = 360 ngày.
            """
            if tool_call_limits["search_telecom_packages"] <= 0:
                return "[HỆ THỐNG] Bạn đã hết lượt gọi tool này. Hãy sử dụng thông tin hiện có để trả lời."
            tool_call_limits["search_telecom_packages"] = 0
            
            args_dict = {
                "package_name": package_name,
                "price_min": price_min,
                "price_max": price_max,
                "cycle_days_min": cycle_days_min,
                "cycle_days_max": cycle_days_max,
                "data_gb_per_day_min": data_gb_per_day_min,
                "data_gb_per_day_max": data_gb_per_day_max
            }
            res = global_search_telecom_packages.invoke(args_dict)
            
            args_str = ", ".join([f"{k}={repr(v)}" for k, v in args_dict.items() if v is not None])
            short_res = res[:1500] + "..." if len(res) > 1500 else res
            tool_logs.append(f"**[GỌI TOOL]**\n\n`search_telecom_packages({args_str})`\n\n```\n{short_res}\n```\n")
            
            return res
            
        @tool(args_schema=RewriteQueryArgs)
        def rewrite_query_tool(query_to_rewrite: str, reason: str, retrieved_info: Optional[str] = None) -> str:
            """Sử dụng tool này để viết lại câu hỏi nếu bạn cảm thấy không rõ ý của người hỏi (VD: bị thiếu chủ ngữ do ngữ cảnh từ lịch sử trò chuyện). Tool sẽ tự động dùng LLM để viết lại câu hỏi hoàn chỉnh."""
            if tool_call_limits["rewrite_query"] <= 0:
                return "[HỆ THỐNG] Bạn đã hết lượt gọi tool này."
            tool_call_limits["rewrite_query"] = 0
            
            # Reset lượt gọi cho 2 tool tra cứu
            tool_call_limits["search_general_knowledge"] = 1
            tool_call_limits["search_telecom_packages"] = 1

            if len(history) == 0: return query_to_rewrite
            
            history_text = ""
            # Lấy tối đa 6 tin nhắn cuối (tương đương 3 hội thoại: User-AI)
            recent_history = history[-6:]
            for msg in recent_history:
                role = "User" if isinstance(msg, HumanMessage) else "AI"
                history_text += f"{role}: {msg.content}\n"
            
            prompt = f"""Bạn là công cụ viết lại câu hỏi (Rewrite Query). Nhiệm vụ của bạn là làm rõ Câu hỏi hiện tại để các công cụ tìm kiếm có đủ thông tin tra cứu độc lập. Tuân thủ NGHIÊM NGẶT các quy tắc sau:

1. BẢO TOÀN Ý ĐỊNH: Không được bóp méo hay thay đổi bản chất câu hỏi gốc của User dựa vào câu trả lời của AI. Câu hỏi mới phải giữ nguyên mục đích hỏi ban đầu.
2. BỔ SUNG NGỮ CẢNH BẰNG "Context:": Nếu câu hỏi nhắc đến "các gói trên", "gói này", "nó"... bạn phải trích xuất các điều kiện, tiêu chí hoặc thông tin cụ thể từ Câu trả lời của AI trong lịch sử và đính kèm vào sau câu hỏi.
3. ĐỊNH DẠNG BẮT BUỘC: [Câu hỏi đã được làm rõ từ ngữ]. Context: [Liệt kê chi tiết các điều kiện, tên gói cước, hoặc thông tin cụ thể từ lịch sử mà user đang ám chỉ].
Ví dụ:
- Câu hỏi cũ: "trong các gói trên, gói nào rẻ nhất"
- Câu mới: "trong các gói trên, gói nào rẻ nhất. Context: các gói trên mà user nhắc tới là các gói data một năm, rẻ hơn 1 triệu, thông tin cụ thể các gói là: [thông tin chi tiết các gói được lấy từ lịch sử trả lời của AI]."
4. CHỈ IN RA Câu hỏi mới (bao gồm phần Context nếu có), tuyệt đối không giải thích dài dòng hay thêm bất kỳ từ ngữ nào khác.

[LỊCH SỬ TRÒ CHUYỆN (Tối đa 3 hội thoại gần nhất)]
{history_text.strip()}

[LÝ DO TỪ LLM YÊU CẦU VIẾT LẠI]
{reason}

[THÔNG TIN ĐÃ TRA CỨU TỪ CÂU HỎI HIỆN TẠI (NẾU CÓ)]
{retrieved_info if retrieved_info else "Không có"}

[CẦN XỬ LÝ]
Câu hỏi hiện tại: {query_to_rewrite}
Câu hỏi mới:"""
            
            response = llm.invoke([("user", prompt)])
            content = response.content
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            res = content if content else query_to_rewrite
            short_res = res[:1500] + "..." if len(res) > 1500 else res
            tool_logs.append(f"**[GỌI TOOL]**\n\n`rewrite_query_tool(query_to_rewrite={repr(query_to_rewrite)}, reason={repr(reason)})`\n\n```\n{short_res}\n```\n")
            return res

        agent = create_agent(llm, [search_general_knowledge, search_telecom_packages, rewrite_query_tool])

        SYSTEM_PROMPT = f"""Bạn là trợ lý ảo hỗ trợ ví điện tử và tư vấn gói cước viễn thông. Tuân thủ NGHIÊM NGẶT các quy tắc sau:
1. MỖI LẦN TRẢ LỜI CÂU HỎI (trừ khi chỉ là lời chào), BẠN BẮT BUỘC PHẢI GỌI TOOL TRA CỨU (`search_general_knowledge` hoặc `search_telecom_packages`) ĐỂ LẤY THÔNG TIN. Tuyệt đối KHÔNG được tự bịa ra thông tin.
2. Quy định về thứ tự gọi Tool:
   - Với các câu hỏi bình thường, BẠN BẮT BUỘC PHẢI GỌI TOOL TRA CỨU TRƯỚC. Nếu kết quả tra cứu không có hoặc bạn nhận ra câu hỏi bị thiếu chủ ngữ/ngữ cảnh, lúc đó mới gọi tool `rewrite_query_tool` để làm rõ.
   - Nếu câu hỏi của người dùng thực chất chỉ là một câu bổ sung thông tin cho câu hỏi liền trước (ví dụ: "cho tôi gói rẻ hơn", "thêm 1 chút data"), bạn được phép gọi `rewrite_query_tool` trước để khôi phục ngữ cảnh, sau đó mới gọi tool tra cứu.
3. Khi được hỏi về MÃ GÓI CƯỚC (ví dụ: YOLO, BIG, D169G...), DATA, GIÁ TIỀN, CHU KỲ, 3G/4G/5G, BẠN BẮT BUỘC PHẢI GỌI TOOL `search_telecom_packages`.
4. Tuyệt đối không được tự suy diễn mã gói cước là thiết bị/điện thoại.
5. Mỗi tool có lượt gọi còn lại mặc định là 1. Sau khi gọi tool `rewrite_query_tool`, lượt gọi của các tool tra cứu sẽ được reset về 1 để bạn có thể tra cứu lại.
6. Nếu kết quả tra cứu trả về thông tin, hãy dùng nó để trả lời. Nếu không tìm thấy, hãy thông báo là không có thông tin thay vì bịa đặt.
7. Khi đã có kết quả từ các tool, BẠN PHẢI DÙNG KẾT QUẢ ĐÓ ĐỂ TRẢ LỜI NGƯỜI DÙNG bằng ngôn ngữ tự nhiên. TUYỆT ĐỐI KHÔNG đưa ra bình luận, khuyên người dùng làm gì hay tự suy diễn thêm thông tin không có trong tài liệu. Chỉ trả lời đúng những gì tài liệu cung cấp.
8. FORMAT VÀ NỘI DUNG TRẢ LỜI:
   - Cố gắng đưa thông tin theo đúng format trong tài liệu, tránh rephrase.
   - KHÔNG format cầu kỳ như tô màu nền cho bảng, in màu, in đậm, in nghiêng (trừ tiêu đề lớn và tiêu đề bảng có thể in đậm, nhưng phải nhất quán).
   - Nếu người dùng yêu cầu thông tin có nội dung dài, cố gắng bao gồm đầy đủ thông tin, hạn chế việc tóm tắt hay cắt bớt (đảm bảo thông tin chuẩn từ tài liệu, không bịa ra).
"""

        
        t_start = time.time()
        messages = [("system", SYSTEM_PROMPT), ("user", current_query)]
        inputs = {"messages": messages}
        
        batch_text = ""
        full_answer = ""
        first_token_time = None
        in_thinking = False
        
        input_tokens = 0
        output_tokens = 0
        
        last_chunk_time = t_start
        in_llm_generation = False
        total_prompt_time = 0.0
        total_gen_time = 0.0
        
        async for chunk, metadata in agent.astream(inputs, stream_mode="messages"):
            current_time = time.time()
            if isinstance(chunk, AIMessageChunk) and metadata.get("langgraph_node") == "model":
                reasoning = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                chunk_content = chunk.content if hasattr(chunk, "content") else str(chunk)
                usage = chunk.usage_metadata if hasattr(chunk, "usage_metadata") else None
                
                if not in_llm_generation:
                    if chunk_content or reasoning:
                        in_llm_generation = True
                        total_prompt_time += (current_time - last_chunk_time)
                        last_chunk_time = current_time
                        if first_token_time is None: 
                            first_token_time = current_time
                else:
                    total_gen_time += (current_time - last_chunk_time)
                    last_chunk_time = current_time
                
                if reasoning:
                    if not in_thinking:
                        batch_text += "<think>\n"
                        in_thinking = True
                    batch_text += reasoning
                if isinstance(chunk_content, str) and chunk_content:
                    if "Execute Tool Call" in chunk_content or "Call tim_kiem_goi_cuoc" in chunk_content:
                        pass
                    else:
                        if in_thinking:
                            batch_text += "\n</think>\n"
                            in_thinking = False
                        batch_text += chunk_content
                        full_answer += chunk_content
                    
                if usage:
                    input_tokens += usage.get("input_tokens", 0)
                    output_tokens += usage.get("output_tokens", 0)
                
                if batch_text:
                    yield {"event": "token", "data": json.dumps({"text": batch_text})}
                    batch_text = ""
                    
            elif isinstance(chunk, ToolMessage):
                in_llm_generation = False
                last_chunk_time = current_time
                
                if tool_logs:
                    log_text = "\n\n" + tool_logs.pop(0) + "\n\n"
                    if not in_thinking:
                        yield {"event": "token", "data": json.dumps({"text": "<think>" + log_text})}
                        in_thinking = True
                    else:
                        yield {"event": "token", "data": json.dumps({"text": log_text})}
                        
        if in_thinking: yield {"event": "token", "data": json.dumps({"text": "\n</think>\n"})}
            
        t_end = time.time()
        total_time = t_end - t_start
        ttft = (first_token_time - t_start) if first_token_time else 0
        
        prompt_speed = input_tokens / total_prompt_time if total_prompt_time > 0 else 0
        gen_speed = output_tokens / total_gen_time if total_gen_time > 0 else 0
        
        stats_msg = f"\n\nTTFT: {ttft:.2f}s | Prompt: {prompt_speed:.1f} t/s ({input_tokens}t) | Gen: {gen_speed:.1f} t/s ({output_tokens}t) | Total: {total_time:.2f}s"
        yield {"event": "stats", "data": json.dumps({"text": stats_msg})}
            
        app_state.histories[session_id].append(HumanMessage(content=query))
        app_state.histories[session_id].append(AIMessage(content=full_answer))

    except Exception as e:
        import traceback
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": f"Error: {str(e)}"})}

@app.post("/api/query")
async def query_endpoint(req: QueryRequest):
    return EventSourceResponse(stream_query(req.query, req.session_id))

@app.get("/api/health")
async def health_check():
    return {"status": "ready"}
