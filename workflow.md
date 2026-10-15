# Workflow: Test Tool Calling với Data Gói Cước

1. **Khởi tạo Workflow (Done)**: Tạo file `workflow.md` và `progress.md`.
2. **Khám phá Dữ liệu**: Phân tích cấu trúc của file `docs/goi_cuoc.json`.
3. **Viết Script Tool Calling**:
    - Load data JSON.
    - Định nghĩa một tool (ví dụ: `search_goi_cuoc` để tìm kiếm thông tin gói cước, hoặc lấy giá gói cước...).
    - Khởi tạo LLM bằng `get_llama_cpp_model()` từ `backend.services.llm`.
    - Tạo Agent với `create_agent` theo yêu cầu Rule 7.
4. **Thực thi Script**: Chạy script để test tool calling bằng một câu query (ví dụ: "Cho tôi biết gói cước 12ST60N").
5. **Đánh giá**:
    - Đánh giá kết quả sinh ra.
    - Đánh giá chất lượng dữ liệu trong JSON.
    - Đánh giá phương pháp (tool calling với model cục bộ).
6. **Cập nhật Progress**: Ghi nhận hoàn thành vào `progress.md`.

## Phase 2: Nâng cấp Tool Calling (Tìm kiếm Nâng cao)
7. **Cập nhật Tool Search**:
    - Chuyển đổi dữ liệu JSON từ String sang Float/Int để so sánh.
    - Hỗ trợ các tham số: `ten_goi` (partial match), `gia_min/max`, `chu_ky_min/max`, `dung_luong_min/max`.
    - Viết docstring chi tiết để LLM tự hiểu các từ đồng nghĩa (lưu lượng = dung lượng, thời gian = chu kỳ) và các phép tính khoảng (<=, >=).
8. **Thử nghiệm Nâng cao**:
    - Test case thời gian: "Gói từ 3 ngày trở xuống".
    - Test case giá/dung lượng: "Gói nào rẻ hơn 50k, dung lượng cao".
    - Test case fuzzy name: "Gói BIG".
9. **Cập nhật Evaluation và Progress**.

## Phase 3: Tích hợp Hệ thống (Routing & Unified Tool Calling)
10. **Cập nhật Backend Main**:
    - Tích hợp hàm `classify_intent_llm` để xác định [GREETING, GENERAL, DATA_PLAN].
    - Chuyển logic search Qdrant thành `@tool tim_kiem_kien_thuc` (thủ công).
    - Chuyển data JSON thành `@tool tim_kiem_goi_cuoc` (tool calling parameter extraction bằng `llm.bind_tools`).
    - Gộp dữ liệu từ các intent thành 1 Prompt duy nhất.
    - Trả kết quả cuối cùng bằng cơ chế Streaming hiện tại của hệ thống.
11. **Kiểm thử tích hợp**: Chạy Backend và gửi các câu lệnh kết hợp nhiều intent.

## Phase 4: Fix Bug "Biểu phí dịch vụ" (Frontend Freezing)
12. **Xác định nguyên nhân gốc rễ**: Phân tích log SSE từ backend (khi tải model sinh ra token rỗng) và logic clear `systemStatus` trên frontend `App.jsx`.
13. **Sửa lỗi**: Cập nhật `App.jsx` để chỉ clear trạng thái loading khi text nhận được khác rỗng.
14. **Cập nhật Progress**: Cập nhật `progress.md` và viết log phân tích lỗi.

## Phase 5: Fix Markdown Table Formatting
15. **Xác định nguyên nhân gốc rễ**: Lỗi hiển thị bảng trên 1 dòng do `react-markdown` thiếu plugin `remark-gfm` (GitHub Flavored Markdown) để nhận diện cú pháp bảng.
16. **Sửa lỗi**: Cài đặt `remark-gfm`, thêm vào `remarkPlugins` trong `App.jsx`, và bổ sung CSS cho bảng.
17. **Cập nhật Progress**: Ghi nhận hoàn thành vào `progress.md`.

## Phase 8: Refactor Configuration and UI Logging
18. **Tach config port**: Chuyen port backend va frontend sang file config ports.json.
19. **Tu dong don dep tien trinh**: Cap nhat un_app.bat tu dong kill cac tien trinh cu dang chay tren port can dung.
20. **Toi uu UI Log**: Xoa bot cac yield status khong can thiet o terminal frontend (Khoi tao he thong, dang sinh cau tra loi, hoan tat goi tool, vv). Thay vao do in ra thoi gian khoi tao xong tren cmd. 
21. **Toi uu hien thi Tool Call**: Format lai tool call giong kieu function call, dung tag \\\ cho OUTPUT va tang limit ky tu len gap 10 lan (150 -> 1500).
  
## Phase 9: Don dep du an  
22. Xoa toan bo cac file test, patch, log, output text, chunk md, va thu muc scratch khong can dung de chay app. 

## Phase 10: Thay the Reranker bang Jev (TypeSafe)
23. **Cap nhat Retrieval Service**: Xay dung class `JevReranker` tich hop `typesafe-sdk` theo cookbook `rerank_typesafe`, thay the model `CrossEncoder` cu trong `backend/services/retrieval.py`.
24. **Ho tro cau hinh**: Cho phep lay `TYPESAFE_API_KEY` tu bien moi truong hoac `local_paths.json`.
25. **Thuc thi Kiem thu (Test)**: Viet script test danh gia hieu nang, tinh chinh xac va do tre cua Jev Reranker voi du lieu knowledge base Qdrant.
26. **Cap nhat Progress & Bao cao**: Ghi nhan ket qua vao `progress.md` va bao cao chi tiet cho nguoi dung.
27. **Loc nguong Score**: Bo sung logic loc ket qua theo nguong diem (chi lay cac doan co score >= 0.6) trong `backend/services/retrieval.py`.

## Phase 11: Thay the LLM Local bang IBM Granite qua Hugging Face Router
28. **Kiem thu doc lap**: Chay smoke test kiem tra ket noi, streaming thinking va tool calling tren `ibm-granite/granite-4.2-3b:deepinfra`.
29. **Cap nhat LLM Service**: Tich hop co che dinh tuyen remote LLM qua Hugging Face Router trong `backend/services/llm.py`, khong can khoi chay `llama-server.exe` ngam.
30. **Kiem thu toan trinh & Ghi nhan**: Chay backend, kiem tra ket qua va cap nhat `progress.md`.

## Phase 12: Rerank voi Parent Chunk thay vi Child Chunk
31. **Chuyen doi logic Rerank sang Parent Chunk**: Thay doi `search_and_rerank` trong `backend/services/retrieval.py` de lay parent doc tu store truoc, sau do moi rerank voi parent doc page_content.
32. **Test va danh gia nguong Score**: Chay test mot truong hop cu the, in ra tat ca cac parent chunk va score de danh gia va de xuat nguong score toi uu.
33. **Cap nhat Progress & Bao cao**: Ghi nhan ket qua vao `progress.md`.

## Phase 13: Refactor LLM Service va don dep Legacy code
34. **Refactor LLM Service**: Doi ten `get_llama_cpp_model` thanh `get_llm_model`, loai bo class `LlamaServerManager` va cac tien trinh quan ly local server trong `backend/services/llm.py`.
35. **Cap nhat cac vi tri goi LLM**: Thay the import va goi ham trong `backend/main.py`.
36. **Cap nhat tai lieu & tien do**: Dong bo hoa `agent_structure.md`, `workflow.md` va `progress.md`.

## Phase 14: Kich hoat do toc do Token qua stream_usage chuan API
37. **Bat stream_usage**: Them `stream_usage=True` vao `ChatDeepSeek` trong `backend/services/llm.py`.
38. **Cap nhat hien thi Stats**: Trong `backend/main.py`, neu co du lieu token thi in day du toc do Prompt & Gen, neu khong thi an 2 thong so do.
39. **Kiem thu & Ghi nhan**: Chay test SSE stream kiem tra thong so stats va cap nhat `progress.md`.

## Phase 15: Tra ve list chunks cho search_general_knowledge va rut gon output thinking
40. **Cap nhat search_general_knowledge**: Thay doi kieu tra ve thanh list cac chunk da sap xep theo score giam dan thay vi noi string.
41. **Toi uu hien thi Thinking**: Trong khoi thinking, in ra tong so chunk va chi in 2 dong dau cua moi chunk.
42. **Kiem thu & Ghi nhan**: Chay test luong tra cuu va cap nhat `progress.md`.

## Phase 16: Thay the LLM model bang Qwen/Qwen3-8B:nscale
43. **Cap nhat cau hinh**: Doi `HF_MODEL_NAME` sang `Qwen/Qwen3-8B:nscale` trong `local_paths.json` va gia tri mac dinh trong `backend/services/llm.py`.
44. **Kiem thu ket noi & suy luan**: Chay smoke test kiem tra model qua Hugging Face Router ve stream thinking, tool calling va stream_usage.
45. **Kiem thu he thong toan trinh & cap nhat tien do**: Chay test backend va dong bo `agent_structure.md`, `progress.md`.

## Phase 17: Fix loi khoi thinking bi tran ra output khi goi tool
46. **Sua backend (`backend/main.py`)**: Khong dong `</think>` khi chunk content chi la khoang trang (`\n\n`) truoc tool call hoac khi co `tool_calls`; giu mot khoi thinking duy nhat xuyen suot qua trinh suy luan va goi tool.
47. **Sua frontend (`frontend/src/App.jsx`)**: Nang cap `parseMessage` tach toan bo cac khoi `<think>...</think>` (neu co nhieu khoi) gom vao thinking, loai bo triet de khoi output chinh.
48. **Kiem thu & Ghi nhan**: Test kiem tra stream SSE voi cau hoi goi tool va cap nhat `progress.md`.

## Phase 18: Ho tro render the br xuong dong trong bang Markdown va van ban
49. **Sua frontend (`frontend/src/App.jsx`)**: Bo sung `renderWithLineBreaks` va `markdownComponents` cho ReactMarkdown (xu ly `td`, `th`, `p`, `li`) de chuyen `<br>` thanh `<br />` JSX thuc thu.
50. **CSS Styling (`frontend/src/App.css`)**: Can chinh `vertical-align: top;` cho cac o bang de du lieu nhieu dong hien thi can doi.
51. **Kiem thu & Ghi nhan**: Kiem thu render bang voi the `<br>` va cap nhat `progress.md`.

## Phase 19: Cap nhat so chunk toi da lay ve None, gap doi max token va do dai chunk
52. **Cap nhat retrieval (`backend/services/retrieval.py`)**: Doi default `top_k: int | None = None` trong `search_and_rerank` de lay toan bo cac chunk thoa man nguong score.
53. **Gap doi max token (`backend/services/llm.py`)**: Nâng `max_tokens` mac dinh tu 8192 len 16384 tokens.
54. **Chinh do dai chunk (`backend/main.py`)**: Nâng gioi han tong do dai cac chunk dua vao query tu 30000 len 60000 ky tu.
55. **Kiem thu & Ghi nhan**: Chay kiem thu tra cuu voi `top_k=None` va cap nhat `progress.md`.

## Phase 20: Bo gioi han max_tokens cua LLM
56. **Cap nhat llm service (`backend/services/llm.py`)**: Dat mac dinh `max_tokens=None` (bo gioi han max_tokens o phia client, cho phep model su dung toi da context window).
57. **Kiem thu & Ghi nhan**: Kiem thu khoi tao model khong gioi han token va dong bo `agent_structure.md`, `progress.md`.

## Phase 21: Chuyen model sang Qwen/Qwen3.5-9B:deepinfra
58. **Kiem thu model & provider**: Thu nghiem `Qwen/Qwen3-8B:fastest` (ket qua: `model_not_supported`), kiem thu `Qwen/Qwen3.5-9B:deepinfra` (xac nhan thanh cong 200 va ho tro tool calling).
59. **Cap nhat cau hinh**: Chuyen `HF_MODEL_NAME` sang `Qwen/Qwen3.5-9B:deepinfra` trong `local_paths.json` va gia tri fallback trong `backend/services/llm.py`.
60. **Kiem thu toan trinh & Cap nhat tien do**: Chay kiem thu goi tool va dong bo `agent_structure.md`, `workflow.md`, `progress.md`.

## Phase 22: Toi uu trai nghiem nap mo hinh & luong khoi tao
61. **Xay dung Init Progress API (`backend/main.py`)**:
    - Quan ly tien trinh nap cac thanh phan: Qdrant & FileStore, Dense Embedding, Sparse Embedding, Reranker, LLM.
    - Cung cap endpoint SSE `/api/init-stream` va endpoint `/api/health` phan hoi trang thai thoi gian thuc.
62. **Cap nhat giao dien khoi tao & bong bong chat rieng (`frontend/src/App.jsx`, `frontend/src/App.css`)**:
    - Loading indicator thong bao tu ngu chuan xac thanh phan dang nap.
    - Hien thi bong bong chat rieng dau tien in danh sach cac thanh phan khi nap xong, tach biet hoan toan voi cau tra loi query cua user.
    - Cho phep user nhap san cau hoi vao o input khi dang nap, chi vo hieu hoa nut gui cho den khi he thong san sang.
63. **Kiem thu toan trinh & Cap nhat tien do**:
    - Kiem thu luong stream khoi tao, kiem thu nhap san cau hoi va gui query khi he thong ready.
    - Dong bo `progress.md`.

## Phase 23: Toi gian hoa giao dien khoi tao & chuan hoa tieng Anh
64. **Chuan hoa thong diep Backend (`backend/main.py`)**:
    - Chuyen ten cac thanh phan sang tieng Anh ngan gon: `Knowledge Base`, `Dense Embedding`, `Sparse Embedding`, `Reranker`, `LLM`.
    - Rut gon thong diep loading va hoan tat (`System ready.`).
65. **Toi gian hoa giao dien Frontend (`frontend/src/App.jsx`, `frontend/src/App.css`)**:
    - Loai bo toan bo emoji, the heading, in dam va lùi dong.
    - Hien thi danh sach theo dinh dang log terminal toi gian: `<component>: loaded`.
    - Tinh chinh CSS typography (monospace, padding, border toi gian).
66. **Kiem thu toan trinh & Cap nhat tien do**:
    - Kiem thu build frontend va kiem tra luong SSE backend.
    - Dong bo `progress.md`.

## Phase 24: Hop nhat script indexing va convert du lieu voi 3 che do CLI
67. **Thiet ke & Cau hinh Trang thai Index**:
    - Dinh nghia `STATE_FILE` de luu hash va id chunk cua tung file tai lieu.
    - Xay dung co che bo qua file excel (.xlsx, .xls) va json (.json) khi xu ly database vector.
68. **Gop logic Convert Excel sang JSON vao `index_docs.py`**:
    - Chuyen ham chuyen doi excel thanh json tu `convert_excel_to_json.py` vao `index_docs.py`.
    - Xoa file `convert_excel_to_json.py`.
69. **Cai dat 3 che do CLI trong `index_docs.py`**:
    - Che do `reset`: Xoa database index lai tu dau (khong bao gom file excel, json) va luu state.
    - Che do `update`: So sanh hash cac file voi state (xu ly cac file them, sua, xoa) va cap nhat Qdrant cung LocalFileStore tuong ung.
    - Che do `convert`: Chuyen doi noi dung excel thanh file json.
70. **Kiem thu ca 3 che do & Cap nhat tien do**:
    - Chay thu che do convert, kiem tra ket qua json.
    - Chay thu che do reset, kiem tra so luong point va parent doc duoc index.
    - Chay thu che do update (kiem tra khong thay doi, them file moi, sua file, xoa file).
    - Dong bo `progress.md`.

## Phase 25: Chuyen doi Dense Embedding sang google/embeddinggemma-300m qua Hugging Face API
71. **Cap nhat cau hinh & Retrieval Service**:
    - Them `HF_EMBEDDING_MODEL` vao `local_paths.json`.
    - Dinh nghia `get_dense_embedding_model` trong `backend/services/retrieval.py` su dung `HuggingFaceEndpointEmbeddings(model="google/embeddinggemma-300m")`.
72. **Refactor Backend & Loai bo Legacy**:
    - Cap nhat `backend/main.py` goi `get_dense_embedding_model`, dam bao event SSE `Dense Embedding: loaded` hoat dong chuan xac.
    - Xoa bo toan bo tham chieu den `sentence-transformers` va `all-MiniLM-L12-v2`.
    - Loai bo `sentence-transformers` khoi `requirements.txt`.
73. **Cap nhat Script Indexing (`index_docs.py`)**:
    - Chuyen dense vector size tu 384 len 768 trong Qdrant collection config.
    - Su dung `dense_model.embed_documents` theo batch (size 32) de toi uu thoi gian goi Hugging Face API.
74. **Thuc thi Index lai toan bo & Kiem thu**:
    - Chay `python index_docs.py --mode reset --export-chunks chunks_output` de rebuild vector database voi dense vector 768 chieu va cap nhat chunk files.
    - Kiem thu khoi dong backend SSE init-stream xac nhan `Dense Embedding: loaded`.
    - Kiem thu truy van RAG (search & rerank) voi vector moi.
    - Dong bo `progress.md`.

## Phase 26: He thong hoa va toi uu bo do toc do/thoi gian (StreamMetricsTracker)
75. **Xay dung StreamMetricsTracker (`backend/utils/metrics.py`)**:
    - Su dung `time.perf_counter()` thay the `time.time()` cho phep do chinh xac microsecond.
    - Phân chia ro rang cac mốc: TTFT, Prompt Processing Time, Generation Time, Tool Execution Time.
    - Tu dong gom `usage_metadata` (input_tokens, output_tokens) va format thong diep stats.
76. **Refactor ham stream_query (`backend/main.py`)**:
    - Tich hop `StreamMetricsTracker` vao vong lap `agent.astream`.
    - Loai bo cac bien tinh delta thu cong (`current_time - last_chunk_time`, `in_llm_generation`, etc.).
77. **Kiem thu & Ghi nhan**:
    - Kiem thu stream SSE qua script test, xac nhan do chinh xac va format thong so stats.
    - Dong bo `progress.md`.

## Phase 27: Tách biệt LLM Call quyết định Tool và LLM Call sinh kết quả với 2 Prompt độc lập
78. **Thiết kế 2 System Prompt riêng biệt (`backend/main.py`)**:
    - Dựng `TOOL_ROUTING_SYSTEM_PROMPT` chuyên trách phân tích ý định, điều phối và quyết định gọi tool (`search_general_knowledge`, `search_telecom_packages`, `rewrite_query_tool`), loại bỏ hoàn toàn các yêu cầu về format và ràng buộc trả lời.
    - Dựng `FINAL_RESPONSE_SYSTEM_PROMPT` chuyên trách tổng hợp câu trả lời cuối cùng từ dữ liệu tra cứu, tuân thủ nghiêm ngặt các ràng buộc: dùng kết quả tra cứu, không bình luận, không suy diễn, tránh rephrase, giữ cấu trúc format tài liệu gốc (bảng/danh sách), bao gồm đầy đủ thông tin.
79. **Cấu hình Tool Return Direct & Quản lý Ngữ cảnh (`backend/main.py`)**:
    - Thiết lập `return_direct=True` cho `search_general_knowledge` và `search_telecom_packages` để kết thúc Agent ngay khi hoàn thành tra cứu.
    - Giữ `return_direct=False` cho `rewrite_query_tool` để tiếp tục vòng lặp quyết định tool tra cứu.
    - Thu thập dữ liệu kết quả tra cứu (`retrieved_context`) và query đã làm rõ.
80. **Thực thi 2 lần gọi LLM riêng biệt trong `stream_query` (`backend/main.py`)**:
    - **Lần gọi 1 (Tool Selection & Routing)**: Chạy `agent.astream()` với `TOOL_ROUTING_SYSTEM_PROMPT`. Stream thinking và tool logs. Nếu là lời chào hỏi (không gọi tool), stream câu trả lời trực tiếp và hoàn tất.
    - **Lần gọi 2 (Final Response Synthesis)**: Nếu có dữ liệu tra cứu, gọi `llm.astream()` độc lập với `FINAL_RESPONSE_SYSTEM_PROMPT` và dữ liệu tra cứu. Stream câu trả lời cuối cùng thỏa mãn đầy đủ các ràng buộc.
    - Đo lường chính xác các chỉ số hiệu năng qua `StreamMetricsTracker`.
81. **Kiểm thử toàn diện & Cập nhật tiến độ**:
    - Kiểm thử kịch bản tra cứu gói cước, kiến thức chung, câu hỏi tiếp nối và chào hỏi xã giao.
    - Đồng bộ `agent_structure.md`, `workflow.md` và `progress.md`.

## Phase 28: Loại bỏ Rewrite Tool & Tích hợp Đánh giá Tương đồng Lịch sử bằng TypeSafe Jev với Cập nhật Harmonic Bridge
82. **Loại bỏ Rewrite Query Tool**: Xóa `RewriteQueryArgs`, tool `rewrite_query_tool`, và toàn bộ tham chiếu tới rewrite trong prompt.
83. **Mô hình hóa Message Lịch sử**: Lưu trữ hội thoại theo lượt (Message = User Query + Agent Output + Tool Output nếu có) cùng ma trận tương đồng lịch sử `r_ij`.
84. **Xây dựng History Scorer với TypeSafe Jev**: Lấy tối đa 10 message gần nhất, truyền vị trí tương quan và prompt ưu tiên các từ ngữ quy chiếu ngữ cảnh ("phần trên", "thứ 2", "trước đó"...) để tính $d_i$.
85. **Cài đặt công thức cập nhật Harmonic Bridge**:
    - $d_{bridge\_ij} = \frac{2 \cdot d_i \cdot r_{ij}}{d_i + r_{ij}}$
    - $u_i = a \cdot d_i + (1 - a) \cdot \text{avg}_{j \neq i}(d_{bridge\_ij})$ với $a = 0.5$.
    - Lưu lại $u_i$ làm $r_{ij}$ cho các query sau.
86. **Lọc Ngưỡng Score 0.7 & Đưa vào Context**: Các message đạt $u_i \ge 0.7$ được đưa vào context cho LLM kèm thứ tự tương quan và điểm tương đồng.
87. **Cập nhật System Prompts**:
    - `TOOL_ROUTING_SYSTEM_PROMPT`: Đổi bắt buộc gọi tool thành bắt buộc có context tra cứu (từ lịch sử hoặc tool). Nếu đã đủ thông tin từ lịch sử thì không cần gọi tool, nếu chưa có hoặc thiếu thì phải gọi tool đúng 1 lần.
    - `FINAL_RESPONSE_SYSTEM_PROMPT`: Sử dụng dữ liệu tra cứu từ cả tool và ngữ cảnh lịch sử liên quan để trả lời.
88. **In Debug Info ra phần Thinking**: In ngắn gọn số lượng message được đánh giá, danh sách số thứ tự message và các điểm $d_i$, $r_{ij}$, $u_i$.
89. **Kiểm thử toàn trình & Cập nhật Tiến độ**: Kiểm thử với các kịch bản tiếp nối ngữ cảnh và câu hỏi mới độc lập, đồng bộ `agent_structure.md` và `progress.md`.

## Phase 29: Tích hợp Intent Resolver Tool xử lý câu hỏi mơ hồ / không chắc chắn
90. **Thiết kế Tool `resolve_intent`**: Xây dựng Pydantic schema `ResolveIntentArgs` và tool thực hiện 3 bước:
    - Bước 1 (Hypotheses): Tạo danh sách các cách hiểu hợp lý (nghĩa đen và nghĩa dựa trên ngữ cảnh).
    - Bước 2 (Evidence Evaluation): Đối chiếu từng cách hiểu với query, lịch sử hội thoại và trạng thái tác vụ.
    - Bước 3 (Decision): Chọn cách hiểu đủ căn cứ, hoặc trả về nhiều khả năng, hoặc đề xuất câu hỏi làm rõ ngắn.
91. **Tích hợp vào Agent Routing**: Thêm tool vào `create_agent` với `return_direct=False`, lượt gọi tối đa 1 lần trong `tool_call_limits`.
92. **Cập nhật System Prompts**:
    - `TOOL_ROUTING_SYSTEM_PROMPT`: Thêm hướng dẫn gọi `resolve_intent` khi gặp câu hỏi mơ hồ/thiếu chủ ngữ mà lịch sử có nhiều thực thể, và hướng dẫn hành động tiếp theo sau khi có decision.
    - `FINAL_RESPONSE_SYSTEM_PROMPT`: Tiếp nhận kết quả phân tích hypothesis từ Lần 1 (nếu có) để tổng hợp câu trả lời theo đúng quyết định.
93. **Kiểm thử toàn trình & Cập nhật Tiến độ**: Kiểm thử kịch bản câu hỏi mơ hồ (cần làm rõ hoặc phân tích đa nghĩa) và câu hỏi bình thường, đồng bộ `agent_structure.md` và `progress.md`.

## Phase 30: Chuẩn hóa & Đồng bộ agent_structure.md
94. **Rà soát nội dung outdate trong `agent_structure.md`**: Cập nhật LLM model sang `openai/gpt-oss-20b:fastest`, bổ sung tham số `cycle_days_min / max` cho `search_telecom_packages`, cập nhật output `search_general_knowledge`.
95. **Bổ sung các thành phần mới**: Thêm điều kiện kích hoạt Call 2 và mục `5. Đánh giá tương đồng lịch sử (History Scoring & Harmonic Bridge)`. Giữ nguyên 100% cấu trúc và phong cách tài liệu.
96. **Đồng bộ tài liệu**: Cập nhật `progress.md` và `workflow.md`.

## Phase 31: Chuẩn hóa & Cập nhật .gitignore
97. **Cập nhật file .gitignore**: Bổ sung bỏ qua AI Agent metadata, thư mục chunks_output, cache trạng thái index docs/file_state.json, các file log/output text tạm thời và cache code quality.
98. **Xác nhận trạng thái Git & Đồng bộ tiến độ**: Kiểm tra `git status`, đảm bảo repo sạch sẽ và cập nhật `progress.md`.

## Phase 32: Tối ưu hóa định dạng hiển thị Relevance trên Frontend
99. **Cập nhật format debug_text trong HistoryScorer**: Đổi sang format `History context: {m} messages` và `Msg {id} (-{diff}): {score:.2f}`, ưu tiên tin nhắn gần nhất và ngắt dòng chuẩn Markdown.
100. **Kiểm thử & Đồng bộ tiến độ**: Xác nhận kết quả test format và cập nhật `progress.md`.

## Phase 33: Lọc Message Vượt Ngưỡng, Xóa Thẻ Think Thừa & Hiển Thị Tên Model Khởi Động
101. **Lọc và sắp xếp relevance**: Chỉ hiển thị các tin nhắn đạt ngưỡng $u_i \ge 0.7$, sắp xếp theo thứ tự thời gian từ lâu nhất đến gần nhất.
102. **Khử thẻ `<think>` thừa**: Đồng bộ trạng thái `in_thinking = True` và lọc thẻ `<think>` ở cả backend và frontend.
103. **Hiển thị tên model khi khởi động**: Gửi tên model chi tiết từ backend và format dạng `<Component>: <Model Name>.  Loaded.` trên frontend.
104. **Kiểm thử & Đồng bộ tài liệu**: Chạy test xác nhận và cập nhật `progress.md`.

## Phase 34: Refactoring Architecture & Tái Cấu Trúc Mã Nguồn Chuẩn Hóa
105. **Tách tầng Core & State (`backend/core/state.py`)**: Đóng gói `AppState`, `SessionManager` và logic `lifespan` / `load_models_background`.
106. **Tách tầng Prompts (`backend/prompts/`)**: Module hóa `routing.py`, `final_response.py`, và `intent_resolver.py`.
107. **Tách tầng Tools (`backend/tools/`)**: Module hóa `schemas.py`, `general_knowledge.py`, `telecom_packages.py`, `intent_resolver.py`.
108. **Xây dựng Agent Orchestrator Service (`backend/services/agent_orchestrator.py`)**: Điều phối 2 Call, tool state binding, SSE event generator và metrics tracker.
109. **Tách tầng API (`backend/api/`)**: Tạo `routes.py` và `schemas.py` chứa các endpoints `/api/query`, `/api/init-stream`, `/api/health`.
110. **Tinh gọn `backend/main.py`**: Biến `main.py` thành Composition Root gọn gàng (~60 dòng).
111. **Kiểm thử toàn diện E2E**: Chạy smoke test, API streaming test, đảm bảo hoạt động chính xác 100%.
112. **Cập nhật tài liệu**: Đồng bộ `agent_structure.md`, `progress.md` và `workflow.md`.


















