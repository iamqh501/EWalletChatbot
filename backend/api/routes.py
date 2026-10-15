import json
import asyncio
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import QueryRequest, HealthResponse
from backend.core.state import app_state
from backend.services.agent_orchestrator import orchestrator

router = APIRouter(prefix="/api")


@router.post("/query")
async def query_endpoint(req: QueryRequest):
    """Endpoint xử lý câu hỏi qua Agent với SSE streaming."""
    return EventSourceResponse(orchestrator.stream_query(req.query, req.session_id))


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
