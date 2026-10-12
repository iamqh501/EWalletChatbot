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
- [x] Cap nhat un_app.bat doc port tu ports.json va tu dong kill process cu.
- [x] Xoa cac log hien thi Khoi tao he thong, Dang sinh cau tra loi, Hoan tat goi tool thua thai. Them log thoi gian khoi tao.
- [x] Format lai log [GOI TOOL] theo dang ham unction(arg=...) voi OUTPUT doc lap trong the  ` , tang limit length len 1500.
  
## Phase 9: Don dep du an  
- [x] Da xoa cac file patch, test, error log, ket qua chunking va output sinh ra trong qua trinh phat trien (patch_*.py, test_*.py, langchain_chunks_*.md, output.txt, table_output.txt, debug_stream.py, evaluation.md, scratch/). 
