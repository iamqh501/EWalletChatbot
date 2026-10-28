from typing import Optional, List
from backend.core.state import session_manager
from backend.tools.schemas import TransactionRecord, TransactionHistoryResult, ToolResultItem

PLACEHOLDER_TRANSACTIONS: List[TransactionRecord] = [
    TransactionRecord(
        date="20/10/2026 15:42",
        action="Chuyển tiền",
        amount="250.000 đ",
        target="NGUYEN VAN A (STK: 190367891234 - Techcombank)",
        content="Chuyen tien an trua",
        type="transfer",
        description="Ngày 20/10/2026: Chuyển 250.000 đ tới NGUYEN VAN A (STK: 190367891234 - Techcombank). Nội dung: Chuyen tien an trua."
    ),
    TransactionRecord(
        date="19/10/2026 09:15",
        action="Nhận tiền",
        amount="1.500.000 đ",
        target="TRAN THI B (Ví VNPT Money - 0987***567)",
        content="Thanh toan tien phong tro thang 10",
        type="receive",
        description="Ngày 19/10/2026: Nhận 1.500.000 đ từ TRAN THI B (Ví VNPT Money - 0987***567). Nội dung: Thanh toan tien phong tro thang 10."
    ),
    TransactionRecord(
        date="18/10/2026 18:30",
        action="Thanh toán hóa đơn",
        amount="85.000 đ",
        target="Cửa hàng tiện lợi Circle K",
        content="Thanh toan mua hang tien loi QR",
        type="payment",
        description="Ngày 18/10/2026: Chuyển (Thanh toán) 85.000 đ tới Cửa hàng tiện lợi Circle K. Nội dung: Thanh toan mua hang tien loi QR."
    ),
    TransactionRecord(
        date="15/10/2026 11:20",
        action="Nhận tiền",
        amount="500.000 đ",
        target="LE VAN C (STK: 0011004321987 - Vietcombank)",
        content="Tra tien mua sach",
        type="receive",
        description="Ngày 15/10/2026: Nhận 500.000 đ từ LE VAN C (STK: 0011004321987 - Vietcombank). Nội dung: Tra tien mua sach."
    ),
    TransactionRecord(
        date="12/10/2026 08:05",
        action="Nạp tiền điện thoại",
        amount="97.600 đ",
        target="Thuê bao VinaPhone 0912***789",
        content="Nap tien dien thoai (Mệnh giá 100.000 đ, chiết khấu 2.4%)",
        type="topup",
        description="Ngày 12/10/2026: Chuyển (Nạp tiền điện thoại) 97.600 đ tới Thuê bao VinaPhone 0912***789 (Mệnh giá 100.000 đ, chiết khấu 2.4%)."
    )
]


def execute_get_transaction_history(
    session_id: str,
    user_consent: Optional[bool] = None,
    query: Optional[str] = None
) -> ToolResultItem:
    """
    Thực thi kiểm tra quyền consent, truy xuất dữ liệu lịch sử giao dịch cá nhân
    và đóng gói ToolResultItem.
    """
    if user_consent is not None:
        session_manager.set_consent(session_id, user_consent)

    has_consent = session_manager.get_consent(session_id)

    if not has_consent:
        msg_text = (
            "Yêu cầu cấp quyền truy cập thông tin cá nhân: Để tra cứu và hiển thị lịch sử giao dịch cá nhân, "
            "hệ thống cần sự đồng ý của bạn để truy xuất dữ liệu cá nhân. "
            "Vui lòng lựa chọn Cho phép hoặc Không cho phép trên khung chat để tiếp tục."
        )
        res = TransactionHistoryResult(
            status="consent_required",
            has_consent=False,
            message=msg_text
        )
        log_detail = "Trạng thái: Chưa có quyền (Consent required). Cần người dùng xác nhận Cho phép/Không cho phép."
        ctx_block = (
            "[YÊU CẦU QUYỀN TRUY CẬP THÔNG TIN CÁ NHÂN]:\n"
            f"{msg_text}\n"
            "- Tình trạng: Người dùng chưa cấp quyền truy cập thông tin cá nhân trong phiên này.\n"
            "- Yêu cầu: Hãy giải thích ngắn gọn, lịch sự rằng hệ thống cần được người dùng cho phép truy cập thông tin cá nhân để xem lịch sử giao dịch, và mời người dùng bấm lựa chọn 'Cho phép' hoặc 'Không cho phép' ngay ở khung chat bên dưới."
        )
        consent_required = True
    else:
        formatted_rows = [f"- {tx.description}" for tx in PLACEHOLDER_TRANSACTIONS]
        data_text = (
            "Dữ liệu lịch sử giao dịch gần đây của người dùng (Placeholder Data):\n"
            + "\n".join(formatted_rows)
        )
        res = TransactionHistoryResult(
            status="success",
            has_consent=True,
            transactions=PLACEHOLDER_TRANSACTIONS,
            data_text=data_text
        )
        log_detail = f"Trạng thái: Đã có quyền truy cập. Lấy thành công {len(PLACEHOLDER_TRANSACTIONS)} giao dịch mẫu."
        ctx_block = f"[KẾT QUẢ TRA CỨU LỊCH SỬ GIAO DỊCH CỦA NGƯỜI DÙNG]:\n{data_text}"
        consent_required = False

    tool_log = (
        f"**[GỌI TOOL: get_transaction_history]**\n"
        f"- Query: {query or 'Mặc định'}\n"
        f"- User Consent: {user_consent}\n"
        f"- {log_detail}\n"
    )

    return ToolResultItem(
        tool="get_transaction_history",
        context_block=ctx_block,
        tool_log=tool_log,
        data=res.model_dump(),
        consent_required=consent_required
    )
