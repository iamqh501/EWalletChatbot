import os
import re
import json
from typing import Optional, Dict, Any, List
from qdrant_client import models

from backend.core.config import DOCS_DIR
from backend.services.retrieval import get_reranker

NAVIGATION_MAP_FILE = os.path.join(DOCS_DIR, "navigation_map.json")


def load_navigation_map() -> Dict[str, Any]:
    """Tải sơ đồ điều hướng navigation_map.json."""
    if os.path.exists(NAVIGATION_MAP_FILE):
        try:
            with open(NAVIGATION_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Error] Không đọc được navigation_map.json: {e}")
    return {}


def resolve_screen_id(
    candidate: Optional[str],
    screens: Dict[str, Any],
    fallback_text: Optional[str] = None
) -> str:
    """
    Xác định screen_id dựa trên navigation_map.json một cách linh hoạt, data-driven.
    Đối chiếu candidate hoặc fallback_text với:
    - screen_id
    - title
    - visual_cues
    """
    if not screens:
        return "HOME"

    def normalize_str(s: str) -> str:
        s = s.lower()
        s = re.sub(r'[\-_/]', ' ', s)
        return s.strip()

    # 1. Nếu candidate được truyền vào
    if candidate:
        cand_upper = candidate.strip().upper()
        if cand_upper in screens:
            return cand_upper

        cand_norm = normalize_str(candidate)
        for s_id, s_info in screens.items():
            if normalize_str(s_id) in cand_norm:
                return s_id
            s_title = normalize_str(s_info.get("title", ""))
            if s_title and (s_title in cand_norm or cand_norm in s_title):
                return s_id

    # 2. Match từ context text (task_query / rewritten query)
    search_text = []
    if candidate:
        search_text.append(candidate)
    if fallback_text:
        search_text.append(fallback_text)

    corpus = normalize_str(" ".join(search_text))

    best_screen = None
    best_score = 0

    for s_id, s_info in screens.items():
        score = 0
        s_id_norm = normalize_str(s_id)
        s_title_norm = normalize_str(s_info.get("title", ""))

        if s_id_norm in corpus:
            score += 10
        if s_title_norm and s_title_norm in corpus:
            score += 12

        title_tokens = [w for w in s_title_norm.split() if len(w) > 2]
        for token in title_tokens:
            if token in corpus:
                score += 2

        visual_cues = s_info.get("visual_cues", "")
        if visual_cues:
            quotes = re.findall(r"['\"]([^'\"]+)['\"]", visual_cues)
            for q in quotes:
                q_norm = normalize_str(q)
                if q_norm and q_norm in corpus:
                    score += 3

        if score > best_score:
            best_score = score
            best_screen = s_id

    if best_screen and best_score >= 3:
        return best_screen

    return "HOME"


def build_navigation_path(
    current_screen_id: str,
    target_screen_id: str,
    screens: Dict[str, Any],
    global_nav: Dict[str, Any]
) -> List[str]:
    """Xây dựng các bước di chuyển giữa 2 màn hình hoàn toàn từ navigation_map.json."""
    steps = []
    current_info = screens.get(current_screen_id, {})
    target_info = screens.get(target_screen_id, {})
    current_title = current_info.get("title", current_screen_id)
    target_title = target_info.get("title", target_screen_id)

    if current_screen_id == target_screen_id:
        steps.append(f"Bạn hiện đang ở sẵn màn hình **{target_title}** (`{target_screen_id}`).")
        return steps

    def get_action_from_home(target_id: str) -> Optional[str]:
        home_navs = screens.get("HOME", {}).get("navigates_to", [])
        for item in home_navs:
            if item.get("target") == target_id:
                return item.get("action")
        for item in global_nav.get("items", []):
            if item.get("target") == target_id:
                return item.get("action")
        return None

    if current_screen_id == "HOME":
        action = get_action_from_home(target_screen_id)
        if action:
            steps.append(f"Tại màn hình **Trang chủ** (`HOME`): {action} để vào màn hình **{target_title}**.")
        else:
            steps.append(f"Tại màn hình **Trang chủ** (`HOME`): Điều hướng đến màn hình **{target_title}**.")
    else:
        # Bước 1: Thoát màn hình con hoặc tab hiện tại về Trang chủ (HOME)
        exit_action = current_info.get("exit_action")
        if exit_action:
            steps.append(f"Bước 1 (Thoát màn hình hiện tại): {exit_action}.")
        elif not current_info.get("has_bottom_bar", True):
            steps.append(f"Bước 1 (Thoát màn hình hiện tại): Bấm nút 'X' ở góc trên cùng bên phải màn hình để đóng và quay lại Trang chủ (`HOME`).")
        else:
            home_tab_action = None
            for item in global_nav.get("items", []):
                if item.get("target") == "HOME":
                    home_tab_action = item.get("action")
                    break
            if home_tab_action:
                steps.append(f"Bước 1: {home_tab_action} để về Trang chủ (`HOME`).")
            else:
                steps.append(f"Bước 1: Quay về màn hình Trang chủ (`HOME`).")

        # Bước 2: Từ Trang chủ (HOME) vào màn hình đích
        action = get_action_from_home(target_screen_id)
        if action:
            steps.append(f"Bước 2 (Vào màn hình đích): Tại màn hình Trang chủ (`HOME`), {action} để vào màn hình **{target_title}**.")
        else:
            steps.append(f"Bước 2 (Vào màn hình đích): Tại Trang chủ (`HOME`), chọn để vào màn hình **{target_title}**.")

    return steps


def retrieve_app_guide_chunk_from_db(
    task_query: str,
    dense_model,
    sparse_model,
    client,
    store,
    collection_name: str = "knowledge"
) -> Optional[Dict[str, Any]]:
    """Truy vấn chunk hướng dẫn tác vụ phù hợp từ file cach_dung_ap.md / cach_dung_app.md trong database."""
    try:
        if dense_model is None or sparse_model is None or client is None or store is None:
            return None

        query_dense_vec = dense_model.embed_query(task_query)
        query_sparse_res = list(sparse_model.embed([task_query]))[0]

        file_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.file_path",
                    match=models.MatchAny(any=["cach_dung_ap.md", "cach_dung_app.md"])
                )
            ]
        )

        results = client.query_points(
            collection_name=collection_name,
            prefetch=[
                models.Prefetch(
                    query=query_dense_vec,
                    using="dense",
                    limit=10,
                    filter=file_filter
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=query_sparse_res.indices.tolist(),
                        values=query_sparse_res.values.tolist()
                    ),
                    using="sparse",
                    limit=10,
                    filter=file_filter
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=10,
            with_payload=True,
        )

        unique_parent_ids = []
        seen = set()
        for pt in results.points:
            pid = pt.payload.get("metadata", {}).get("doc_id") if pt.payload else None
            if pid and pid not in seen:
                seen.add(pid)
                unique_parent_ids.append(pid)

        if not unique_parent_ids:
            return None

        parent_docs_raw = store.mget(unique_parent_ids)
        valid_parents = [(pid, pdoc) for pid, pdoc in zip(unique_parent_ids, parent_docs_raw) if pdoc]

        if not valid_parents:
            return None

        # Rerank các parent chunks
        pairs = [[task_query, pdoc.page_content] for _, pdoc in valid_parents]
        reranker = get_reranker()
        scores = reranker.predict(pairs)

        best_idx = 0
        best_score = scores[0] if scores else 0.0
        for i, sc in enumerate(scores):
            if sc > best_score:
                best_score = sc
                best_idx = i

        best_doc = valid_parents[best_idx][1]
        return {
            "source": best_doc.metadata.get("file_path", "cach_dung_app.md"),
            "score": round(float(best_score), 4),
            "content": best_doc.page_content
        }
    except Exception as e:
        print(f"[retrieve_app_guide_chunk_from_db Error] {e}")
        return None


def fallback_read_guide_chunk(task_query: str) -> Optional[Dict[str, Any]]:
    """Đọc trực tiếp từ file docs/cach_dung_app.md nếu database chưa sẵn sàng."""
    for filename in ["cach_dung_app.md", "cach_dung_ap.md"]:
        path = os.path.join(DOCS_DIR, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # Chia thành các section tác vụ
            sections = re.split(r'\n(?=##\s*Tác vụ:)', content)
            q = task_query.lower()
            for sec in sections:
                if not sec.strip().startswith("## Tác vụ:"):
                    continue
                sec_lower = sec.lower()
                if "data" in q and ("data" in sec_lower or "4g/5g" in sec_lower):
                    return {"source": filename, "score": 1.0, "content": sec.strip()}
                if ("nạp" in q or "topup" in q) and ("nạp tiền" in sec_lower or "top-up" in sec_lower):
                    return {"source": filename, "score": 1.0, "content": sec.strip()}
                if ("lịch sử" in q or "sao kê" in q or "thống kê" in q) and "lịch sử" in sec_lower:
                    return {"source": filename, "score": 1.0, "content": sec.strip()}
            if len(sections) > 1:
                return {"source": filename, "score": 0.8, "content": sections[1].strip()}
    return None


def execute_guide_app_task(
    task_query: str,
    current_screen: Optional[str] = None,
    dense_model=None,
    sparse_model=None,
    client=None,
    store=None
) -> str:
    """
    Thực thi nạp sơ đồ điều hướng navigation_map.json, truy vấn chunk hướng dẫn từ cach_dung_ap.md,
    và tổng hợp lộ trình điều hướng kèm các bước thao tác trên màn hình đích.
    """
    # 1. Nạp navigation_map.json
    nav_map = load_navigation_map()
    screens = nav_map.get("screens", {})
    global_nav = nav_map.get("global_navigation", {})

    # 2. Truy vấn chunk phù hợp từ database
    guide_chunk = retrieve_app_guide_chunk_from_db(
        task_query=task_query,
        dense_model=dense_model,
        sparse_model=sparse_model,
        client=client,
        store=store
    )
    if guide_chunk is None:
        guide_chunk = fallback_read_guide_chunk(task_query)

    if not guide_chunk:
        return "Không tìm thấy tài liệu hướng dẫn cho tác vụ này trong cơ sở dữ liệu."

    chunk_content = guide_chunk["content"]

    # 3. Trích xuất required_screen_id từ chunk (hoặc match data-driven từ navigation_map)
    screen_match = re.search(r'required_screen_id`?\)?:\s*`?([A-Z0-9_]+)`?', chunk_content)
    if screen_match:
        required_screen_id = screen_match.group(1)
    else:
        required_screen_id = resolve_screen_id(None, screens, fallback_text=chunk_content)

    # 4. Xác định màn hình hiện tại (current_screen) từ input hoặc task_query
    current_screen_id = resolve_screen_id(current_screen, screens, fallback_text=task_query)

    # Nếu current_screen_id bị gán trùng với required_screen_id nhưng ngữ cảnh nhắc tới Trang chủ / HOME
    if current_screen_id == required_screen_id and current_screen_id != "HOME":
        q_lower = (task_query or "").lower()
        if "trang chủ" in q_lower or "trang chu" in q_lower or "màn hình chính" in q_lower or "home" in q_lower:
            current_screen_id = "HOME"

    target_screen_info = screens.get(required_screen_id, {})
    current_screen_info = screens.get(current_screen_id, {})

    target_title = target_screen_info.get("title", required_screen_id)
    current_title = current_screen_info.get("title", current_screen_id)

    # 5. Xây dựng lộ trình điều hướng hoàn toàn từ navigation_map.json
    nav_steps = build_navigation_path(
        current_screen_id=current_screen_id,
        target_screen_id=required_screen_id,
        screens=screens,
        global_nav=global_nav
    )
    navigation_instruction = "\n".join(nav_steps)

    output = f"""=== KẾT QUẢ ĐIỀU HƯỚNG VÀ HƯỚNG DẪN TÁC VỤ APP ===
- Nguồn trích xuất: {guide_chunk.get('source', 'cach_dung_app.md')} (Score: {guide_chunk.get('score', 1.0)})
- Màn hình hiện tại: {current_screen_id} ({current_title})
- Màn hình thực hiện tác vụ: {required_screen_id} ({target_title})

[LỘ TRÌNH ĐIỀU HƯỚNG MÀN HÌNH]:
{navigation_instruction}

[HƯỚNG DẪN CHI TIẾT TỪ TÀI LIỆU]:
{chunk_content}
"""
    return output.strip()
    return output.strip()
