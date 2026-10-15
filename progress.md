# Progress

- [x] Khởi tạo Workflow (workflow.md và progress.md).
- [x] Khám phá Dữ liệu.
- [x] Viết Script Tool Calling.
- [x] Thực thi Script.
- [x] Đánh giá.

## Phase 2: Nâng cấp Tool Calling (Tìm kiếm Nâng cao)
- [x] Cập nhật Tool Search: Trích xuất Data/Price/Duration, fuzzy name matching, Alias handling.
- [x] Thử nghiệm Nâng cao (4 test cases thành công mỹ mãn).
- [x] Hoàn thiện tài liệu và theo dõi tiến độ.

## Phase 3: Tích hợp Hệ thống (Routing & Unified Tool Calling)
- [x] Tích hợp Intent Routing (`classify_intent_llm`) vào `main.py`.
- [x] Bọc logic Qdrant và JSON search thành `@tool` của LangChain.
- [x] Khởi chạy tool thủ công và gom Context thành Unified Prompt.
- [x] Cập nhật kết quả vào tài liệu.

## Phase 4: Dọn dẹp
- [x] Xóa thư mục `scratch/` và các file test (`test_tool_calling.py`).

## Phase 5: Debug & T?i uu Streaming
- [x] Kh?c ph?c l?i chunking b?ng bi?u (Markdown Table).
- [x] S?a l?i parse th? <think> khi?n UI b? treo.
- [x] Kh?c ph?c l?i tr�n Token Context Limit (8192) khi g?i Tool.
- [x] T?i uu c?t chu?i b?ng bi?u (Markdown Table Splitter) gi? nguy�n Header.
- [x] N�ng context size l�n 16384 tokens v� n?i l?ng truncate limit l�n 30000 k� t?.
  
## Phase 6: Fix Frontend Freeze  
- [x] Ph�n t�ch log SSE x�c d?nh nguy�n nh�n (Empty token clear systemStatus).  
- [x] S?a l?i App.jsx kh�ng clear status v?i token r?ng. 
  
## Phase 7: Fix Markdown Table Formatting  
- [x] B? sung thu vi?n remark-gfm v�o frontend.  
- [x] T�ch h?p remarkGfm v�o ReactMarkdown plugins d? render b?ng d�ng d?nh d?ng.  
- [x] Th�m style CSS co b?n cho b?ng. 

## Phase 8: Refactor Configuration and UI Logging
- [x] Tao file ports.json de quan ly port frontend/backend.
- [x] Cap nhat 
un_app.bat doc port tu ports.json va tu dong kill process cu.
- [x] Xoa cac log hien thi Khoi tao he thong, Dang sinh cau tra loi, Hoan tat goi tool thua thai. Them log thoi gian khoi tao.
- [x] Format lai log [GOI TOOL] theo dang ham unction(arg=...) voi OUTPUT doc lap trong the  ` , tang limit length len 1500.
  
## Phase 9: Don dep du an  
- [x] Da xoa cac file patch, test, error log, ket qua chunking va output sinh ra trong qua trinh phat trien (patch_*.py, test_*.py, langchain_chunks_*.md, output.txt, table_output.txt, debug_stream.py, evaluation.md, scratch/). 

## Phase 10: Thay the Reranker bang Jev (TypeSafe)
- [x] Cai dat thu vien `typesafe-sdk`.
- [x] Xay dung class `JevReranker` su dung `Noul` theo TypeSafe Reranking Cookbook tai `backend/services/retrieval.py`.
- [x] Tich hop co che doc `TYPESAFE_API_KEY` va `RERANKER_MODEL` linh hoat tu Environment hoac `local_paths.json`.
- [x] Thuc hien kiem thu khoi tao va kiem tra co che bat loi / xac thuc qua script test.
- [x] Chay kiem thu live Jev Reranker: 3 doan van ban mau dat do phan giai diem xuat sac (0.98 cho doan lien quan, 0.06 & 0.02 cho doan khong lien quan), do tre 0.49s.
- [x] Chay kiem thu toan trinh Hybrid Search + Jev Rerank tren Qdrant knowledge base: hoan tat trong 2.14s, xep hang chuan xac cac tai lieu lien ket ngan hang voi vi dien tu.
- [x] Bo sung logic loc ket qua theo nguong diem score >= 0.6: da loc thanh cong chi giu lai 3 tai lieu phu hop cao nhat (score >= 0.87), loai bo cac tai lieu < 0.6.

## Phase 11: Thay the LLM Local bang IBM Granite qua Hugging Face Router
- [x] Cau hinh thong tin `HF_TOKEN`, `HF_MODEL_NAME`, `HF_BASE_URL` trong `local_paths.json`.
- [x] Chay kiem thu doc lap (smoke test): xac nhan ket noi Hugging Face Router (`https://router.huggingface.co/v1`), model `ibm-granite/granite-4.2-3b:deepinfra` ho tro day du streaming reasoning (thinking) va tool calling.
- [x] Cap nhat `backend/services/llm.py` tich hop remote router, bo qua tien trinh local llama-server khi co `HF_TOKEN`.
- [x] Chay kiem thu toan trinh SSE streaming tren `backend/main.py`: agent tu dong suy luan (thinking) -> goi tool tra cuu kien thuc -> tra loi nguoi dung muot ma, TTFT 0.89s.

## Phase 12: Rerank voi Parent Chunk thay vi Child Chunk
- [x] Chuyen doi logic `search_and_rerank` trong `backend/services/retrieval.py`: trích xuất `doc_id` của 20 child chunks từ Qdrant, deduplicate, fetch parent docs từ store rồi rerank trực tiếp trên `page_content` của parent chunk.
- [x] Kiem thu thuc te: Parent chunk chua tron ven noi dung bang bieu phi giup Jev cham diem dat **0.9800** tuyet doi (thay vi dao dong quanh 0.59 ~ 0.70 nhu child chunk bi dut nua dau). Cac chunk khong lien quan roi xuong 0.37 ~ 0.02.
- [x] Xac nhan do on dinh 5 lan lien tiep: ca 5 lan deu dat diem 0.9800 on dinh 100%, khong con hien tuong chap chon.

## Phase 13: Refactor LLM Service va don dep Legacy code
- [x] Doi ten ham `get_llama_cpp_model` thanh `get_llm_model` trong `backend/services/llm.py`, giu alias cho backward compatibility.
- [x] Xoa bo toan bo class `LlamaServerManager`, socket health check port 8080 va cac import he thong khong con su dung (`subprocess`, `socket`, `time`, `atexit`, `urllib.request`).
- [x] Cap nhat import va khoi tao `get_llm_model` trong `backend/main.py`.
- [x] Dong bo thong so ky thuat ve LLM moi (`ibm-granite/granite-4.2-3b:deepinfra`) va Jev Reranker vao `agent_structure.md`.

## Phase 14: Kich hoat do toc do Token qua stream_usage chuan API
- [x] Kich hoat `stream_usage=True` trong `ChatDeepSeek` tai `backend/services/llm.py`.
- [x] Cap nhat logic format `stats_msg` trong `backend/main.py`: in day du toc do Prompt va Gen neu API tra ve token; neu khong co du lieu token se tu dong an 2 thong so do (chi hien TTFT va Total).
- [x] Kiem thu thuc te: HF Router tra ve `usage_metadata` chuan xac, he thong do va in ra toc do Prompt: ~1940 t/s va Gen: ~259 t/s.

## Phase 15: Tra ve list chunks cho search_general_knowledge va rut gon output thinking
- [x] Cap nhat `global_search_general_knowledge` va `search_general_knowledge` tra ve `List[Dict[str, Any]]` thay vi noi chuoi string, duoc sap xep theo score tu cao xuong thap.
- [x] Dinh dang lai output trong khoi `thinking`: dong dau in `Tổng số chunk: N`, moi chunk ben duoi chi in 2 dong dau tien kem thong tin Nguon va Score.
- [x] Kiem thu thuc te: Khoi thinking hien thi gon gang, LLM van tiep nhan day du du lieu qua ToolMessage va tra loi chinh xac.

## Phase 16: Thay the LLM model bang Qwen/Qwen3-8B:nscale
- [x] Cap nhat cau hinh `HF_MODEL_NAME` sang `Qwen/Qwen3-8B:nscale` trong `local_paths.json` va gia tri fallback trong `backend/services/llm.py`.
- [x] Kiem thu doc lap: Model stream suy luan (thinking) tot (718 ky tu), tra ve `stream_usage` day du, goi tool chinh xac.
- [x] Kiem thu Agent toan trinh: Agent hieu cau hoi ("gói data 1 năm"), tu dong map chu ky 360 ngay, goi tool tra cuu va tra ve ket qua chuan xac.
- [x] Dong bo hoa `agent_structure.md`, `workflow.md` va `progress.md`.

## Phase 17: Fix loi khoi thinking bi tran ra output khi goi tool
- [x] Sua `backend/main.py`: Khong dong the `</think>` khi chunk content chi la khoang trang (`\n\n`) truoc tool call hoac khi dang co `tool_calls`; giu duy nhat mot khoi thinking lien mach xuyen suot luong suy luan va goi tool.
- [x] Sua `frontend/src/App.jsx`: Nang cap `parseMessage` bóc tách toàn bộ các khối `<think>...</think>` (kể cả khi có nhiều khối), gom vào `ThinkingBlock`, đảm bảo content của câu trả lời không bao giờ bị rò rỉ thẻ think hay log tool.
- [x] Kiem thu toan dien: Chay test SSE streaming voi luong goi tool cua model Qwen3, xac nhan chi co dung 1 khoi thinking va output content hoan toan sach dep.

## Phase 18: Ho tro render the br xuong dong trong bang Markdown va van ban
- [x] Sua `frontend/src/App.jsx`: Xay dung ham `renderWithLineBreaks` va `markdownComponents` cho `ReactMarkdown` (ap dung cho ca `td`, `th`, `p`, `li`) de bien the `<br>` trong chuoi thanh component `<br />` JSX thuc thu ma khong can cai them thu vien ngoai.
- [x] Sua `frontend/src/App.css`: Bo sung `vertical-align: top;` cho cac o `th`, `td` giup du lieu bang nhieu dong can deu dep mat.
- [x] Kiem thu render SSR: Chay test render bang voi chuoi du lieu goc tu bieu phi VNPT Money, xac nhan da bien thanh cac the `<br/>` HTML hop le, khong con bi lo the `<br>` tho.

## Phase 19: Cap nhat so chunk toi da lay ve None, gap doi max token va do dai chunk
- [x] Sua `backend/services/retrieval.py`: Thiet lap gia tri mac dinh `top_k: int | None = None` trong `search_and_rerank` de lay toan bo cac parent chunk vuot nguong `score_threshold >= 0.6`.
- [x] Sua `backend/services/llm.py`: Nâng `max_tokens` mac dinh cua LLM tu 8192 len 16384 tokens (gap doi).
- [x] Sua `backend/main.py`: Nâng gioi han tong do dai noi dung cac chunk dua vao query tu 30000 len 60000 ky tu (gap doi tuong ung).
- [x] Dong bo `agent_structure.md`, `workflow.md` va `progress.md`.

## Phase 20: Bo gioi han max_tokens cua LLM
- [x] Sua `backend/services/llm.py`: Dat `max_tokens = None` mac dinh cho `ChatDeepSeek`, loai bo han che so token sinh toi da o phia client, cho phep mo hinh tu do sinh cau tra loi va suy luan theo kich thuoc context cua server.
- [x] Kiem thu doc lap: Xac nhan khoi tao model tra ve `max_tokens: None` va invoke thanh cong tren Hugging Face Router.
- [x] Dong bo `agent_structure.md`, `workflow.md` va `progress.md`.

## Phase 21: Chuyen model sang Qwen/Qwen3.5-9B:deepinfra
- [x] Kiem thu `Qwen/Qwen3-8B:fastest`: Router bao loi `400 model_not_supported` do model `Qwen3-8B` khong ton tai tren HF Router.
- [x] Kiem thu `Qwen/Qwen3.5-9B:deepinfra`: Ket noi thanh cong HTTP 200, ho tro native tool calling on dinh.
- [x] Cap nhat cau hinh: Chuyen `HF_MODEL_NAME` sang `Qwen/Qwen3.5-9B:deepinfra` trong `local_paths.json` va gia tri fallback mac dinh tai `backend/services/llm.py`.
- [x] Dong bo tai lieu: Cap nhat `agent_structure.md`, `workflow.md` va `progress.md`.

## Phase 22: Toi uu trai nghiem nap mo hinh & luong khoi tao
- [x] Xay dung Init Progress API (`backend/main.py`):
  - Bo sung co che tracking tien trinh nạp từng thành phần: Qdrant & FileStore, Dense Embedding (`all-MiniLM-L12-v2`), Sparse Embedding (`Qdrant/bm25`), Reranker (`Jev TypeSafe`), và LLM (`Qwen/Qwen3.5-9B:deepinfra`).
  - Cung cap SSE endpoint `/api/init-stream` truyen su kien thoi gian thuc (`loading`, `loaded`, `complete`) va endpoint `/api/health` dong bo trang thai `is_ready`.
- [x] Cap nhat giao dien khoi tao & bong bong chat rieng (`frontend/src/App.jsx`, `frontend/src/App.css`):
  - Bong bong chat khoi tao he thong: hien thi rieng biet dau tien, cap nhat danh sach tich xanh `✅` khi tung thanh phan nap xong, khong bi gop vao cau tra loi query dau tien.
  - Loading indicator: hien thi thong tin chuan xac thanh phan dang nap (`init-loading-banner`).
  - Nhap truoc cau hoi: O input khong bi khoa khi dang nap, cho phep user go san cau hoi; nut Gui va su kien enter bi vo hieu hoa cho den khi he thong hoan tat nap.
- [x] Kiem thu toan trinh:
  - SSE init-stream phan hoi theo dung thu tu tung thanh phan khi cold-start.
  - Khi refresh trang, init-stream tra ve ngay lap tuc tat ca cac thanh phan da co trong bo nho kem event `complete`.
  - Query tra loi muot ma, khong con bi chen text loading vao noi dung bot tra loi.

## Phase 23: Toi gian hoa giao dien khoi tao & chuan hoa tieng Anh
- [x] Chuan hoa phia Backend (`backend/main.py`):
  - Chuyen toan bo ten cac thanh phan sang tieng Anh: `Knowledge Base`, `Dense Embedding`, `Sparse Embedding`, `Reranker`, `LLM`.
  - Rut gon cac thong bao status: `Connecting Knowledge Base...`, `Loading Dense Embedding...`, `Connecting LLM...`, va hoan tat bang `System ready.`.
- [x] Toi gian hoa phia Frontend (`frontend/src/App.jsx`, `frontend/src/App.css`):
  - Loai bo 100% emoji, the tieu de h3, font in dam, va cac ky tu thụt dòng `-`.
  - Hien thi bong bong khoi tao theo dang text thuan monospace, moi thanh phan mot dong: `<Component>: loaded`.
  - Footer banner thiet ke toi gian, placeholder tinh gon, khong mau me.
- [x] Kiem thu:
  - Vite build hoan tat khong loi (327ms).
  - Backend phan hoi SSE event dung dinh dang moi: `Knowledge Base: loaded`, `Dense Embedding: loaded`, `Sparse Embedding: loaded`, `Reranker: loaded`, `LLM: loaded`, `System ready.`.

## Phase 24: Hop nhat script indexing va convert du lieu voi 3 che do CLI
- [x] Cau hinh trang thai index (`backend/core/config.py`):
  - Dinh nghia `STATE_FILE` luu thong tin tai `file_state.json`.
  - Loai tru triet de cac file excel (`.xlsx`, `.xls`) va json (`.json`) khoi database vector.
- [x] Gop logic `convert_excel_to_json.py` vao `index_docs.py`:
  - Chuyen toan bo ham `excel_to_json` sang `index_docs.py` (bao toan format `pkg_xxx`, kieu du lieu gia tien, ma hoa UTF-8).
  - Xoa file doc lap `convert_excel_to_json.py`.
- [x] Cai dat 3 che do thuc thi qua command-line arguments:
  - `--mode reset` (hoac `--reset`): Xoa sach Qdrant collection, LocalFileStore va state file, sau do index lai tu dau toan bo 19 tai lieu markdown.
  - `--mode update` (hoac `--update`): So sanh MD5 hash tung file voi `file_state.json`, tu dong xu ly them moi, cap nhat (xoa chunk cu, nap chunk moi) va xoa bo (xoa khoi Qdrant va Store).
  - `--mode convert` (hoac `--convert`): Chuyen doi bang tinh `docs/goi_cuoc.xlsx` thanh `docs/goi_cuoc.json`.
- [x] Kiem thu toan dien ca 3 che do:
  - Kiem thu goi lenh khong tham so: Hien thi huong dan CLI ro rang.
  - Kiem thu che do convert: Chuyen doi thanh cong 20 goi cuoc sang file json chuan.
  - Kiem thu che do reset: Index thanh cong 19 tai lieu markdown, sinh `file_state.json` day du doc_ids va point_ids.
  - Kiem thu che do update: Xac nhan trang thai up-to-date (0 file thay doi), test thanh cong chu trinh tao moi -> sua noi dung -> xoa file thuc te.

## Phase 25: Chuyen doi Dense Embedding sang google/embeddinggemma-300m qua Hugging Face API
- [x] Cau hinh va tich hop model (`local_paths.json`, `backend/services/retrieval.py`):
  - Bo sung `HF_EMBEDDING_MODEL: "google/embeddinggemma-300m"` vao `local_paths.json`.
  - Xay dung ham `get_dense_embedding_model` khoi tao `HuggingFaceEndpointEmbeddings` (vector 768-dim), kem buoc warmup kiem tra ket noi API.
- [x] Refactor Backend & loai bo toan bo Legacy code (`backend/main.py`, `requirements.txt`):
  - Thay the viec khoi tao local `sentence-transformers` bang `get_dense_embedding_model`.
  - Bao toan luong SSE event cho frontend: emit `Loading Dense Embedding...` va `Dense Embedding: loaded`.
  - Loai bo hoan toan thu vien `sentence-transformers` khoi `requirements.txt` va toan bo import trong ma nguon.
- [x] Cap nhat script indexing (`index_docs.py`):
  - Nang kich thuoc dense vector collection trong Qdrant tu 384 len 768 chieu.
  - Toi uu embedding bang co che batching (`embed_documents` batch size 32 kem retry) thay vi goi don le, giam thoi gian indexing.
- [x] Thuc thi index lai toan bo & kiem thu:
  - Chay reset index thanh cong 19 file markdown, tao 19 file chunk voi ten sach dep trong `chunks_output/`.
  - Kiem thu background loader: Backend nap thanh cong ca 4 thanh phan `['Dense Embedding', 'Sparse Embedding', 'Reranker', 'LLM']`.
  - Kiem thu toan trinh Hybrid Search + Reranker: Truy van mau tra ve chuan xac 9 parent chunks voi diem score cao.

## Phase 26: He thong hoa va toi uu bo do toc do/thoi gian (StreamMetricsTracker)
- [x] Xay dung class `StreamMetricsTracker` (`backend/utils/metrics.py`):
  - Su dung `time.perf_counter()` dat do chinh xac microsecond, loai bo sai so dong bo gio OS tu `time.time()`.
  - Tach biet ro rang cac phase: TTFT, Prompt Processing, Generation Time, va Tool Latency.
  - Dong goi ham format chuoi thong ke `get_stats_message()` chuan SSE format.
- [x] Refactor ham `stream_query` (`backend/main.py`):
  - Thay the toan bo cac bien roi rac (`t_start`, `last_chunk_time`, `in_llm_generation`, `total_prompt_time`, `total_gen_time`) bang instance `metrics`.
  - Tich hop su kien `on_token()`, `update_usage()`, `on_tool_start()`, `on_tool_end()`, `stop()`.
- [x] Kiem thu thuc te:
  - Unit test tracker ca truong hop co goi tool va khong goi tool: phan chia phase chuan xac.
  - End-to-end test stream query voi LLM: TTFT 0.86s, Prompt 1891.4 t/s (1627t), Gen 79.9 t/s (192t), Total 3.26s.

## Phase 27: Tách biệt LLM Call quyết định Tool và LLM Call sinh kết quả với 2 Prompt độc lập
- [x] Thiết kế 2 System Prompt riêng biệt (`backend/main.py`):
  - `TOOL_ROUTING_SYSTEM_PROMPT`: Tập trung 100% vào việc phân tích câu hỏi, điều phối và quyết định gọi tool (`search_general_knowledge`, `search_telecom_packages`, `rewrite_query_tool`), không chứa các ràng buộc định dạng để tránh loãng sự chú ý khi trích xuất tham số.
  - `FINAL_RESPONSE_SYSTEM_PROMPT`: Tập trung 100% vào việc sinh câu trả lời cuối cùng dựa trên kết quả đã tra cứu, tuân thủ nghiêm ngặt các ràng buộc: dùng kết quả tra cứu, không bình luận, không suy diễn, tránh rephrase, giữ nguyên format bảng/danh sách từ tài liệu gốc, cung cấp đầy đủ thông tin.
- [x] Cấu hình Tool Return Direct & Quản lý Ngữ cảnh (`backend/main.py`):
  - Thiết lập `return_direct=True` cho `search_general_knowledge` và `search_telecom_packages` để dừng Agent ngay khi hoàn tất tra cứu.
  - Giữ `return_direct=False` cho `rewrite_query_tool` để Agent tiếp tục vòng lặp quyết định tool tra cứu sau khi làm rõ ngữ cảnh.
  - Tự động thu thập dữ liệu tra cứu (`retrieved_context`) và query đã làm rõ (`rewritten_query_holder`).
- [x] Thực thi 2 lần gọi LLM riêng biệt trong `stream_query` (`backend/main.py`):
  - **Lần gọi 1 (Tool Selection & Routing)**: Gọi `agent.astream()` với `TOOL_ROUTING_SYSTEM_PROMPT`. Stream thinking và tool logs. Trường hợp là lời chào hỏi xã giao (không gọi tool), stream trực tiếp câu trả lời và kết thúc.
  - **Lần gọi 2 (Final Response Synthesis)**: Khi có dữ liệu tra cứu, gọi `llm.astream()` độc lập không kèm tool schemas với `FINAL_RESPONSE_SYSTEM_PROMPT` và dữ liệu tra cứu. Stream câu trả lời cuối cùng tuân thủ toàn bộ các constraint.
  - Đồng bộ `StreamMetricsTracker` đo lường chính xác toàn bộ tiến trình.
- [x] Kiểm thử toàn trình (E2E Test):
  - Test gói cước (`Gói YOLO90`): Lần 1 gọi `search_telecom_packages`, Lần 2 tổng hợp dạng bảng Markdown chuẩn xác, không bình luận thêm (Total: 1.90s).
  - Test chào hỏi (`Xin chào bạn!`): Lần 1 nhận diện lời chào, phản hồi ngắn gọn lịch sự, không gọi tool, bỏ qua Lần 2 (Total: 0.70s).
  - Test tài liệu (`Phí chuyển tiền qua ví điện tử là bao nhiêu?`): Lần 1 gọi `search_general_knowledge`, Lần 2 trả lời sát nội dung trích xuất từ `thong_tin_chung.md`, không suy diễn.
- [x] Đồng bộ tài liệu: Cập nhật `agent_structure.md`, `workflow.md`, `progress.md`.

## Phase 28: Loại bỏ Rewrite Tool & Tích hợp Đánh giá Tương đồng Lịch sử bằng TypeSafe Jev với Cập nhật Harmonic Bridge
- [x] Loại bỏ hoàn toàn Rewrite Tool:
  - Xóa schema `RewriteQueryArgs` và tool `rewrite_query_tool` khỏi `backend/main.py`.
  - Loại bỏ hoàn toàn các prompt hướng dẫn/quy tắc rewrite khỏi `TOOL_ROUTING_SYSTEM_PROMPT` và `FINAL_RESPONSE_SYSTEM_PROMPT`.
- [x] Mô hình hóa Message Hội thoại:
  - Mỗi message lưu trữ: `user_query` + `tool_output` (nếu có) + `agent_output` cùng ID tuần tự trong `app_state.conversations`.
  - Quản lý ma trận tương đồng lịch sử đối xứng `r_matrix` trong `app_state.relevance_matrices`.
- [x] Xây dựng Service `HistoryScorer` (`backend/services/history_scorer.py`):
  - Tích hợp TypeSafe Jev (`system_one`, `Noul`) đánh giá tương đồng ngữ nghĩa.
  - Lấy tối đa 10 message gần nhất, truyền vị trí tương quan (`{k} message trước`) và prompt ưu tiên các từ ngữ quy chiếu ngữ cảnh ("phần trên", "thứ 2", "trước đó", "vừa rồi"...).
  - Chạy đánh giá song song qua `ThreadPoolExecutor` tối ưu độ trễ.
- [x] Cài đặt công thức cập nhật Harmonic Bridge:
  - $d_{bridge\_ij} = \frac{2 \cdot d_i \cdot r_{ij}}{d_i + r_{ij}}$
  - $u_i = a \cdot d_i + (1 - a) \cdot \text{avg}_{j \neq i}(d_{bridge\_ij})$ với $a = 0.5$.
  - Lưu lại $u_i$ làm $r_{ij}$ cho các query tiếp theo trong session.
- [x] Lọc Ngưỡng Score >= 0.7 & Cung cấp Ngữ cảnh cho LLM:
  - Các message đạt ngưỡng được đưa vào context kèm thứ tự tương quan và điểm tương đồng.
  - Cập nhật prompt: Ngữ cảnh lịch sử là ngữ cảnh tra cứu hợp lệ. Nếu đủ thông tin, LLM trả lời trực tiếp mà không gọi tool; nếu chưa có hoặc thiếu, bắt buộc gọi tool 1 lần.
- [x] In ngắn gọn Debug Info ra Frontend Thinking:
  - Xuất số lượng message đánh giá, danh sách số thứ tự message kèm $d_i$, $r_{ij}$ và $u_i$.
- [x] Kiểm thử toàn trình (Integration Test):
  - Test 1 (Câu hỏi mới): 0 message lịch sử -> gọi tool `search_telecom_packages`.
  - Test 2 (Câu hỏi nối tiếp 'trong các gói trên, gói nào rẻ nhất?'): Jev chấm $d_1 = 0.91 \ge 0.7$ -> LLM trả lời trực tiếp từ ngữ cảnh, không gọi tool tra cứu.
  - Test 3 (Câu hỏi nối tiếp 'thế còn gói thứ 2?'): Jev chấm $d_1, d_2 \ge 0.7$, cập nhật $u_i \approx 0.93$ -> LLM trả lời trực tiếp.
  - Test 4 (Câu hỏi đổi chủ đề 'Hướng dẫn liên kết ngân hàng'): $d_i \approx 0.04 - 0.09$, $u_i < 0.7$ (không đạt) -> LLM gọi tool `search_general_knowledge`.
- [x] Đồng bộ tài liệu: Cập nhật `agent_structure.md`, `workflow.md`, `progress.md`.

## Phase 29: Tích hợp Intent Resolver Tool xử lý câu hỏi mơ hồ / không chắc chắn
- [x] Thiết kế Schema `ResolveIntentArgs` & Tool `resolve_intent` (`backend/main.py`):
  - Nhận tham số `query` và `uncertainty_reason`.
  - Thực thi quy trình chuẩn 3 bước:
    1. *Hypotheses*: Liệt kê các cách hiểu hợp lý (nghĩa đen và ngữ cảnh lịch sử).
    2. *Evidence-based Evaluation*: Đối chiếu bằng chứng từ câu hỏi, lịch sử, logic tác vụ và đánh giá độ tin cậy.
    3. *Decision*: Ra quyết định chọn cách hiểu tối ưu, trình bày nhiều khả năng, hoặc đề xuất câu hỏi làm rõ ngắn.
- [x] Tích hợp vào Agent Routing (Lần 1):
  - Thêm tool vào `create_agent` với `return_direct=False`, giới hạn gọi tối đa 1 lần trong `tool_call_limits`.
  - Nếu xác định rõ ý định: Agent tiếp tục gọi tool tra cứu tương ứng (`search_telecom_packages` hoặc `search_general_knowledge`).
  - Nếu kết luận cần làm rõ: Agent dừng tra cứu và phản hồi câu hỏi làm rõ ngắn trực tiếp cho người dùng.
- [x] Tối ưu hóa Luồng 2 Lần gọi LLM (Call 1 & Call 2):
  - Chỉ kích hoạt Call 2 khi có dữ liệu tra cứu từ search tools (`has_search_context`). Tránh hiện tượng lặp lại câu hỏi làm rõ khi chỉ gọi `resolve_intent`.
  - Tích hợp kết quả phân tích ý định vào `context_blocks` của Call 2 và lưu trữ vào lịch sử hội thoại.
- [x] Cập nhật System Prompts:
  - `TOOL_ROUTING_SYSTEM_PROMPT`: Bổ sung nguyên tắc xử lý khi không chắc chắn và hướng dẫn gọi `resolve_intent`.
  - `FINAL_RESPONSE_SYSTEM_PROMPT`: Hướng dẫn trình bày đa chiều nếu kết quả phân tích ý định chỉ ra nhiều khả năng.
- [x] Kiểm thử toàn trình (Integration & Live API Test):
  - Test 1 (Câu hỏi mơ hồ 'Cái đó dùng như thế nào và bao nhiêu tiền?'): LLM kích hoạt `resolve_intent`, phân tích 2 hypotheses (nghĩa đen vs ngữ cảnh), đối chiếu bằng chứng (đều độ tin cậy Thấp do thiếu thông tin) -> Đưa ra câu hỏi làm rõ ngắn gọn mà không gọi tool tra cứu thừa.
  - Test 2 (Câu hỏi tường minh 'Gói YOLO90 giá bao nhiêu và có bao nhiêu GB data một ngày?'): LLM nhận diện ý định rõ ràng, không gọi `resolve_intent`, gọi thẳng `search_telecom_packages` và trả kết quả dạng bảng chuẩn xác.
  - Test 3 (Đa ngữ cảnh tiếp nối 'gói đó có ưu đãi gì khác không?'): LLM nhận diện ngữ cảnh từ gói cước vừa liệt kê và tra cứu ưu đãi qua `search_general_knowledge`.
- [x] Đồng bộ tài liệu: Cập nhật `agent_structure.md`, `workflow.md`, `progress.md`.

## Phase 30: Chuẩn hóa & Đồng bộ agent_structure.md
- [x] Rà soát và cập nhật nội dung outdate trong `agent_structure.md`:
  - Cập nhật LLM model sang `openai/gpt-oss-20b:fastest` (đang cấu hình trong `local_paths.json`).
  - Bổ sung tham số chu kỳ ngày `cycle_days_min / max` cho tool `search_telecom_packages`.
  - Cập nhật định dạng output danh sách chunk (kèm nguồn và score) cho `search_general_knowledge`.
  - Bổ sung điều kiện kích hoạt Call 2 (`has_search_context`) tại mục System Prompt Lần 2.
  - Bổ sung mục `5. Đánh giá tương đồng lịch sử (History Scoring & Harmonic Bridge)` chi tiết cơ chế Jev, Harmonic Bridge $u_i$, và ngưỡng lọc $\ge 0.7$.
  - Giữ nguyên 100% cấu trúc, phong cách và định dạng gốc của file.

## Phase 31: Chuẩn hóa & Cập nhật .gitignore
- [x] Cập nhật toàn diện file `.gitignore`:
  - Bổ sung bỏ qua AI Agent metadata (`.agents/`, `skills-lock.json`, `.gemini/`, `.claude/`, `.cursor/`).
  - Bổ sung bỏ qua thư mục chunking thử nghiệm (`chunks_output/`) và cache trạng thái index vector (`docs/file_state.json`, `file_state.json`).
  - Bổ sung bỏ qua các file test/output tạm thời (`test_out*.txt`, `*output.txt`, `*.tmp`, `*.bak`).
  - Bổ sung cache kiểm thử code quality (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`) và frontend Vite (`frontend/.vite/`, `.eslintcache`).
  - Kiểm tra trạng thái Git: Xác nhận repository sạch sẽ, chỉ còn lại các file source code và docs chuẩn cần track.
