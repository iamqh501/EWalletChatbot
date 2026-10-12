import os
import sys
import time
import uuid
import shutil
import json

# Ensure UTF-8 output on Windows CMD
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from qdrant_client import QdrantClient, models
from langchain_core.documents import Document
from langchain_classic.storage import LocalFileStore
from langchain_classic.storage.encoder_backed import EncoderBackedStore
from langchain_huggingface import HuggingFaceEmbeddings
from fastembed import SparseTextEmbedding
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from backend.core.config import QDRANT_PATH, STORE_PATH, DOCS_DIR

def index_docs():
    print("Xóa dữ liệu cũ...")
    if os.path.exists(QDRANT_PATH):
        shutil.rmtree(QDRANT_PATH)
    if os.path.exists(STORE_PATH):
        shutil.rmtree(STORE_PATH)
        
    os.makedirs(QDRANT_PATH, exist_ok=True)
    os.makedirs(STORE_PATH, exist_ok=True)
    
    print("Khởi tạo Qdrant Client...")
    client = QdrantClient(path=QDRANT_PATH)
    collection_name = "knowledge"
    
    print("Khởi tạo Embeddings...")
    dense_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L12-v2", 
        model_kwargs={'device': 'cpu'}
    )
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)}
    )
    
    fs = LocalFileStore(STORE_PATH)
    store = EncoderBackedStore(
        store=fs,
        key_encoder=lambda x: x,
        value_serializer=lambda doc: json.dumps(doc.model_dump()).encode("utf-8"),
        value_deserializer=lambda bytes_data: Document(**json.loads(bytes_data.decode("utf-8")))
    )
    
    print("Khởi tạo LangChain Markdown Splitters...")
    headers_to_split_on = [
        ("#", "H1"),
        ("##", "H2"),
        ("###", "H3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=3500, chunk_overlap=200)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=40)
    import re
    def split_markdown_documents_with_tables(docs, max_rows=15):
        new_docs = []
        for doc in docs:
            lines = doc.page_content.split("\n")
            i = 0
            current_text = []
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("|") and line.endswith("|") and i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    if next_line.startswith("|") and next_line.endswith("|") and re.match(r'^\|[\s\-\|:]+\|$', next_line):
                        if current_text:
                            text = "\n".join(current_text).strip()
                            if text:
                                new_docs.append(Document(page_content=text, metadata=doc.metadata))
                            current_text = []
                        
                        header = lines[i]
                        separator = lines[i+1]
                        i += 2
                        rows = []
                        while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                            rows.append(lines[i])
                            i += 1
                        
                        for j in range(0, len(rows), max_rows):
                            chunk_rows = rows[j:j+max_rows]
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

    for filename in os.listdir(DOCS_DIR):
        if filename.endswith(".md"):
            filepath = os.path.join(DOCS_DIR, filename)
            print(f"Đang xử lý {filename}...")
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 1. Tách văn bản theo Header trước
            md_docs = markdown_splitter.split_text(content)
            
            # 2. Tách các bảng dài ra thành các Document riêng biệt để không bị dính chunk_overlap
            md_docs = split_markdown_documents_with_tables(md_docs, max_rows=10)
            
            # 3. Đảm bảo các đoạn text thường (không phải bảng) không vượt quá max length
            parent_chunks = parent_splitter.split_documents(md_docs)
            
            parent_docs = []
            
            # Ghi chunk ra file log để kiểm tra
            chunk_file_path = f"langchain_chunks_{filename}"
            with open(chunk_file_path, "w", encoding="utf-8") as f_chunk:
                for idx, doc in enumerate(parent_chunks, 1):
                    headers = []
                    for h in ["H1", "H2", "H3"]:
                        if h in doc.metadata:
                            headers.append(doc.metadata[h])
                    
                    heading_context = " > ".join(headers)
                    raw_text = f"[{heading_context}]\n\n{doc.page_content}" if heading_context else doc.page_content
                    
                    f_chunk.write(f"[Start chunk {idx}]\n")
                    f_chunk.write(raw_text)
                    f_chunk.write(f"\n[End chunk {idx}]\n\n")
                    
                    parent_docs.append(Document(
                        page_content=raw_text,
                        metadata={"file_path": filename}
                    ))
                
            doc_ids = [str(uuid.uuid4()) for _ in parent_docs]
            points = []
            
            for i, parent_doc in enumerate(parent_docs):
                _id = doc_ids[i]
                _sub_docs = child_splitter.split_documents([parent_doc])
                for _doc in _sub_docs:
                    child_id = str(uuid.uuid4())
                    text = _doc.page_content
                    dense_vec = dense_model.embed_query(text)
                    sparse_res = list(sparse_model.embed([text]))[0]
                    points.append(
                        models.PointStruct(
                            id=child_id,
                            payload={"page_content": text, "metadata": {"doc_id": _id}},
                            vector={
                                "dense": dense_vec,
                                "sparse": models.SparseVector(
                                    indices=sparse_res.indices.tolist(),
                                    values=sparse_res.values.tolist()
                                )
                            }
                        )
                    )
            
            if points:
                client.upload_points(collection_name=collection_name, points=points)
                print(f"-> Đã upload {len(points)} child chunks lên Qdrant.")
            if doc_ids:
                store.mset(list(zip(doc_ids, parent_docs)))
                print(f"-> Đã lưu {len(doc_ids)} parent docs vào LocalFileStore.")

    print("Hoàn tất indexing!")

if __name__ == "__main__":
    index_docs()
