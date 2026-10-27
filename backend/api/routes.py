import json
import asyncio
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import QueryRequest, HealthResponse, ConsentRequest
from backend.core.state import app_state, session_manager
from backend.services.agent_orchestrator import orchestrator
from backend.services.doc_manager import doc_manager

router = APIRouter(prefix="/api")


@router.post("/query")
async def query_endpoint(req: QueryRequest):
    """Endpoint xử lý câu hỏi qua Agent với SSE streaming."""
    if req.consent is not None:
        session_manager.set_consent(req.session_id, req.consent)
    return EventSourceResponse(orchestrator.stream_query(req.query, req.session_id, req.image))


@router.post("/consent")
async def update_consent_endpoint(req: ConsentRequest):
    """Cập nhật quyền truy cập thông tin cá nhân cho session."""
    session_manager.set_consent(req.session_id, req.consent)
    return {
        "status": "ok",
        "session_id": req.session_id,
        "consent": session_manager.get_consent(req.session_id)
    }


@router.get("/consent/{session_id}")
async def get_consent_endpoint(session_id: str):
    """Lấy trạng thái quyền truy cập thông tin cá nhân hiện tại của session."""
    return {
        "session_id": session_id,
        "consent": session_manager.get_consent(session_id)
    }


@router.get("/init-stream")
async def init_stream():
    """Endpoint stream tiến trình khởi tạo và nạp các thành phần AI dưới nền."""
    async def event_generator():
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


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Endpoint kiểm tra sức khỏe hệ thống và trạng thái nạp model."""
    return {
        "status": "ready" if app_state.is_ready else "loading",
        "is_ready": app_state.is_ready,
        "current_step": app_state.current_loading_step,
        "loaded_components": app_state.loaded_components
    }


# ==========================================
# DOCUMENT MANAGEMENT ENDPOINTS
# ==========================================

@router.get("/docs")
async def list_documents_endpoint():
    """Lấy danh sách các tài liệu trong thư mục docs/ kèm trạng thái index và category."""
    try:
        docs = await asyncio.to_thread(doc_manager.list_documents)
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docs/sync")
async def sync_documents_endpoint():
    """Đồng bộ toàn bộ thay đổi (thêm, sửa, xóa) trong docs/ vào database."""
    try:
        res = await doc_manager.sync_all_documents()
        if res.get("status") == "error":
            raise HTTPException(status_code=503, detail=res.get("reason", "Lỗi đồng bộ tài liệu"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docs/upload")
async def upload_document_endpoint(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None)
):
    """Tải lên file tài liệu mới vào subfolder tương ứng và tự động index."""
    try:
        content_bytes = await file.read()
        res = await doc_manager.upload_file(file.filename, content_bytes, category=category)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs/{file_path:path}")
async def get_document_endpoint(file_path: str):
    """Lấy nội dung chi tiết của một tài liệu (Markdown text hoặc Excel rows)."""
    try:
        data = await asyncio.to_thread(doc_manager.get_document_content, file_path)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/docs/{file_path:path}")
async def update_document_endpoint(file_path: str, payload: dict = Body(...)):
    """Chỉnh sửa nội dung file (text Markdown hoặc bảng rows Excel) và tự động index lại."""
    try:
        res = await doc_manager.save_document_content(file_path, payload)
        return res
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/docs/{file_path:path}")
async def delete_document_endpoint(file_path: str):
    """Xóa file tài liệu và un-index khỏi database."""
    try:
        res = await doc_manager.delete_document(file_path)
        return res
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docs/{file_path:path}/reindex")
async def reindex_single_document_endpoint(file_path: str):
    """Yêu cầu index lại một file tài liệu cụ thể."""
    try:
        res = await doc_manager.index_single_document(file_path)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("reason", "Lỗi index tài liệu"))
        return res
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
