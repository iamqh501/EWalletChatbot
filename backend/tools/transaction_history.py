from typing import Optional, List
from backend.core.state import session_manager
from backend.tools.schemas import TransactionRecord, TransactionHistoryResult

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
) -> TransactionHistoryResult:
    """
    Thực thi kiểm tra quyền consent và truy xuất dữ liệu lịch sử giao dịch cá nhân.
    Quyền truy cập được lưu persistent trong SessionManager của session tương ứng.
    """
    if user_consent is not None:
        session_manager.set_consent(session_id, user_consent)

    has_consent = session_manager.get_consent(session_id)

    if not has_consent:
        return TransactionHistoryResult(
            status="consent_required",
            has_consent=False,
            message=(
                "Yêu cầu cấp quyền truy cập thông tin cá nhân: Để tra cứu và hiển thị lịch sử giao dịch cá nhân, "
                "hệ thống cần sự đồng ý của bạn để truy xuất dữ liệu cá nhân. "
                "Vui lòng lựa chọn Cho phép hoặc Không cho phép trên khung chat để tiếp tục."
            )
        )

    formatted_rows = [f"- {tx.description}" for tx in PLACEHOLDER_TRANSACTIONS]
    data_text = (
        "Dữ liệu lịch sử giao dịch gần đây của người dùng (Placeholder Data):\n"
        + "\n".join(formatted_rows)
    )

    return TransactionHistoryResult(
        status="success",
        has_consent=True,
        transactions=PLACEHOLDER_TRANSACTIONS,
        data_text=data_text
    )
