from typing import List, Dict, Any
from backend.services.retrieval import search_and_rerank


def execute_search_general_knowledge(
    query: str,
    dense_model,
    sparse_model,
    client,
    store,
    collection_name: str = "knowledge",
    max_context_chars: int = 60000
) -> List[Dict[str, Any]]:
    """
    Thực hiện truy vấn Hybrid Search và Rerank tài liệu kiến thức ví điện tử.
    Đảm bảo giới hạn tổng số ký tự an toàn (mặc định 60.000 ký tự).
    """
    results = search_and_rerank(
        query=query,
        dense_model=dense_model,
        sparse_model=sparse_model,
        client=client,
        store=store,
        collection_name=collection_name
    )

    chunks = []
    total_len = 0
    for res in results:
        content = res["content"]
        if total_len + len(content) > max_context_chars:
            content = content[:max_context_chars - total_len] + "... (đã cắt bớt do quá dài)"
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


def format_chunks_summary_for_thinking(chunks: List[Dict[str, Any]]) -> str:
    """Format tóm tắt output của tool search_general_knowledge cho khối thinking."""
    if not chunks:
        return "Tổng số chunk: 0\n(Không tìm thấy thông tin chung nào.)"

    lines = [f"Tổng số chunk: {len(chunks)}"]
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "Unknown")
        score = chunk.get("score", 0.0)
        content = chunk.get("content", "").strip()
        content_lines = [l.strip() for l in content.split("\n") if l.strip()]
        first_two_lines = "\n".join(content_lines[:2]) if content_lines else ""
        lines.append(f"\n[Chunk {i} - Nguồn: {source} | Score: {score:.4f}]\n{first_two_lines}\n...")
    return "\n".join(lines)
