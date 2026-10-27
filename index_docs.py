import os
import sys
import time
import shutil
import json
import argparse

# Ép kiểu encoding của sys.stdout sang utf-8 để tránh lỗi khi in tiếng Việt trên CMD Windows (Rule 8)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import backend.core.env

from qdrant_client import QdrantClient, models
from langchain_core.documents import Document
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from fastembed import SparseTextEmbedding

from backend.services.retrieval import get_dense_embedding_model

from backend.core.config import (
    QDRANT_PATH, STORE_PATH, DOCS_DIR, STATE_FILE,
    COLLECTION_NAME, CATEGORIES, TELECOM_EXCEL_FILE, TELECOM_PACKAGES_FILE
)

from backend.services.doc_manager import (
    is_indexable_doc,
    determine_category,
    get_file_hash,
    load_state,
    save_state,
    init_splitters,
    convert_telecom_excel_to_json,
    index_single_excel_file as doc_index_excel,
    index_single_markdown_file as doc_index_markdown,
    delete_file_from_index
)


def scan_indexable_files():
    """Quét toàn bộ file hợp lệ để index qua các thư mục con knowledge, faq, navigation."""
    results = {}
    if not os.path.exists(DOCS_DIR):
        return results
    for root, dirs, files in os.walk(DOCS_DIR):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, DOCS_DIR).replace("\\", "/")
            if is_indexable_doc(rel_path):
                results[rel_path] = fpath
    return results


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


def run_reset():
    """Chế độ 1: Xóa database index lại từ đầu trên tất cả các danh mục."""
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

    # 2. Quét file tài liệu hợp lệ trên tất cả các subfolder (knowledge, faq, navigation)
    file_map = scan_indexable_files()
    rel_keys = list(file_map.keys())
    print(f"Tìm thấy {len(rel_keys)} tài liệu hợp lệ trên các danh mục để index.\n")

    new_state = {}
    for idx, rel_key in enumerate(rel_keys, 1):
        filepath = file_map[rel_key]
        print(f"[{idx}/{len(rel_keys)}] Đang xử lý {rel_key}...")
        if rel_key.lower().endswith((".xlsx", ".xls")):
            doc_ids, point_ids = doc_index_excel(filepath, rel_key, client, store, dense_model, sparse_model)
        else:
            doc_ids, point_ids = doc_index_markdown(
                filepath, rel_key, client, store, dense_model, sparse_model,
                markdown_splitter, parent_splitter, child_splitter
            )
        new_state[rel_key] = {
            "hash": get_file_hash(filepath),
            "doc_ids": doc_ids,
            "point_ids": point_ids,
            "category": determine_category(rel_key),
            "indexed_at": time.time()
        }

    save_state(new_state)
    client.close()
    print("\n" + "=" * 60)
    print(f"Hoàn tất Reset & Index! Đã index thành công {len(rel_keys)} files vào database.")
    print("=" * 60)


def run_update():
    """Chế độ 2: Update database dựa trên các file đã thay đổi nội dung từ lần cuối (thêm, sửa, xoá)."""
    print("=" * 60)
    print("[CHẾ ĐỘ UPDATE] Cập nhật database dựa trên các file đã thay đổi")
    print("=" * 60)

    state = load_state()
    if not os.path.exists(QDRANT_PATH) or not state:
        print("Chưa tìm thấy database hoặc trạng thái index trước đó. Tự động chuyển sang index lại từ đầu...")
        run_reset()
        return

    file_map = scan_indexable_files()
    current_files = {rel_k: get_file_hash(file_map[rel_k]) for rel_k in file_map}
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
    for rel_path in deleted_files:
        print(f"-> Đang xóa dữ liệu của: {rel_path}...")
        delete_file_from_index(rel_path, state[rel_path], client, store)
        del state[rel_path]

    # 2. Xử lý các file được chỉnh sửa hoặc thêm mới
    if added_files or modified_files:
        dense_model, sparse_model = init_embeddings()
        markdown_splitter, parent_splitter, child_splitter = init_splitters()

        # Chỉnh sửa
        for rel_path in modified_files:
            print(f"-> Đang cập nhật lại file: {rel_path}...")
            delete_file_from_index(rel_path, state[rel_path], client, store)
            filepath = file_map[rel_path]
            if rel_path.lower().endswith((".xlsx", ".xls")):
                doc_ids, point_ids = doc_index_excel(filepath, rel_path, client, store, dense_model, sparse_model)
            else:
                doc_ids, point_ids = doc_index_markdown(
                    filepath, rel_path, client, store, dense_model, sparse_model,
                    markdown_splitter, parent_splitter, child_splitter
                )
            state[rel_path] = {
                "hash": current_files[rel_path],
                "doc_ids": doc_ids,
                "point_ids": point_ids,
                "category": determine_category(rel_path),
                "updated_at": time.time()
            }

        # Thêm mới
        for rel_path in added_files:
            print(f"-> Đang index file mới: {rel_path}...")
            filepath = file_map[rel_path]
            if rel_path.lower().endswith((".xlsx", ".xls")):
                doc_ids, point_ids = doc_index_excel(filepath, rel_path, client, store, dense_model, sparse_model)
            else:
                doc_ids, point_ids = doc_index_markdown(
                    filepath, rel_path, client, store, dense_model, sparse_model,
                    markdown_splitter, parent_splitter, child_splitter
                )
            state[rel_path] = {
                "hash": current_files[rel_path],
                "doc_ids": doc_ids,
                "point_ids": point_ids,
                "category": determine_category(rel_path),
                "indexed_at": time.time()
            }

    save_state(state)
    client.close()
    print("\n" + "=" * 60)
    print(f"Cập nhật hoàn tất! (Thêm: {len(added_files)}, Sửa: {len(modified_files)}, Xóa: {len(deleted_files)})")
    print("=" * 60)


def excel_to_json(excel_path: str = None, json_path: str = None):
    """Chế độ 3: Chuyển đổi nội dung Excel sang file JSON."""
    excel_path = excel_path or TELECOM_EXCEL_FILE
    json_path = json_path or TELECOM_PACKAGES_FILE

    print("=" * 60)
    print(f"[CHẾ ĐỘ CONVERT] Chuyển đổi từ '{excel_path}' sang '{json_path}'")
    print("=" * 60)

    if not os.path.exists(excel_path):
        print(f"Lỗi: Không tìm thấy file Excel tại '{excel_path}'")
        return

    try:
        count = convert_telecom_excel_to_json(excel_path, json_path)
        print(f"Đã chuyển đổi thành công {count} gói cước từ '{excel_path}' sang '{json_path}'.")
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
    parser.add_argument("--reset", action="store_true", help="Chế độ xóa database index lại từ đầu")
    parser.add_argument("--update", action="store_true", help="Chế độ cập nhật database dựa trên các file thay đổi (thêm, sửa, xoá)")
    parser.add_argument("--convert", action="store_true", help="Chế độ chuyển đổi file Excel sang JSON")

    parser.add_argument("--excel", type=str, default=None, help=f"Đường dẫn file Excel đầu vào (dùng cho chế độ convert, mặc định: {TELECOM_EXCEL_FILE})")
    parser.add_argument("--json", type=str, default=None, help=f"Đường dẫn file JSON đầu ra (dùng cho chế độ convert, mặc định: {TELECOM_PACKAGES_FILE})")

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
        sys.exit(1)

    if mode == "reset":
        run_reset()
    elif mode == "update":
        run_update()
    elif mode == "convert":
        excel_to_json(args.excel, args.json)


if __name__ == "__main__":
    main()
