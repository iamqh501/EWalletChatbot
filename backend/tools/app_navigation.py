import logging
import os
import json
from typing import Optional, Dict, Any
from qdrant_client import models

from backend.core.config import NAVIGATION_MAP_FILE, APP_GUIDE_FILE, APP_GUIDE_REL_PATHS, COLLECTION_NAME
from backend.services.retrieval import search_and_rerank

logger = logging.getLogger(__name__)


def load_navigation_map() -> Dict[str, Any]:
    """Tải sơ đồ điều hướng navigation_map.json."""
    if os.path.exists(NAVIGATION_MAP_FILE):
        try:
            with open(NAVIGATION_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("[Error] Không đọc được navigation_map.json: %s", e)
    return {}


def execute_guide_app_task(
    task_query: str,
    current_screen: Optional[str] = None,
    nav_map: Optional[Dict[str, Any]] = None,
    dense_model=None,
    sparse_model=None,
    client=None,
    store=None
) -> str:
    """
    Truy vấn chunk hướng dẫn tác vụ từ cơ sở dữ liệu tri thức và cung cấp kèm
    sơ đồ điều hướng navigation_map.json làm grounding data cho mô hình suy luận.
    """
    # 1. Nạp navigation_map.json (dùng nav_map từ app_state nếu đã truyền vào)
    if nav_map is None:
        nav_map = load_navigation_map()

    # 2. Truy vấn chunk hướng dẫn tác vụ từ database với filter theo file navigation
    file_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.file_path",
                match=models.MatchAny(any=APP_GUIDE_REL_PATHS)
            )
        ]
    )
    guide_results = search_and_rerank(
        query=task_query,
        dense_model=dense_model,
        sparse_model=sparse_model,
        client=client,
        store=store,
        collection_name=COLLECTION_NAME,
        filter=file_filter
    ) if dense_model and sparse_model and client and store else []

    if not guide_results:
        return "Không tìm thấy tài liệu hướng dẫn cho tác vụ này trong cơ sở dữ liệu."

    best = guide_results[0]
    required_screen_id = best.metadata.get("required_screen_id") if best.metadata else None

    output = f"""=== DỮ LIỆU ĐIỀU HƯỚNG VÀ HƯỚNG DẪN TÁC VỤ ỨNG DỤNG ===
- Nguồn trích xuất: {best.source or os.path.basename(APP_GUIDE_FILE)} (Score: {best.score:.4f})
- Màn hình người dùng đang đứng (nếu có): {current_screen or 'Chưa xác định (mặc định xuất phát từ Trang chủ/HOME nếu câu hỏi không nêu rõ)'}
- Màn hình đích thực hiện tác vụ (từ metadata): {required_screen_id or 'Tự xác định từ tài liệu hướng dẫn'}

[HƯỚNG DẪN THAO TÁC CHI TIẾT TỪ TÀI LIỆU]:
{best.content}

[SƠ ĐỒ ĐIỀU HƯỚNG VÀ CÁC MÀN HÌNH (NAVIGATION MAP)]:
{json.dumps(nav_map, ensure_ascii=False, indent=2)}
"""
    return output.strip()
