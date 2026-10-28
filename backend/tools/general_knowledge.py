from typing import List
from backend.core.config import COLLECTION_NAME
from backend.services.retrieval import search_and_rerank
from backend.tools.schemas import KnowledgeChunk, ToolResultItem


def format_chunks_summary_for_thinking(chunks: List[KnowledgeChunk]) -> str:
    """Format tóm tắt output của tool search_general_knowledge cho khối thinking."""
    if not chunks:
        return "Tổng số chunk: 0\n(Không tìm thấy thông tin chung nào.)"

    lines = [f"Tổng số chunk: {len(chunks)}"]
    for i, chunk in enumerate(chunks, 1):
        content_lines = [l.strip() for l in chunk.content.strip().split("\n") if l.strip()]
        first_two_lines = "\n".join(content_lines[:2]) if content_lines else ""
        lines.append(f"\n[Chunk {i} - Nguồn: {chunk.source} | Score: {chunk.score:.4f}]\n{first_two_lines}\n...")
    return "\n".join(lines)


def execute_search_general_knowledge(
    query: str,
    dense_model,
    sparse_model,
    client,
    store,
    collection_name: str = COLLECTION_NAME,
    max_context_chars: int = 60000
) -> ToolResultItem:
    """
    Thực hiện truy vấn Hybrid Search và Rerank tài liệu kiến thức ví điện tử,
    giới hạn tổng số ký tự an toàn (mặc định 60.000 ký tự) và đóng gói ToolResultItem.
    """
    results = search_and_rerank(
        query=query,
        dense_model=dense_model,
        sparse_model=sparse_model,
        client=client,
        store=store,
        collection_name=collection_name
    )

    chunks: List[KnowledgeChunk] = []
    total_len = 0
    for res in results:
        content = res.content
        if total_len + len(content) > max_context_chars:
            content = content[:max_context_chars - total_len] + "... (đã cắt bớt do quá dài)"
            chunks.append(KnowledgeChunk(
                source=res.source,
                score=round(float(res.score), 4),
                content=content
            ))
            break
        chunks.append(KnowledgeChunk(
            source=res.source,
            score=round(float(res.score), 4),
            content=content
        ))
        total_len += len(content)

    if not chunks:
        ctx_block = "Kết quả tra cứu kiến thức chung: Không tìm thấy tài liệu phù hợp."
    else:
        doc_texts = [f"[Tài liệu {i} - Nguồn: {ch.source}]\n{ch.content}" for i, ch in enumerate(chunks, 1)]
        ctx_block = "Kết quả tra cứu kiến thức chung:\n" + "\n\n".join(doc_texts)

    tool_summary = format_chunks_summary_for_thinking(chunks)
    tool_log = f"**[GỌI TOOL]**\n\n`search_general_knowledge(query=\"{query}\")`\n\n```\n{tool_summary}\n```\n"

    return ToolResultItem(
        tool="search_general_knowledge",
        context_block=ctx_block,
        tool_log=tool_log,
        data=chunks
    )
