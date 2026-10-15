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
from fastembed import SparseTextEmbedding
from backend.services.retrieval import get_dense_embedding_model
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, ToolMessage
from backend.core.config import QDRANT_PATH, STORE_PATH, DOCS_DIR
from backend.services.retrieval import search_and_rerank
from backend.services.llm import get_llm_model
from backend.services.history_scorer import get_history_scorer
from backend.utils.metrics import StreamMetricsTracker

# ==========================================
# 1. APP STATE
# ==========================================
class AppState:
    dense_model = None
    sparse_model = None
    qdrant_client = None
    store = None
    histories: Dict[str, List[Any]] = {}
    conversations: Dict[str, List[Dict[str, Any]]] = {}
    relevance_matrices: Dict[str, Dict[Tuple[int, int], float]] = {}
    llm = None
    load_task = None
    
    # Init progress tracking
    is_ready: bool = False
    current_loading_step: str = "Starting server..."
    loaded_components: List[str] = []
    init_listeners: List[asyncio.Queue] = []

app_state = AppState()

def notify_init_step(step_name: str):
    app_state.current_loading_step = step_name
    msg = {"event": "loading", "data": json.dumps({"text": step_name})}
    for q in list(app_state.init_listeners):
        try:
            q.put_nowait(msg)
        except Exception:
            pass

def notify_component_loaded(comp_name: str):
    if comp_name not in app_state.loaded_components:
        app_state.loaded_components.append(comp_name)
    msg = {"event": "loaded", "data": json.dumps({"component": comp_name})}
    for q in list(app_state.init_listeners):
        try:
            q.put_nowait(msg)
        except Exception:
            pass

def notify_init_complete():
    app_state.is_ready = True
    app_state.current_loading_step = ""
    msg = {"event": "complete", "data": json.dumps({"text": "System ready."})}
    for q in list(app_state.init_listeners):
        try:
            q.put_nowait(msg)
        except Exception:
            pass

def notify_init_error(err_msg: str):
    msg = {"event": "error", "data": json.dumps({"text": f"Error: {err_msg}"})}
    for q in list(app_state.init_listeners):
        try:
            q.put_nowait(msg)
        except Exception:
            pass



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

class ResolveIntentArgs(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc yêu cầu hiện tại của người dùng đang bị mơ hồ hoặc không chắc chắn.")
    uncertainty_reason: str = Field(..., description="Lý do chi tiết vì sao bạn không chắc chắn người dùng muốn gì (VD: câu hỏi có nhiều cách hiểu, thiếu chủ ngữ/thực thể tham chiếu).")

class QueryRequest(BaseModel):
    query: str
    session_id: str = "default_session"

# ==========================================
# 4. GLOBAL TOOLS (Core Logic)
# ==========================================
@tool(args_schema=SearchGeneralKnowledgeArgs)
def global_search_general_knowledge(query: str) -> List[Dict[str, Any]]:
    """Tìm kiếm thông tin hướng dẫn sử dụng, chính sách chung về ví điện tử."""
    results = search_and_rerank(
        query=query,
        dense_model=app_state.dense_model,
        sparse_model=app_state.sparse_model,
        client=app_state.qdrant_client,
        store=app_state.store,
        collection_name="knowledge"
    )
    # results đã được search_and_rerank sắp xếp theo score từ cao tới thấp
    chunks = []
    total_len = 0
    for res in results:
        content = res["content"]
        if total_len + len(content) > 60000:
            content = content[:60000 - total_len] + "... (đã cắt bớt do quá dài)"
            chunks.append({
                "source": res["source"],
                "score": round(float(res["score"]), 4),
                "content": content
            })
            break
        chunks.append({
            "source": res["source"],
            "score": round(float(res["score"]), 4),
            "content": content
        })
        total_len += len(content)
    return chunks

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
        notify_init_step("Loading Dense Embedding...")
        app_state.dense_model = await asyncio.to_thread(
            get_dense_embedding_model
        )
        notify_component_loaded("Dense Embedding")

        notify_init_step("Loading Sparse Embedding...")
        app_state.sparse_model = await asyncio.to_thread(
            SparseTextEmbedding, 
            model_name="Qdrant/bm25"
        )
        notify_component_loaded("Sparse Embedding")

        notify_init_step("Loading Reranker...")
        from backend.services.retrieval import get_reranker
        await asyncio.to_thread(get_reranker)
        notify_component_loaded("Reranker")
        
        notify_init_step("Connecting LLM...")
        if not hasattr(app_state, "llm") or app_state.llm is None:
            app_state.llm = await asyncio.to_thread(get_llm_model)

        notify_component_loaded("LLM")

        notify_init_complete()
        print("All models loaded successfully!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"CRITICAL ERROR: Failed to load models: {e}")
        notify_init_error(str(e))
        raise e

@asynccontextmanager
async def lifespan(app: FastAPI):
    t0_start = time.time()
    notify_init_step("Connecting Knowledge Base...")
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
    notify_component_loaded("Knowledge Base")
    
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
        if hasattr(app_state, "load_task") and app_state.load_task and not app_state.load_task.done():
            yield {"event": "status", "data": json.dumps({"step": "loading", "status": "info", "text": "Loading models..."})}
            await app_state.load_task
            
        llm = app_state.llm
        if llm is None:
            yield {"event": "status", "data": json.dumps({"step": "error", "status": "error", "text": "Lỗi: Chưa load được LLM."})}
            return
            
        if session_id not in app_state.histories:
            app_state.histories[session_id] = []
        if session_id not in app_state.conversations:
            app_state.conversations[session_id] = []
        if session_id not in app_state.relevance_matrices:
            app_state.relevance_matrices[session_id] = {}
            
        past_turns = app_state.conversations[session_id]
        r_matrix = app_state.relevance_matrices[session_id]
        
        # ==========================================
        # 6. ĐÁNH GIÁ TƯƠNG ĐỒNG LỊCH SỬ QUA JEV (TYPESAFE)
        # ==========================================
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
        
        # In ngắn gọn kết quả đánh giá ra frontend phần thinking để debug
        debug_text = eval_result["debug_text"]
        yield {"event": "token", "data": json.dumps({"text": f"<think>\n{debug_text}\n"})}
        in_thinking = True
        
        history_context_text = eval_result.get("context_text", "")
        if history_context_text:
            user_prompt_content = f"[NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN (Độ tương đồng >= 0.7)]:\n{history_context_text}\n\nCâu hỏi hiện tại của người dùng: {query}"
        else:
            user_prompt_content = query
        
        # ==========================================
        # 7. LOCAL TOOLS WITH STATE MANAGEMENT
        # ==========================================
        tool_logs = []
        retrieved_context = []
        tool_call_limits = {
            "search_general_knowledge": 1,
            "search_telecom_packages": 1,
            "resolve_intent": 1
        }
        
        @tool(args_schema=SearchGeneralKnowledgeArgs, return_direct=True)
        def search_general_knowledge(query: str) -> List[Dict[str, Any]]:
            """Tìm kiếm thông tin hướng dẫn sử dụng, chính sách chung về ví điện tử."""
            if tool_call_limits["search_general_knowledge"] <= 0:
                return [{"error": "[HỆ THỐNG] Bạn đã hết lượt gọi tool này. Hãy sử dụng thông tin hiện có để trả lời."}]
            tool_call_limits["search_general_knowledge"] = 0
            res = global_search_general_knowledge.invoke({"query": query})
            retrieved_context.append({"tool": "search_general_knowledge", "data": res})
            
            # Format output cho khối thinking:
            # 1. Đầu tiên in ra tổng số chunk
            # 2. Với mỗi chunk, chỉ in ra 2 dòng đầu thay vì toàn bộ nội dung
            if not res:
                tool_summary = "Tổng số chunk: 0\n(Không tìm thấy thông tin chung nào.)"
            else:
                lines = [f"Tổng số chunk: {len(res)}"]
                for i, chunk in enumerate(res, 1):
                    source = chunk.get("source", "Unknown")
                    score = chunk.get("score", 0.0)
                    content = chunk.get("content", "").strip()
                    content_lines = [l.strip() for l in content.split("\n") if l.strip()]
                    first_two_lines = "\n".join(content_lines[:2]) if content_lines else ""
                    lines.append(f"\n[Chunk {i} - Nguồn: {source} | Score: {score:.4f}]\n{first_two_lines}\n...")
                tool_summary = "\n".join(lines)

            tool_logs.append(f"**[GỌI TOOL]**\n\n`search_general_knowledge(query=\"{query}\")`\n\n```\n{tool_summary}\n```\n")
            return res

        @tool(args_schema=SearchTelecomPackagesArgs, return_direct=True)
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
            retrieved_context.append({"tool": "search_telecom_packages", "data": res})
            
            args_str = ", ".join([f"{k}={repr(v)}" for k, v in args_dict.items() if v is not None])
            short_res = res[:2500] + "..." if len(res) > 2500 else res
            tool_logs.append(f"**[GỌI TOOL]**\n\n`search_telecom_packages({args_str})`\n\n```\n{short_res}\n```\n")
            
            return res

        @tool(args_schema=ResolveIntentArgs)
        def resolve_intent(query: str, uncertainty_reason: str) -> str:
            """Sử dụng tool này khi bạn KHÔNG CHẮC CHẮN người dùng muốn gì (câu hỏi mơ hồ, có nhiều cách hiểu, thiếu chủ ngữ/thực thể).
            Tool thực hiện quy trình Intent Resolver 3 bước:
            1. Tạo danh sách hypothesis (cách hiểu hợp lý gồm nghĩa đen và nghĩa theo ngữ cảnh).
            2. Evidence-based evaluation (đối chiếu từng cách hiểu với query, lịch sử và trạng thái tác vụ).
            3. Decision (chọn cách hiểu đủ căn cứ, hoặc trả về nhiều khả năng, hoặc đề xuất câu hỏi làm rõ ngắn)."""
            if tool_call_limits["resolve_intent"] <= 0:
                return "[HỆ THỐNG] Bạn đã hết lượt gọi tool resolve_intent."
            tool_call_limits["resolve_intent"] = 0

            intent_prompt = f"""Bạn là công cụ phân tích và giải quyết ý định người dùng (Intent Resolver) cho trợ lý ảo ví điện tử và viễn thông.
Nhiệm vụ của bạn là giải quyết sự không chắc chắn về ý định của người dùng bằng quy trình 3 bước chặt chẽ:

[THÔNG TIN ĐẦU VÀO]
- Câu hỏi hiện tại: "{query}"
- Lý do không chắc chắn: "{uncertainty_reason}"
- Ngữ cảnh lịch sử cuộc trò chuyện (nếu có):
{history_context_text if history_context_text else "(Không có ngữ cảnh lịch sử)"}

[QUY TRÌNH XỬ LÝ 3 BƯỚC BẮT BUỘC]

1. DANH SÁCH HYPOTHESES (CÁC CÁCH HIỂU HỢP LÝ):
   - Đưa ra ít nhất 2 cách hiểu khác nhau về điều người dùng thực sự muốn:
     + Cách hiểu theo nghĩa đen (literal meaning): Dựa thuần túy vào câu từ hiện tại.
     + Cách hiểu dựa trên ngữ cảnh (context-based meaning): Dựa vào lịch sử trao đổi, các thực thể vừa nhắc tới (gói cước, tính năng ví, v.v.).

2. EVIDENCE-BASED EVALUATION (ĐỐI CHIẾU BẰNG CHỨNG):
   - Với từng hypothesis, phân tích:
     + Bằng chứng ủng hộ (từ câu từ query, từ lịch sử, từ logic tác vụ).
     + Bằng chứng phản bác hoặc điểm thiếu sót / chưa rõ ràng.
     + Đánh giá độ tin cậy (Cao / Trung bình / Thấp).

3. DECISION (QUYẾT ĐỊNH Ý ĐỊNH & HÀNH ĐỘNG):
   - Đưa ra quyết định rõ ràng:
     + NẾU ĐỦ CĂN CỨ: Chọn cách hiểu tối ưu nhất và chỉ định rõ ý định (tra cứu gói cước hay tra cứu kiến thức ví) kèm các từ khóa/tiêu chí cụ thể để gọi tool tra cứu tiếp theo.
     + NẾU CÓ NHIỀU KHẢ NĂNG TƯƠNG ĐƯƠNG: Trình bày tóm tắt các khả năng để phản hồi cho người dùng.
     + NẾU THIẾU CĂN CỨ: Đề xuất một câu hỏi làm rõ ngắn gọn, lịch sự để hỏi trực tiếp người dùng.

HÃY TRÌNH BÀY ĐẦY ĐỦ, RÕ RÀNG VÀ NGẮN GỌN THEO ĐÚNG 3 PHẦN TRÊN."""

            response = llm.invoke([("user", intent_prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            retrieved_context.append({"tool": "resolve_intent", "data": content})
            tool_logs.append(f"**[GỌI TOOL: resolve_intent]**\n- Lý do không chắc chắn: {uncertainty_reason}\n\n```\n{content}\n```\n")
            return content

        agent = create_agent(llm, [search_general_knowledge, search_telecom_packages, resolve_intent])

        TOOL_ROUTING_SYSTEM_PROMPT = """Bạn là trợ lý ảo hỗ trợ ví điện tử và tư vấn gói cước viễn thông. Nhiệm vụ của bạn là phân tích câu hỏi của người dùng và quyết định gọi tool tra cứu phù hợp. Tuân thủ NGHIÊM NGẶT các quy tắc sau:
1. BẮT BUỘC PHẢI CÓ NGỮ CẢNH TRA CỨU (từ lịch sử trò chuyện được cung cấp hoặc từ công cụ tra cứu) để trả lời:
   - [NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN] (nếu có ở bên dưới) được coi là ngữ cảnh tra cứu hợp lệ. Nếu ngữ cảnh này đã chứa ĐẦY ĐỦ THÔNG TIN để trả lời chính xác và trọn vẹn câu hỏi của người dùng, bạn KHÔNG CẦN gọi tool tra cứu thêm mà hãy trả lời trực tiếp dựa trên ngữ cảnh này.
   - Nếu CHƯA CÓ ngữ cảnh tra cứu hoặc ngữ cảnh lịch sử KHÔNG ĐỦ thông tin để trả lời, BẠN BẮT BUỘC PHẢI GỌI TOOL TRA CỨU (`search_general_knowledge` hoặc `search_telecom_packages`) ĐÚNG 1 LẦN để lấy dữ liệu. Tuyệt đối KHÔNG được tự bịa ra thông tin.
2. XỬ LÝ KHI KHÔNG CHẮC CHẮN Ý ĐỊNH NGƯỜI DÙNG:
   - Khi bạn KHÔNG CHẮC CHẮN người dùng muốn gì (câu hỏi mơ hồ, có nhiều cách hiểu, thiếu chủ ngữ/thực thể mà không thể xác định chắc chắn từ lịch sử), BẠN ĐƯỢC PHÉP GỌI TOOL `resolve_intent`.
   - Tool `resolve_intent` sẽ phân tích các hypothesis, đối chiếu bằng chứng và đưa ra quyết định (chọn cách hiểu chuẩn xác hoặc đề xuất câu hỏi làm rõ).
   - Sau khi gọi `resolve_intent`:
     + Nếu đã xác định được ý định tra cứu rõ ràng, bạn hãy gọi tiếp tool tra cứu tương ứng (`search_telecom_packages` hoặc `search_general_knowledge`).
     + Nếu kết luận là cần làm rõ từ người dùng hoặc trình bày các khả năng, bạn hãy phản hồi trực tiếp dựa trên kết quả của tool và kết thúc mà không cần gọi tool tra cứu.
3. Quy định gọi Tool tra cứu (khi đã rõ ý định nhưng chưa có đủ ngữ cảnh):
   - Khi được hỏi về MÃ GÓI CƯỚC (ví dụ: YOLO, BIG, D169G...), DATA, GIÁ TIỀN, CHU KỲ, 3G/4G/5G, BẠN BẮT BUỘC PHẢI GỌI TOOL `search_telecom_packages`.
   - Khi được hỏi về HƯỚNG DẪN SỬ DỤNG, LIÊN KẾT TÀI KHOẢN, NẠP/RÚT/CHUYỂN TIỀN, BIỂU PHÍ, CHÍNH SÁCH VÍ ĐIỆN TỬ, BẠN BẮT BUỘC PHẢI GỌI TOOL `search_general_knowledge`.
4. Mỗi tool tra cứu có lượt gọi tối đa là 1 lần. Tool `resolve_intent` có lượt gọi tối đa 1 lần.
5. Nếu câu hỏi chỉ là lời chào hỏi thông thường (như 'xin chào', 'hello', 'bạn là ai'), hãy phản hồi ngắn gọn, lịch sự và không cần gọi tool.
6. Khi trả lời trực tiếp từ ngữ cảnh lịch sử hoặc phản hồi làm rõ, TUYỆT ĐỐI tuân thủ: chỉ dùng thông tin có trong ngữ cảnh, không bình luận, không suy diễn thêm ngoài ngữ cảnh đã cho.
"""

        FINAL_RESPONSE_SYSTEM_PROMPT = """Bạn là trợ lý ảo hỗ trợ ví điện tử và tư vấn gói cước viễn thông. Nhiệm vụ của bạn là dựa vào thông tin được cung cấp từ ngữ cảnh tra cứu (kết quả từ công cụ tra cứu, phân tích ý định và/hoặc ngữ cảnh lịch sử liên quan) để trả lời câu hỏi của người dùng. Tuân thủ NGHIÊM NGẶT các quy định sau:
1. SỬ DỤNG DỮ LIỆU ĐÃ TRA CỨU / NGỮ CẢNH:
   - BẠN BẮT BUỘC PHẢI DÙNG DỮ LIỆU ĐÃ ĐƯỢC CUNG CẤP TRONG NGỮ CẢNH ĐỂ TRẢ LỜI NGƯỜI DÙNG bằng ngôn ngữ tự nhiên. Tuyệt đối KHÔNG tự bịa ra bất kỳ thông tin nào không có trong tài liệu/ngữ cảnh.
   - Nếu kết quả phân tích ý định chỉ ra nhiều khả năng hoặc đề xuất hỏi làm rõ, hãy trình bày rõ ràng các khả năng hoặc câu hỏi làm rõ đó cho người dùng.
   - Nếu kết quả tra cứu thông báo không tìm thấy hoặc rỗng và lịch sử không có thông tin, hãy thông báo rõ ràng là không tìm thấy thông tin phù hợp trong hệ thống thay vì tự suy diễn hay bịa đặt.
2. KHÔNG BÌNH LUẬN, KHÔNG SUY DIỄN:
   - TUYỆT ĐỐI KHÔNG đưa ra bình luận, khuyên người dùng nên làm gì, không thêm các lời khen chê hay đánh giá chủ quan.
   - Tuyệt đối không suy diễn thêm thông tin không có trong tài liệu tra cứu. Chỉ trả lời đúng và sát những gì tài liệu cung cấp.
3. TRÁNH REPHRASE:
   - Cố gắng đưa thông tin theo đúng nguyên văn và cú pháp trong tài liệu gốc, tránh việc diễn giải lại (rephrase) làm sai lệch ý nghĩa hoặc mất tính chuẩn xác.
4. FORMAT VÀ ĐỊNH DẠNG:
   - KHÔNG format cầu kỳ như tô màu nền cho bảng, in màu, in đậm, in nghiêng (trừ tiêu đề lớn và tiêu đề bảng có thể in đậm, nhưng phải nhất quán).
   - Giữ nguyên cấu trúc bảng hoặc danh sách nếu có trong tài liệu.
5. ĐỘ ĐẦY ĐỦ CỦA THÔNG TIN:
   - Nếu thông tin trong tài liệu có nội dung dài, cố gắng bao gồm đầy đủ thông tin, hạn chế tối đa việc tóm tắt hay cắt bớt để bảo đảm tính chuẩn xác của tài liệu gốc.
"""
        
        metrics = StreamMetricsTracker()
        metrics.start()
        messages = [("system", TOOL_ROUTING_SYSTEM_PROMPT), ("user", user_prompt_content)]
        inputs = {"messages": messages}
        
        batch_text = ""
        full_answer = ""
        in_thinking = False
        
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
                        
        if in_thinking: yield {"event": "token", "data": json.dumps({"text": "\n</think>\n"})}
            
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

        new_turn_id = len(past_turns) + 1
        # Lưu lại u_i và chính là r_ij cho các query sau:
        for item in eval_result.get("scored_messages", []):
            past_id = item["turn_id"]
            u_score = item["u_i"]
            r_matrix[(new_turn_id, past_id)] = u_score
            r_matrix[(past_id, new_turn_id)] = u_score

        # Lưu message vào lịch sử conversation
        past_turns.append({
            "id": new_turn_id,
            "user_query": query,
            "tool_output": turn_tool_output,
            "agent_output": full_answer
        })

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

@app.get("/api/init-stream")
async def init_stream():
    async def event_generator():
        # Gửi trước các thành phần đã nạp xong
        for comp in list(app_state.loaded_components):
            yield {"event": "loaded", "data": json.dumps({"component": comp})}
            
        if app_state.is_ready:
            yield {"event": "complete", "data": json.dumps({"text": "Hệ thống đã sẵn sàng!"})}
            return
            
        if app_state.current_loading_step:
            yield {"event": "loading", "data": json.dumps({"text": app_state.current_loading_step})}
            
        queue = asyncio.Queue()
        app_state.init_listeners.append(queue)
        try:
            while True:
                msg = await queue.get()
                yield msg
                if msg.get("event") in ("complete", "error"):
                    break
        finally:
            if queue in app_state.init_listeners:
                app_state.init_listeners.remove(queue)

    return EventSourceResponse(event_generator())

@app.get("/api/health")
async def health_check():
    return {
        "status": "ready" if app_state.is_ready else "loading",
        "is_ready": app_state.is_ready,
        "current_step": app_state.current_loading_step,
        "loaded_components": app_state.loaded_components
    }

