import time
import json
import asyncio
import logging
from collections import OrderedDict
from typing import Optional, List, Dict, Any, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI
from qdrant_client import QdrantClient
from fastembed import SparseTextEmbedding
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from langchain_core.documents import Document
from backend.core.config import (
    QDRANT_PATH, STORE_PATH,
    EMBEDDING_MODEL, SPARSE_MODEL, RERANKER_MODEL,
    HF_LLM_MODEL, HF_VLM_MODEL
)
from backend.services.retrieval import get_dense_embedding_model, get_reranker
from backend.services.llm import get_llm_model, get_vlm_model
from backend.tools.schemas import ConversationTurn, TelecomPackage

logger = logging.getLogger(__name__)


class AppState:
    dense_model = None
    sparse_model = None
    qdrant_client = None
    store = None
    llm = None
    vlm = None
    load_task: Optional[asyncio.Task] = None

    # Init progress tracking
    is_ready: bool = False
    current_loading_step: str = "Starting server..."
    loaded_components: List[str] = []
    init_listeners: List[asyncio.Queue] = []

    # Cached static data
    telecom_packages: List[TelecomPackage] = []
    nav_map: dict = {}


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


class SessionManager:
    """Quản lý phiên hội thoại với giới hạn bộ nhớ LRU và dọn dẹp ma trận tương quan cũ."""

    def __init__(self, max_sessions: int = 500, max_turns_per_session: int = 50):
        self.max_sessions = max_sessions
        self.max_turns_per_session = max_turns_per_session
        self.conversations: OrderedDict[str, List[ConversationTurn]] = OrderedDict()
        self.relevance_matrices: Dict[str, Dict[Tuple[int, int], float]] = {}
        self.consents: Dict[str, bool] = {}

    def ensure_session(self, session_id: str):
        if session_id in self.conversations:
            self.conversations.move_to_end(session_id)
            return

        # Dọn dẹp session cũ nhất nếu vượt quá giới hạn
        if len(self.conversations) >= self.max_sessions:
            oldest_id, _ = self.conversations.popitem(last=False)
            self.relevance_matrices.pop(oldest_id, None)
            self.consents.pop(oldest_id, None)

        self.conversations[session_id] = []
        self.relevance_matrices[session_id] = {}
        self.consents[session_id] = False

    def get_consent(self, session_id: str) -> bool:
        self.ensure_session(session_id)
        return self.consents.get(session_id, False)

    def set_consent(self, session_id: str, consent: bool):
        self.ensure_session(session_id)
        self.consents[session_id] = bool(consent)

    def get_recent_turns(self, session_id: str, limit: int = 10) -> List[ConversationTurn]:
        self.ensure_session(session_id)
        return list(self.conversations[session_id][-limit:])

    def get_relevance_matrix(self, session_id: str) -> Dict[Tuple[int, int], float]:
        self.ensure_session(session_id)
        return dict(self.relevance_matrices[session_id])

    def save_turn(
        self,
        session_id: str,
        user_query: str,
        agent_output: str,
        scored_messages: List[Dict[str, Any]]
    ):
        self.ensure_session(session_id)
        past_turns = self.conversations[session_id]
        r_matrix = self.relevance_matrices[session_id]

        new_turn_id = (past_turns[-1].id + 1) if past_turns else 1

        # Lưu lại u_i làm r_ij cho các query sau (đối xứng)
        for item in scored_messages:
            past_id = item["turn_id"]
            u_score = item["u_i"]
            r_matrix[(new_turn_id, past_id)] = u_score
            r_matrix[(past_id, new_turn_id)] = u_score

        # Cắt tỉa các khóa quá cũ trong r_matrix để tránh rò rỉ RAM (chỉ giữ turn trong phạm vi 20 turn gần nhất)
        cutoff_id = new_turn_id - 20
        stale_keys = [k for k in r_matrix if k[0] < cutoff_id or k[1] < cutoff_id]
        for sk in stale_keys:
            r_matrix.pop(sk, None)

        past_turns.append(ConversationTurn(
            id=new_turn_id,
            user_query=user_query,
            agent_output=agent_output
        ))

        # Giữ số lượt hội thoại không vượt quá max_turns_per_session
        if len(past_turns) > self.max_turns_per_session:
            self.conversations[session_id] = past_turns[-self.max_turns_per_session:]


session_manager = SessionManager()


async def load_models_background():
    logger.info("Loading AI Models into memory...")
    try:
        notify_init_step(f"Loading Dense Embedding ({EMBEDDING_MODEL})...")
        app_state.dense_model = await asyncio.to_thread(get_dense_embedding_model)
        notify_component_loaded(f"Dense Embedding: {EMBEDDING_MODEL}")

        notify_init_step(f"Loading Sparse Embedding ({SPARSE_MODEL})...")
        app_state.sparse_model = await asyncio.to_thread(
            SparseTextEmbedding,
            model_name=SPARSE_MODEL
        )
        notify_component_loaded(f"Sparse Embedding: {SPARSE_MODEL}")

        get_reranker()
        notify_init_step(f"Loading Reranker ({RERANKER_MODEL})...")
        notify_component_loaded(f"Reranker: {RERANKER_MODEL}")

        notify_init_step(f"Connecting LLM ({HF_LLM_MODEL})...")
        if not hasattr(app_state, "llm") or app_state.llm is None:
            app_state.llm = await asyncio.to_thread(get_llm_model)

        notify_component_loaded(f"LLM: {HF_LLM_MODEL}")

        notify_init_step(f"Connecting VLM ({HF_VLM_MODEL})...")
        if not hasattr(app_state, "vlm") or app_state.vlm is None:
            app_state.vlm = await asyncio.to_thread(get_vlm_model)

        notify_component_loaded(f"VLM: {HF_VLM_MODEL}")

        notify_init_complete()
        logger.info("All models loaded successfully!")
    except Exception as e:
        import traceback
        logger.error("CRITICAL ERROR: Failed to load models: %s\n%s", e, traceback.format_exc())
        notify_init_error(str(e))
        raise e


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0_start = time.time()
    notify_init_step("Connecting Knowledge Base...")
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
    notify_component_loaded("Knowledge Base: Qdrant")

    # Cache dữ liệu tĩnh vào app_state
    try:
        from backend.tools.telecom_packages import load_package_data
        from backend.tools.app_navigation import load_navigation_map
        app_state.telecom_packages = load_package_data()
        app_state.nav_map = load_navigation_map()
    except Exception as e:
        logger.warning("Failed to pre-cache telecom/nav data: %s", e)

    app_state.load_task = asyncio.create_task(load_models_background())
    logger.info("Hệ thống khởi động HTTP server hoàn tất trong %.2fs. Đang nạp mô hình AI dưới nền...", time.time() - t0_start)

    yield

    if app_state.qdrant_client:
        app_state.qdrant_client.close()
