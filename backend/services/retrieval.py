import os
from sentence_transformers import CrossEncoder
from qdrant_client import models

reranker = None

def get_reranker():
    global reranker
    if reranker is None:
        reranker = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", device="cpu")
    return reranker

def search_and_rerank(query: str, dense_model, sparse_model, client, store, collection_name: str):
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
    
    # Reranking
    pairs = [[query, str(point.payload.get("page_content", ""))] for point in results.points]
    reranker_model = get_reranker()
    rerank_scores = reranker_model.predict(pairs)
    
    reranked_results = [(results.points[i], rerank_scores[i]) for i in range(len(results.points))]
    reranked_results.sort(key=lambda x: x[1], reverse=True)
    
    # Deduplicate and get parents
    seen_parent_ids = set()
    retrieved_parents = []
    
    for point, final_score in reranked_results:
        metadata = point.payload.get("metadata", {}) if point.payload else {}
        parent_id = metadata.get("doc_id")
        
        if parent_id and parent_id not in seen_parent_ids:
            seen_parent_ids.add(parent_id)
            parent_doc_list = store.mget([parent_id])
            if parent_doc_list and parent_doc_list[0]:
                parent_doc = parent_doc_list[0]
                retrieved_parents.append({
                    "parent_id": parent_id,
                    "score": final_score,
                    "source": os.path.basename(parent_doc.metadata.get('file_path', 'Unknown')),
                    "page": parent_doc.metadata.get('page_number', 'Unknown'),
                    "is_toc": parent_doc.metadata.get('is_toc', False),
                    "content": parent_doc.page_content
                })
                
            if len(retrieved_parents) >= 5:
                break
                
    return retrieved_parents
