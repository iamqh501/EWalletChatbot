import os
import time
import json
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI
from qdrant_client import QdrantClient
from fastembed import SparseTextEmbedding
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

from backend.core.config import QDRANT_PATH, STORE_PATH
from backend.services.retrieval import get_dense_embedding_model, get_reranker
from backend.services.llm import get_llm_model


class AppState:
    dense_model = None
    sparse_model = None
    qdrant_client = None
    store = None
    llm = None
    load_task: Optional[asyncio.Task] = None

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


class SessionManager:
    def __init__(self):
        self.histories: Dict[str, List[Any]] = {}
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.relevance_matrices: Dict[str, Dict[Tuple[int, int], float]] = {}

    def ensure_session(self, session_id: str):
        if session_id not in self.histories:
            self.histories[session_id] = []
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        if session_id not in self.relevance_matrices:
            self.relevance_matrices[session_id] = {}

    def get_recent_turns(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        self.ensure_session(session_id)
        return self.conversations[session_id][-limit:]

    def get_relevance_matrix(self, session_id: str) -> Dict[Tuple[int, int], float]:
        self.ensure_session(session_id)
        return self.relevance_matrices[session_id]

    def save_turn(
        self,
        session_id: str,
        user_query: str,
        agent_output: str,
        tool_output: str,
        scored_messages: List[Dict[str, Any]]
    ):
        self.ensure_session(session_id)
        past_turns = self.conversations[session_id]
        r_matrix = self.relevance_matrices[session_id]

        new_turn_id = len(past_turns) + 1

        # Lưu lại u_i làm r_ij cho các query sau (đối xứng)
        for item in scored_messages:
            past_id = item["turn_id"]
            u_score = item["u_i"]
            r_matrix[(new_turn_id, past_id)] = u_score
            r_matrix[(past_id, new_turn_id)] = u_score

        past_turns.append({
            "id": new_turn_id,
            "user_query": user_query,
            "tool_output": tool_output,
            "agent_output": agent_output
        })

        self.histories[session_id].append(HumanMessage(content=user_query))
        self.histories[session_id].append(AIMessage(content=agent_output))


session_manager = SessionManager()


async def load_models_background():
    print("Loading AI Models into memory...")
    try:
        dense_model_name = os.getenv("HF_EMBEDDING_MODEL", "google/embeddinggemma-300m")
        notify_init_step(f"Loading Dense Embedding ({dense_model_name})...")
        app_state.dense_model = await asyncio.to_thread(get_dense_embedding_model)
        notify_component_loaded(f"Dense Embedding: {dense_model_name}")

        sparse_model_name = "Qdrant/bm25"
        notify_init_step(f"Loading Sparse Embedding ({sparse_model_name})...")
        app_state.sparse_model = await asyncio.to_thread(
            SparseTextEmbedding,
            model_name=sparse_model_name
        )
        notify_component_loaded(f"Sparse Embedding: {sparse_model_name}")

        reranker = get_reranker()
        reranker_model_name = getattr(reranker, "model", None) or os.getenv("RERANKER_MODEL", "jev-latest")
        notify_init_step(f"Loading Reranker ({reranker_model_name})...")
        notify_component_loaded(f"Reranker: {reranker_model_name}")

        llm_model_name = os.getenv("HF_MODEL_NAME", "inclusionAI/Ling-3.0-flash:fastest")
        notify_init_step(f"Connecting LLM ({llm_model_name})...")
        if not hasattr(app_state, "llm") or app_state.llm is None:
            app_state.llm = await asyncio.to_thread(get_llm_model)

        notify_component_loaded(f"LLM: {llm_model_name}")

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

    app_state.load_task = asyncio.create_task(load_models_background())
    print(f"Hệ thống khởi động HTTP server hoàn tất trong {time.time() - t0_start:.2f}s. Đang nạp mô hình AI dưới nền...")

    yield

    if app_state.qdrant_client:
        app_state.qdrant_client.close()
