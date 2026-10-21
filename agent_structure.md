```text
[ Người Dùng ]
      │
      ▼ (1. Đặt câu hỏi)
      │
[ Đánh giá Tương đồng Lịch sử - Jev TypeSafe ]
      │ (Chấm điểm 10 message gần nhất, tính u_i qua Harmonic Bridge, lọc >= 0.7)
      ▼
[ Agent - LLM ] <─────────────────────────────────────────────┐
      │                                                       │
      ├─ (2. Quyết định tra cứu nếu chưa có đủ ngữ cảnh)      │
      │                                                       │
      ├───> Tool 1: [ search_general_knowledge ]              │
      │        └─ (Tra cứu kiến thức chung) ──────────────────┤
      │                                                       │ (3. Trả kết quả)
      ├───> Tool 2: [ search_telecom_packages ]               │
      │        └─ (Tra cứu thông tin gói cước) ───────────────┤
      │                                                       │
      └───> Tool 3: [ resolve_intent ]                        │
               └─ (Phân tích giải quyết ý định mơ hồ) ────────┘
      │
      ▼ (4. Tổng hợp thông tin từ Ngữ cảnh Lịch sử & Tool)
      │
[ Người Dùng ] (Nhận câu trả lời)
```

---

## Cấu trúc System Prompt (Tách 2 lần gọi LLM riêng biệt)

### 1. Prompt Lần 1: Quyết định Tool (`TOOL_ROUTING_SYSTEM_PROMPT`)
- **Bắt buộc có ngữ cảnh tra cứu**: Ngữ cảnh lịch sử (đạt độ tương đồng >= 0.7) được coi là hợp lệ. Nếu ngữ cảnh này đã đủ thông tin để trả lời, **không cần gọi tool tra cứu**.
- **Gọi tool tra cứu khi chưa đủ ngữ cảnh**: Nếu chưa có hoặc thiếu thông tin, bắt buộc gọi tool đúng 1 lần.
- **Xử lý khi không chắc chắn / mơ hồ**: Gọi `resolve_intent` theo quy trình 3 bước (Hypotheses ➔ Evidence-based Evaluation ➔ Decision). Nếu đã rõ ý định thì gọi tool tra cứu tương ứng; nếu thiếu căn cứ thì đưa ra câu hỏi làm rõ ngắn gọn.
- **Buộc dùng `search_telecom_packages`** (khi hỏi mã gói, data, giá, chu kỳ) ➔ Dùng đúng DB gói cước
- **Buộc dùng `search_general_knowledge`** (khi hỏi biểu phí, liên kết, chính sách ví) ➔ Dùng đúng DB tài liệu
- *Không chứa bất kỳ ràng buộc nào về định dạng để tránh loãng sự tập trung khi chọn tool.*

### 2. Prompt Lần 2: Ràng buộc kết quả trả về (`FINAL_RESPONSE_SYSTEM_PROMPT`)
- **Điều kiện kích hoạt**: Chỉ kích hoạt khi có kết quả từ các tool tra cứu (`search_general_knowledge` hoặc `search_telecom_packages`). Khi chỉ gọi `resolve_intent` để hỏi làm rõ, hệ thống trả lời trực tiếp từ Lần 1 và bỏ qua Lần 2.
- **Dùng kết quả đã tra cứu / ngữ cảnh hợp lệ để trả lời** ➔ Tuyệt đối không tự bịa đặt khi tài liệu không có
- **Trình bày đa chiều nếu có phân tích ý định**: Trình bày rõ các khả năng hoặc câu hỏi làm rõ nếu kết quả phân tích ý định chỉ ra nhiều khả năng.
- **Không bình luận, không khuyên bảo, không suy diễn** ➔ Chỉ trả lời sát và đúng nội dung tài liệu/ngữ cảnh
- **Tránh rephrase** ➔ Giữ nguyên câu chữ và thuật ngữ chuẩn xác từ tài liệu gốc
- **Giữ nguyên format gốc** (không tô vẽ cầu kỳ) ➔ Bảo toàn cấu trúc bảng, danh sách
- **Đầy đủ thông tin** ➔ Hạn chế tóm tắt hay cắt bớt dữ liệu quan trọng


---

## Tool

### 1. `search_general_knowledge`
- **query**: Từ khóa hoặc nội dung câu hỏi cần tra cứu
- **Output**: Danh sách các đoạn trích tài liệu gốc phù hợp kèm nguồn và điểm số (sắp xếp theo điểm tương đồng giảm dần)

### 2. `search_telecom_packages`
- **package_name**: Tên mã gói cước (VD: YOLO, BIG, D169G)
- **price_min / max**: Khoảng giới hạn giá tiền (VND)
- **cycle_days_min / max**: Khoảng chu kỳ sử dụng tính theo ngày (VD: tuần = 7, tháng = 30, năm = 360)
- **data_gb_per_day_min / max**: Khoảng giới hạn dung lượng data mỗi ngày (GB)
- **Output**: Danh sách thông số chi tiết của các gói cước thỏa điều kiện

### 3. `resolve_intent`
- **query**: Câu hỏi/yêu cầu hiện tại của người dùng đang bị mơ hồ hoặc không chắc chắn
- **uncertainty_reason**: Lý do chi tiết giải thích vì sao không chắc chắn (nhiều cách hiểu, thiếu chủ ngữ, v.v.)
- **Output**: Báo cáo phân tích 3 phần:
  1. *Danh sách Hypotheses*: Cách hiểu theo nghĩa đen và cách hiểu theo ngữ cảnh.
  2. *Evidence-based Evaluation*: Đối chiếu bằng chứng từ query, lịch sử và logic tác vụ kèm độ tin cậy.
  3. *Decision*: Cách hiểu tối ưu để tra cứu tiếp, hoặc tóm tắt các khả năng, hoặc đề xuất câu hỏi làm rõ ngắn.



---

## Hệ thống & Kỹ thuật

### 1. Framework
- **Frontend**: React (Vite)
- **Backend**: FastAPI (Uvicorn), kiến trúc phân tầng chuẩn hóa (`api/`, `core/`, `prompts/`, `tools/`, `services/`, `utils/`)

### 2. LLM & Hosting
- **Mô hình**: Cấu hình linh hoạt qua biến môi trường hoặc file `.env` (`HF_LLM_MODEL_NAME=inclusionAI/Ling-3.0-flash:fastest`)
- **VLM (Vision-Language)**: Cấu hình qua biến môi trường hoặc file `.env` (`HF_VLM_MODEL_NAME=inclusionAI/Ling-3.0-flash-VL:fastest`). Khi query có đính kèm ảnh, mô hình VLM được kích hoạt để quan sát, phân tích chi tiết thông tin ảnh và viết lại câu hỏi (query rewrite) giàu ngữ cảnh trước khi đưa vào pipeline xử lý.
- **Hosting**: Hugging Face Router API (`https://router.huggingface.co/v1`)
- **Tích hợp**: Giao tiếp qua thư viện LangChain `ChatDeepSeek` (hỗ trợ native streaming reasoning, tool calling, `stream_usage=True` đo tốc độ sinh token, `max_tokens=None` - không giới hạn token đầu ra)

### 3. Xử lý tài liệu (Docs Processing)
- **Thư viện**: LangChain, Qdrant Client, FastEmbed, HuggingFace Endpoint Embeddings
- **Tùy biến (Customize)**: Xây dựng logic tự động cắt các bảng Markdown dài (>10 dòng) thành nhiều phần nhỏ nhưng vẫn ghép nối lại với Header cũ, giúp bảng không bị mất cấu trúc khi lên LLM.
- **Lưu trữ (Parent-Child)**:
  - **Child chunks** (đoạn ngắn để tìm kiếm): Lưu vector vào cơ sở dữ liệu Qdrant (`local_qdrant/`)
  - **Parent chunks** (đoạn dài nguyên vẹn ngữ cảnh): Lưu vào LocalFileStore (`parent_store/`)

### 4. Truy xuất dữ liệu (Retrieval)
- **Cơ chế**: Parent-Child Retrieval (Tìm khớp trên đoạn nhỏ, trả về toàn bộ đoạn văn bản lớn chứa nó)
- **Thuật toán**: Hybrid Search kết hợp Dense (gọi qua Hugging Face API - mô hình `google/embeddinggemma-300m`) + Sparse (BM25 - FastEmbed `Qdrant/bm25`), trộn kết quả bằng RRF (Reciprocal Rank Fusion) của Qdrant.
- **Reranking**: Chấm điểm và xếp hạng lại các Parent Chunk bằng mô hình `Jev` (TypeSafe API - `Noul`) với ngưỡng lọc `score_threshold >= 0.6`. Mặc định `top_k=None` (lấy toàn bộ các parent chunk đạt ngưỡng, giới hạn ngữ cảnh an toàn 60.000 ký tự).

### 5. Đánh giá tương đồng lịch sử (History Scoring & Harmonic Bridge)
- **Mô hình & Thư viện**: TypeSafe Jev (`typesafe-sdk`, model `jev-latest` / `Noul`).
- **Phạm vi đánh giá**: Tối đa 10 message gần nhất trong phiên (`app_state.conversations`).
- **Cơ chế ưu tiên vị trí**: Truyền vị trí tương quan (`{k} message trước`) và prompt ưu tiên cao các tin nhắn gần nhất khi query chứa các từ quy chiếu ngữ cảnh ("phần trên", "thứ 2", "trước đó", "vừa rồi"...).
- **Cập nhật Harmonic Bridge**:
  - $d_{bridge\_ij} = \frac{2 \cdot d_i \cdot r_{ij}}{d_i + r_{ij}}$
  - $u_i = a \cdot d_i + (1 - a) \cdot \text{avg}_{j \neq i}(d_{bridge\_ij})$ với $a = 0.5$.
  - Cập nhật ma trận đối xứng $r_{ij}$ lưu trữ qua các lượt query trong session.
- **Ngưỡng lọc & Tích hợp**: Các message đạt $u_i \ge 0.7$ được cung cấp làm ngữ cảnh tra cứu hợp lệ. Nếu đủ thông tin, LLM trả lời trực tiếp mà không cần gọi tool tra cứu.
