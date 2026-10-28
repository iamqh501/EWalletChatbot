import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria
from qdrant_client import models
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from backend.core.config import COLLECTION_NAME, EMBEDDING_MODEL, RERANKER_MODEL
from backend.tools.schemas import SearchResultItem


def get_dense_embedding_model() -> HuggingFaceEndpointEmbeddings:
    dense_model = HuggingFaceEndpointEmbeddings(model=EMBEDDING_MODEL)
    # Warmup để kiểm tra kết nối API
    dense_model.embed_query("warmup")
    return dense_model


class JevReranker:
    def __init__(self, max_workers: int = 10):
        self.model = RERANKER_MODEL
        self.max_workers = max_workers
        self.client = TypeSafeClient(timeout=30.0)
        self.question = Noul(
            instructions=(
                "Đoạn trích thông tin này có trả lời hoặc cung cấp thông tin liên quan trực tiếp cho câu hỏi của người dùng không?"
            ),
            criteria=NoulCriteria(
                true="Đoạn trích chứa thông tin trực tiếp giải đáp hoặc cung cấp ngữ cảnh cần thiết cho câu hỏi.",
                false="Đoạn trích không liên quan hoặc chỉ đề cập đến chủ đề khác.",
            ),
        )

    def predict(self, pairs: list[list[str]]) -> list[float]:
        if not pairs:
            return []

        def score_pair(pair):
            query, passage = pair
            try:
                response = self.client.system_one(
                    state={"query": query, "candidate_passage": passage},
                    questions={"is_relevant": self.question},
                    model=self.model,
                )
                return float(response.nouls["is_relevant"].noul)
            except Exception as e:
                logger.error("JevReranker error: %s", e)
                raise e

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(pairs))) as pool:
            scores = list(pool.map(score_pair, pairs))
        return scores


reranker = None

logger = logging.getLogger(__name__)


def get_reranker():
    global reranker
    if reranker is None:
        reranker = JevReranker()
    return reranker


def search_and_rerank(
    query: str,
    dense_model,
    sparse_model,
    client,
    store,
    collection_name: str = COLLECTION_NAME,
    score_threshold: float = 0.6,
    top_k: int | None = None,
    filter: models.Filter | None = None
) -> list[SearchResultItem]:
    # Embed query song song (Dense API + Sparse local)
    with ThreadPoolExecutor(max_workers=2) as pool:
        dense_future = pool.submit(dense_model.embed_query, query)
        sparse_future = pool.submit(lambda q: list(sparse_model.embed([q]))[0], query)
        query_dense_vec = dense_future.result()
        query_sparse_res = sparse_future.result()

    # Qdrant Hybrid Search
    results = client.query_points(
        collection_name=collection_name,
        prefetch=[
            models.Prefetch(
                query=query_dense_vec,
                using="dense",
                limit=20,
                filter=filter,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=query_sparse_res.indices.tolist(),
                    values=query_sparse_res.values.tolist()
                ),
                using="sparse",
                limit=20,
                filter=filter,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=20,
        with_payload=True,
    )

    # Trích xuất và loại trùng parent_ids từ kết quả Qdrant (giữ thứ tự ưu tiên của Hybrid Search)
    unique_parent_ids = []
    seen_parent_ids = set()
    for point in results.points:
        metadata = point.payload.get("metadata", {}) if point.payload else {}
        pid = metadata.get("doc_id")
        if pid and pid not in seen_parent_ids:
            seen_parent_ids.add(pid)
            unique_parent_ids.append(pid)

    # Lấy parent documents từ store
    parent_docs_raw = store.mget(unique_parent_ids)
    valid_parents = []
    for pid, pdoc in zip(unique_parent_ids, parent_docs_raw):
        if pdoc:
            valid_parents.append((pid, pdoc))

    if not valid_parents:
        return []

    # Reranking trực tiếp trên Parent Chunks
    pairs = [[query, pdoc.page_content] for _, pdoc in valid_parents]
    reranker_model = get_reranker()
    rerank_scores = reranker_model.predict(pairs)

    scored_parents: list[SearchResultItem] = []
    for (pid, pdoc), score in zip(valid_parents, rerank_scores):
        scored_parents.append(SearchResultItem(
            parent_id=pid,
            score=float(score),
            source=os.path.basename(pdoc.metadata.get('file_path', 'Unknown')),
            content=pdoc.page_content,
            metadata=pdoc.metadata or {}
        ))
    scored_parents.sort(key=lambda x: x.score, reverse=True)

    logger.debug(
        "Query: '%s' | Qdrant child points: %d | Unique parent chunks: %d\n%s",
        query, len(results.points), len(scored_parents),
        "\n".join(
            f"  Rank {rank}: score={item.score:.4f} | Source: {item.source} | Content: {item.content.replace(chr(10), ' ')[:120]}"
            for rank, item in enumerate(scored_parents, 1)
        )
    )

    # Lọc theo ngưỡng score và lấy tối đa top_k parent documents
    retrieved_parents: list[SearchResultItem] = []
    for item in scored_parents:
        if item.score < score_threshold:
            break
        retrieved_parents.append(item)
        if top_k is not None and len(retrieved_parents) >= top_k:
            break

    logger.debug("-> Retrieved parents count (threshold >= %s): %d", score_threshold, len(retrieved_parents))
    return retrieved_parents
