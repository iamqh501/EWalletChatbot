```text
[ Người Dùng ]
      │
      ▼ (1. Đặt câu hỏi)
      │
[ Agent - LLM ] <─────────────────────────────────────────────┐
      │                                                       │
      ├─ (2. Quyết định tra cứu dữ liệu nếu cần)              │
      │                                                       │
      ├───> Tool 1: [ search_general_knowledge ]              │
      │        └─ (Tra cứu kiến thức chung) ──────────────────┤
      │                                                       │ (3. Trả kết quả)
      ├───> Tool 2: [ search_telecom_packages ]               │
      │        └─ (Tra cứu thông tin gói cước) ───────────────┤
      │                                                       │
      └───> Tool 3: [ rewrite_query_tool ]                    │
               └─ (Làm rõ ngữ cảnh câu hỏi cũ) ───────────────┘
      │
      ▼ (4. Tổng hợp thông tin từ Tool)
      │
[ Người Dùng ] (Nhận câu trả lời)
```

---

## System Prompt

- **Buộc gọi tool tra cứu** (trừ lời chào) ➔ Tránh bịa thông tin
- **Ưu tiên tool tra cứu** (chỉ rewrite khi thiếu ngữ cảnh) ➔ Tối ưu luồng, tránh lạm dụng rewrite
- **Dùng tool rewrite trước** (với câu hỏi nối tiếp) ➔ Khôi phục ngữ cảnh trước khi tra cứu
- **Buộc dùng `search_telecom_packages`** (khi hỏi mã gói, data, giá) ➔ Dùng đúng DB, tránh nhầm tên điện thoại
- **Trả lời sát kết quả tool** ➔ Không bình luận, khuyên bảo hay tự suy diễn
- **Giữ nguyên format gốc** (không tô vẽ cầu kỳ) ➔ Bảo toàn tính chuẩn xác, tránh lỗi do tóm tắt


---

## Tool

### 1. `search_general_knowledge`
- **query**: Từ khóa hoặc nội dung câu hỏi cần tra cứu
- **Output**: Trích đoạn tài liệu gốc chứa thông tin liên quan

### 2. `search_telecom_packages`
- **package_name**: Tên mã gói cước (VD: YOLO, BIG, D169G)
- **price_min / max**: Khoảng giới hạn giá tiền (VND)
- **data_gb_per_day_min / max**: Khoảng giới hạn dung lượng data mỗi ngày (GB)
- **Output**: Danh sách thông số chi tiết của các gói cước thỏa điều kiện

### 3. `rewrite_query_tool`
- **query_to_rewrite**: Câu hỏi hiện tại đang bị thiếu ngữ cảnh
- **reason**: Lý do giải thích vì sao cần viết lại câu hỏi
- **retrieved_info**: Các thông tin đã tra cứu được từ các bước trước (nếu có)
- **Output**: Câu hỏi mới đã được bổ sung đầy đủ ngữ cảnh để LLM dễ hiểu hơn


---

## Hệ thống & Kỹ thuật

### 1. Framework
- **Frontend**: React (Vite)
- **Backend**: FastAPI (Uvicorn)

### 2. LLM & Hosting
- **Mô hình**: `gemma-4-E2B-it-qat-GGUF` (Local)
- **Hosting**: Chạy offline trực tiếp trên máy qua `llama-server` (llama.cpp)
- **Tích hợp**: Giao tiếp qua thư viện LangChain `ChatDeepSeek` (tương thích chuẩn OpenAI API)

### 3. Xử lý tài liệu (Docs Processing)
- **Thư viện**: LangChain, Qdrant Client, FastEmbed, HuggingFace Embeddings
- **Tùy biến (Customize)**: Xây dựng logic tự động cắt các bảng Markdown dài (>10 dòng) thành nhiều phần nhỏ nhưng vẫn ghép nối lại với Header cũ, giúp bảng không bị mất cấu trúc khi lên LLM.
- **Lưu trữ (Parent-Child)**:
  - **Child chunks** (đoạn ngắn để tìm kiếm): Lưu vector vào cơ sở dữ liệu Qdrant (`local_qdrant/`)
  - **Parent chunks** (đoạn dài nguyên vẹn ngữ cảnh): Lưu vào LocalFileStore (`parent_store/`)

### 4. Truy xuất dữ liệu (Retrieval)
- **Cơ chế**: Parent-Child Retrieval (Tìm khớp trên đoạn nhỏ, trả về toàn bộ đoạn văn bản lớn chứa nó)
- **Thuật toán**: Hybrid Search kết hợp Dense (MiniLM) + Sparse (BM25), trộn kết quả bằng RRF (Reciprocal Rank Fusion) của Qdrant.
- **Reranking**: Chấm điểm và xếp hạng lại Top 20 kết quả bằng mô hình Cross-Encoder (`mmarco-mMiniLMv2`) để chọn ra Top 5 tốt nhất.
