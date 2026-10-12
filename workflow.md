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
