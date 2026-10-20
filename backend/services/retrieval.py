import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria
from qdrant_client import models
from langchain_huggingface import HuggingFaceEndpointEmbeddings
import backend.core.env

def get_dense_embedding_model(token: str | None = None, model: str | None = None) -> HuggingFaceEndpointEmbeddings:
    hf_token = token or os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
    model_name = model or os.getenv("HF_EMBEDDING_MODEL", "google/embeddinggemma-300m")
    if not hf_token:
        raise ValueError("Chưa cấu hình HF_API_KEY hoặc HF_TOKEN trong biến môi trường hoặc file .env.")
    dense_model = HuggingFaceEndpointEmbeddings(
        model=model_name,
        huggingfacehub_api_token=hf_token
    )
    # Warmup để kiểm tra kết nối API
    dense_model.embed_query("warmup")
    return dense_model

class JevReranker:
    def __init__(self, api_key: str | None = None, model: str | None = None, max_workers: int = 10):
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY")
        self.model = model or os.getenv("RERANKER_MODEL", "jev-latest")
        self.max_workers = max_workers
        self.client = TypeSafeClient(api_key=self.api_key, timeout=30.0) if self.api_key else None
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

        if not self.client:
            raise ValueError(
                "Chưa cấu hình TYPESAFE_API_KEY. Vui lòng thiết lập biến môi trường TYPESAFE_API_KEY hoặc thêm vào file .env."
            )

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
                print(f"[JevReranker Error] {e}")
                raise e

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(pairs))) as pool:
            scores = list(pool.map(score_pair, pairs))
        return scores

reranker = None

def get_reranker():
    global reranker
    if reranker is None:
        reranker = JevReranker()
    return reranker

def search_and_rerank(query: str, dense_model, sparse_model, client, store, collection_name: str, score_threshold: float = 0.6, top_k: int | None = None):
    # Embed query
    query_dense_vec = dense_model.embed_query(query)
    query_sparse_res = list(sparse_model.embed([query]))[0]
    
    # Qdrant Hybrid Search
    results = client.query_points(
        collection_name=collection_name,
        prefetch=[
            models.Prefetch(
                query=query_dense_vec,
                using="dense",
                limit=20,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=query_sparse_res.indices.tolist(),
                    values=query_sparse_res.values.tolist()
                ),
                using="sparse",
                limit=20,
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
    
    scored_parents = []
    for (pid, pdoc), score in zip(valid_parents, rerank_scores):
        scored_parents.append({
            "parent_id": pid,
            "score": score,
            "source": os.path.basename(pdoc.metadata.get('file_path', 'Unknown')),
            "page": pdoc.metadata.get('page_number', 'Unknown'),
            "is_toc": pdoc.metadata.get('is_toc', False),
            "content": pdoc.page_content
        })
    scored_parents.sort(key=lambda x: x["score"], reverse=True)
    
    with open("debug_retrieval.log", "a", encoding="utf-8") as f_deb:
        f_deb.write(f"\n========================================\n")
        f_deb.write(f"Query: '{query}' | Qdrant child points: {len(results.points)} | Unique parent chunks: {len(scored_parents)}\n")
        for rank, item in enumerate(scored_parents, 1):
            txt_preview = item["content"].replace("\n", " ")[:120]
            f_deb.write(f"  Rank {rank}: score={item['score']:.4f} | Source: {item['source']} | Content: {txt_preview}\n")
    
    # Lọc theo ngưỡng score và lấy tối đa top_k parent documents
    retrieved_parents = []
    for item in scored_parents:
        if item["score"] < score_threshold:
            break
        retrieved_parents.append(item)
        if top_k is not None and len(retrieved_parents) >= top_k:
            break
            
    with open("debug_retrieval.log", "a", encoding="utf-8") as f_deb:
        f_deb.write(f"-> Retrieved parents count (threshold >= {score_threshold}): {len(retrieved_parents)}\n")
    return retrieved_parents
