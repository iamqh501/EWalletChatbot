import os
import sys
import time
import uuid
import shutil
import json
import hashlib
import re
import argparse
import pandas as pd

# Ép kiểu encoding của sys.stdout sang utf-8 để tránh lỗi khi in tiếng Việt trên CMD Windows (Rule 8)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from qdrant_client import QdrantClient, models
from langchain_core.documents import Document
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from fastembed import SparseTextEmbedding
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from backend.services.retrieval import get_dense_embedding_model

from backend.core.config import QDRANT_PATH, STORE_PATH, DOCS_DIR, STATE_FILE

COLLECTION_NAME = "knowledge"


def is_indexable_doc(filename: str) -> bool:
    """
    Kiểm tra file có hợp lệ để index vào database không.
    Không bao gồm file excel (.xlsx, .xls), file json (.json) và file state.
    Chỉ index các tài liệu Markdown (.md).
    """
    lower = filename.lower()
    if lower == os.path.basename(STATE_FILE).lower() or lower == "file_state.json":
        return False
    if lower.endswith((".xlsx", ".xls", ".json")):
        return False
    return lower.endswith(".md")


def get_file_hash(filepath: str) -> str:
    """Tính mã MD5 hash của file để theo dõi sự thay đổi nội dung."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_state() -> dict:
    """Đọc file state lưu thông tin hash và id các chunk đã index."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            return json.loads(content)
        except Exception as e:
            print(f"Cảnh báo: Không thể đọc file state ({e}), bắt đầu với state rỗng.")
    return {}


def save_state(state: dict):
    """Lưu state vào file (tuân thủ Rule 14: gom dữ liệu vào biến trước khi mở file 'w')."""
    content = json.dumps(state, ensure_ascii=False, indent=2)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def split_markdown_documents_with_tables(docs, max_rows=10):
    """Tách các bảng Markdown dài thành các document nhỏ giữ nguyên header để tránh đứt gãy bảng."""
    new_docs = []
    for doc in docs:
        lines = doc.page_content.split("\n")
        i = 0
        current_text = []
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("|") and line.endswith("|") and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("|") and next_line.endswith("|") and re.match(r'^\|[\s\-\|:]+\|$', next_line):
                    if current_text:
                        text = "\n".join(current_text).strip()
                        if text:
                            new_docs.append(Document(page_content=text, metadata=doc.metadata))
                        current_text = []

                    header = lines[i]
                    separator = lines[i + 1]
                    i += 2
                    rows = []
                    while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                        rows.append(lines[i])
                        i += 1

                    for j in range(0, len(rows), max_rows):
                        chunk_rows = rows[j:j + max_rows]
                        table_chunk = [header, separator] + chunk_rows
                        new_docs.append(Document(page_content="\n".join(table_chunk), metadata=doc.metadata))
                    continue
            current_text.append(lines[i])
            i += 1

        if current_text:
            text = "\n".join(current_text).strip()
            if text:
                new_docs.append(Document(page_content=text, metadata=doc.metadata))
    return new_docs


def init_splitters():
    """Khởi tạo các bộ chia tài liệu Markdown."""
    headers_to_split_on = [
        ("#", "H1"),
        ("##", "H2"),
        ("###", "H3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=200)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    return markdown_splitter, parent_splitter, child_splitter


def init_embeddings():
    """Khởi tạo mô hình dense (google/embeddinggemma-300m qua Hugging Face) và sparse embedding."""
    print("Khởi tạo Embeddings...")
    dense_model = get_dense_embedding_model()
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return dense_model, sparse_model


def init_store():
    """Khởi tạo LocalFileStore và EncoderBackedStore lưu trữ parent documents."""
    fs = LocalFileStore(STORE_PATH)
    store = EncoderBackedStore(
        store=fs,
        key_encoder=lambda x: x,
        value_serializer=lambda doc: json.dumps(doc.model_dump()).encode("utf-8"),
        value_deserializer=lambda bytes_data: Document(**json.loads(bytes_data.decode("utf-8")))
    )
    return store


def index_single_file(filename: str, client: QdrantClient, store, dense_model, sparse_model, markdown_splitter, parent_splitter, child_splitter, chunks_dir: str | None = None):
    """Xử lý và index một file markdown cụ thể vào Qdrant và LocalFileStore.

    Args:
        chunks_dir: Nếu được chỉ định, xuất file log chunk vào thư mục này.
    """
    filepath = os.path.join(DOCS_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Tách văn bản theo Header trước
    md_docs = markdown_splitter.split_text(content)

    # 2. Tách các bảng dài ra thành các Document riêng biệt để không bị dính chunk_overlap
    md_docs = split_markdown_documents_with_tables(md_docs, max_rows=10)

    # 3. Đảm bảo các đoạn text thường (không phải bảng) không vượt quá max length
    parent_chunks = parent_splitter.split_documents(md_docs)

    parent_docs = []
    chunk_texts = []   # Lưu tạm để ghi file (nếu cần)
    for idx, doc in enumerate(parent_chunks, 1):
        headers = []
        for h in ["H1", "H2", "H3"]:
            if h in doc.metadata:
                headers.append(doc.metadata[h])

        heading_context = " > ".join(headers)
        raw_text = f"[{heading_context}]\n\n{doc.page_content}" if heading_context else doc.page_content
        parent_docs.append(Document(
            page_content=raw_text,
            metadata={"file_path": filename}
        ))
        chunk_texts.append((idx, raw_text))

    # Xuất file chunk log nếu có chỉ định thư mục
    if chunks_dir:
        os.makedirs(chunks_dir, exist_ok=True)
        chunk_file_path = os.path.join(chunks_dir, filename)
        lines = []
        for idx, raw_text in chunk_texts:
            lines.append(f"[Start chunk {idx}]\n{raw_text}\n[End chunk {idx}]\n")
        chunk_content = "\n".join(lines)
        with open(chunk_file_path, "w", encoding="utf-8") as f_chunk:
            f_chunk.write(chunk_content)
        print(f"   -> Đã xuất {len(chunk_texts)} chunks ra '{chunk_file_path}'.")

    doc_ids = [str(uuid.uuid4()) for _ in parent_docs]

    # Thu thập tất cả child chunks cần embed
    child_items = []
    for i, parent_doc in enumerate(parent_docs):
        _id = doc_ids[i]
        _sub_docs = child_splitter.split_documents([parent_doc])
        for _doc in _sub_docs:
            child_items.append((_id, _doc.page_content))

    if not child_items:
        if doc_ids:
            store.mset(list(zip(doc_ids, parent_docs)))
        return doc_ids, []

    all_texts = [item[1] for item in child_items]

    # Batch embedding qua Hugging Face Endpoint API cho dense_model
    dense_vectors = []
    batch_size = 32
    for b_idx in range(0, len(all_texts), batch_size):
        batch = all_texts[b_idx:b_idx + batch_size]
        for attempt in range(3):
            try:
                vectors = dense_model.embed_documents(batch)
                dense_vectors.extend(vectors)
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2 ** attempt)

    # Sparse embedding qua FastEmbed
    sparse_results = list(sparse_model.embed(all_texts))

    points = []
    point_ids = []
    for (pid, text), dense_vec, sparse_res in zip(child_items, dense_vectors, sparse_results):
        child_id = str(uuid.uuid4())
        points.append(
            models.PointStruct(
                id=child_id,
                payload={"page_content": text, "metadata": {"doc_id": pid, "file_path": filename}},
                vector={
                    "dense": dense_vec,
                    "sparse": models.SparseVector(
                        indices=sparse_res.indices.tolist(),
                        values=sparse_res.values.tolist()
                    )
                }
            )
        )
        point_ids.append(child_id)

    if points:
        client.upload_points(collection_name=COLLECTION_NAME, points=points)
        print(f"   -> Đã upload {len(points)} child chunks lên Qdrant.")
    if doc_ids:
        store.mset(list(zip(doc_ids, parent_docs)))
        print(f"   -> Đã lưu {len(doc_ids)} parent docs vào LocalFileStore.")

    return doc_ids, point_ids


def delete_file_from_index(filename: str, file_info: dict, client: QdrantClient, store):
    """Xóa toàn bộ parent docs và vector points thuộc về một file khỏi database."""
    doc_ids = file_info.get("doc_ids", [])
    point_ids = file_info.get("point_ids", [])

    # 1. Xóa parent docs khỏi store
    if doc_ids:
        try:
            store.mdelete(doc_ids)
        except Exception as e:
            print(f"   Lỗi khi xóa parent docs cho {filename}: {e}")

    # 2. Xóa points khỏi Qdrant theo danh sách point_ids
    if point_ids:
        try:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=point_ids)
            )
        except Exception as e:
            print(f"   Lỗi khi xóa points theo ID cho {filename}: {e}")

    # 3. Dự phòng: Xóa theo FilterSelector key metadata.file_path
    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.file_path",
                            match=models.MatchValue(value=filename)
                        )
                    ]
                )
            )
        )
    except Exception:
        pass


def run_reset(chunks_dir: str | None = None):
    """Chế độ 1: Xóa database index lại từ đầu (không bao gồm file excel, json)."""
    print("=" * 60)
    print("[CHẾ ĐỘ RESET] Xóa database cũ và index lại toàn bộ từ đầu")
    print("=" * 60)

    # 1. Dọn dẹp dữ liệu cũ và file state
    print("Xóa dữ liệu cũ...")
    if os.path.exists(QDRANT_PATH):
        shutil.rmtree(QDRANT_PATH, ignore_errors=True)
    if os.path.exists(STORE_PATH):
        shutil.rmtree(STORE_PATH, ignore_errors=True)
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except Exception:
            pass

    os.makedirs(QDRANT_PATH, exist_ok=True)
    os.makedirs(STORE_PATH, exist_ok=True)

    print("Khởi tạo Qdrant Client...")
    client = QdrantClient(path=QDRANT_PATH)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={"dense": models.VectorParams(size=768, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)}
    )

    store = init_store()
    dense_model, sparse_model = init_embeddings()
    markdown_splitter, parent_splitter, child_splitter = init_splitters()

    # 2. Lấy danh sách files tài liệu hợp lệ (loại trừ Excel, JSON)
    all_files = [f for f in os.listdir(DOCS_DIR) if is_indexable_doc(f)]
    print(f"Tìm thấy {len(all_files)} tài liệu Markdown hợp lệ để index (không bao gồm Excel, JSON).\n")

    new_state = {}
    for idx, filename in enumerate(all_files, 1):
        filepath = os.path.join(DOCS_DIR, filename)
        print(f"[{idx}/{len(all_files)}] Đang xử lý {filename}...")
        doc_ids, point_ids = index_single_file(
            filename, client, store, dense_model, sparse_model,
            markdown_splitter, parent_splitter, child_splitter,
            chunks_dir=chunks_dir
        )
        new_state[filename] = {
            "hash": get_file_hash(filepath),
            "doc_ids": doc_ids,
            "point_ids": point_ids,
            "indexed_at": time.time()
        }

    save_state(new_state)
    client.close()
    print("\n" + "=" * 60)
    print(f"Hoàn tất Reset & Index! Đã index thành công {len(all_files)} files vào database.")
    print("=" * 60)


def run_update(chunks_dir: str | None = None):
    """Chế độ 2: Update database dựa trên các file đã thay đổi nội dung từ lần cuối (thêm, sửa, xoá)."""
    print("=" * 60)
    print("[CHẾ ĐỘ UPDATE] Cập nhật database dựa trên các file đã thay đổi")
    print("=" * 60)

    state = load_state()
    if not os.path.exists(QDRANT_PATH) or not state:
        print("Chưa tìm thấy database hoặc trạng thái index trước đó. Tự động chuyển sang index lại từ đầu...")
        run_reset(chunks_dir=chunks_dir)
        return

    # Quét danh sách file hiện tại trong docs (bỏ qua excel, json)
    current_files = {f: get_file_hash(os.path.join(DOCS_DIR, f)) for f in os.listdir(DOCS_DIR) if is_indexable_doc(f)}
    saved_files = set(state.keys())

    added_files = [f for f in current_files if f not in saved_files]
    deleted_files = [f for f in saved_files if f not in current_files]
    modified_files = [f for f in current_files if f in saved_files and current_files[f] != state[f].get("hash")]

    total_changes = len(added_files) + len(modified_files) + len(deleted_files)
    if total_changes == 0:
        print("Không có file nào thay đổi (thêm, sửa, xóa). Database đã ở trạng thái mới nhất!")
        return

    print(f"Phát hiện {total_changes} thay đổi:")
    if added_files:
        print(f" - Thêm mới ({len(added_files)}): {', '.join(added_files)}")
    if modified_files:
        print(f" - Chỉnh sửa ({len(modified_files)}): {', '.join(modified_files)}")
    if deleted_files:
        print(f" - Đã xóa   ({len(deleted_files)}): {', '.join(deleted_files)}")
    print()

    client = QdrantClient(path=QDRANT_PATH)
    store = init_store()

    # 1. Xử lý các file bị xóa
    for filename in deleted_files:
        print(f"-> Đang xóa dữ liệu của: {filename}...")
        delete_file_from_index(filename, state[filename], client, store)
        del state[filename]

    # 2. Xử lý các file được chỉnh sửa hoặc thêm mới
    if added_files or modified_files:
        dense_model, sparse_model = init_embeddings()
        markdown_splitter, parent_splitter, child_splitter = init_splitters()

        # Chỉnh sửa
        for filename in modified_files:
            print(f"-> Đang cập nhật lại file: {filename}...")
            delete_file_from_index(filename, state[filename], client, store)
            filepath = os.path.join(DOCS_DIR, filename)
            doc_ids, point_ids = index_single_file(
                filename, client, store, dense_model, sparse_model,
                markdown_splitter, parent_splitter, child_splitter,
                chunks_dir=chunks_dir
            )
            state[filename] = {
                "hash": current_files[filename],
                "doc_ids": doc_ids,
                "point_ids": point_ids,
                "updated_at": time.time()
            }

        # Thêm mới
        for filename in added_files:
            print(f"-> Đang index file mới: {filename}...")
            filepath = os.path.join(DOCS_DIR, filename)
            doc_ids, point_ids = index_single_file(
                filename, client, store, dense_model, sparse_model,
                markdown_splitter, parent_splitter, child_splitter,
                chunks_dir=chunks_dir
            )
            state[filename] = {
                "hash": current_files[filename],
                "doc_ids": doc_ids,
                "point_ids": point_ids,
                "indexed_at": time.time()
            }

    save_state(state)
    client.close()
    print("\n" + "=" * 60)
    print(f"Cập nhật hoàn tất! (Thêm: {len(added_files)}, Sửa: {len(modified_files)}, Xóa: {len(deleted_files)})")
    print("=" * 60)


def excel_to_json(excel_path: str = None, json_path: str = None):
    """Chế độ 3: Chuyển đổi nội dung Excel sang file JSON."""
    excel_path = excel_path or os.path.join(DOCS_DIR, "goi_cuoc.xlsx")
    json_path = json_path or os.path.join(DOCS_DIR, "goi_cuoc.json")

    print("=" * 60)
    print(f"[CHẾ ĐỘ CONVERT] Chuyển đổi từ '{excel_path}' sang '{json_path}'")
    print("=" * 60)

    if not os.path.exists(excel_path):
        print(f"Lỗi: Không tìm thấy file Excel tại '{excel_path}'")
        return

    try:
        # Đọc file Excel
        df = pd.read_excel(excel_path)

        # Thay thế các giá trị NaN (ô trống) thành chuỗi rỗng
        df = df.fillna("")

        json_data = []
        for index, row in df.iterrows():
            metadata = {}

            # Quét tất cả các cột tự động dựa theo file Excel
            for col in df.columns:
                val = row[col]

                # Xử lý định dạng dữ liệu (vd: ép kiểu giá tiền về dạng int thay vì float)
                if col == 'gia_vnd' and val != "":
                    metadata[col] = int(val)
                elif isinstance(val, float) and val.is_integer():
                    metadata[col] = str(int(val))
                else:
                    metadata[col] = str(val) if val != "" else ""

            # Tạo object theo cấu trúc chuẩn có id và metadata
            item = {
                "id": f"pkg_{index + 1:03d}",
                "metadata": metadata
            }
            json_data.append(item)

        # Ghi dữ liệu ra file JSON (tuân thủ Rule 14 & Rule 8)
        content = json.dumps(json_data, ensure_ascii=False, indent=2)
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Đã chuyển đổi thành công {len(json_data)} gói cước từ '{excel_path}' sang '{json_path}'.")
        print("=" * 60)

    except Exception as e:
        print(f"Đã xảy ra lỗi khi chuyển đổi Excel sang JSON: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Quản lý indexing tài liệu và chuyển đổi dữ liệu."
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["reset", "update", "convert"],
        help="Chế độ thực thi: 'reset' (xóa database index lại từ đầu), 'update' (cập nhật file thay đổi), 'convert' (convert excel sang json)"
    )
    parser.add_argument("--reset", action="store_true", help="Chế độ xóa database index lại từ đầu (không bao gồm excel, json)")
    parser.add_argument("--update", action="store_true", help="Chế độ cập nhật database dựa trên các file thay đổi (thêm, sửa, xoá)")
    parser.add_argument("--convert", action="store_true", help="Chế độ chuyển đổi file Excel sang JSON")

    parser.add_argument("--excel", type=str, default=None, help="Đường dẫn file Excel đầu vào (dùng cho chế độ convert, mặc định: docs/goi_cuoc.xlsx)")
    parser.add_argument("--json", type=str, default=None, help="Đường dẫn file JSON đầu ra (dùng cho chế độ convert, mặc định: docs/goi_cuoc.json)")
    parser.add_argument(
        "--export-chunks", metavar="DIR", dest="export_chunks", type=str, default=None,
        help="Xuất file log chunk vào thư mục chỉ định (chỉ dùng với chế độ reset/update). Ví dụ: --export-chunks chunks_output"
    )

    args = parser.parse_args()

    mode = args.mode
    if args.reset:
        mode = "reset"
    elif args.update:
        mode = "update"
    elif args.convert:
        mode = "convert"

    if not mode:
        parser.print_help()
        print("\n[HƯỚNG DẪN] Vui lòng chọn một trong 3 chế độ thực thi:")
        print("  1. Xóa database index lại từ đầu : python index_docs.py --mode reset   (hoặc --reset)")
        print("  2. Cập nhật database theo thay đổi: python index_docs.py --mode update  (hoặc --update)")
        print("  3. Convert Excel sang JSON        : python index_docs.py --mode convert (hoặc --convert)")
        print("\n  Tùy chọn xuất chunk: Thêm --export-chunks <thư_mục> khi dùng chế độ reset hoặc update.")
        sys.exit(1)

    if mode == "reset":
        run_reset(chunks_dir=args.export_chunks)
    elif mode == "update":
        run_update(chunks_dir=args.export_chunks)
    elif mode == "convert":
        excel_to_json(args.excel, args.json)


if __name__ == "__main__":
    main()
