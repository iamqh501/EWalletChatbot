from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ==========================================
# TOOL ARGUMENT SCHEMAS
# ==========================================

class SearchGeneralKnowledgeArgs(BaseModel):
    query: str = Field(
        ...,
        description="Câu hỏi hoặc từ khóa cần tìm kiếm về hướng dẫn sử dụng, chính sách chung về ví điện tử."
    )


class SearchTelecomPackagesArgs(BaseModel):
    package_name: Optional[str] = Field(
        None,
        description="Tên gói cước điện thoại (ví dụ: YOLO90_12T, BIG, D169G)."
    )
    price_min: Optional[float] = Field(
        None,
        description="Giá tiền tối thiểu (VNĐ)."
    )
    price_max: Optional[float] = Field(
        None,
        description="Giá tiền tối đa (VNĐ)."
    )
    cycle_days_min: Optional[int] = Field(
        None,
        description="Chu kỳ tối thiểu (tính bằng ngày). QUY ĐỔI BẮT BUỘC: 1 tuần = 7 ngày, 1 tháng = 30 ngày, 1 năm = 360 ngày."
    )
    cycle_days_max: Optional[int] = Field(
        None,
        description="Chu kỳ tối đa (tính bằng ngày). QUY ĐỔI BẮT BUỘC: 1 tuần = 7 ngày, 1 tháng = 30 ngày, 1 năm = 360 ngày."
    )
    data_gb_per_day_min: Optional[float] = Field(
        None,
        description="Dung lượng data tối thiểu mỗi ngày (GB)."
    )
    data_gb_per_day_max: Optional[float] = Field(
        None,
        description="Dung lượng data tối đa mỗi ngày (GB)."
    )


class ResolveIntentArgs(BaseModel):
    query: str = Field(
        ...,
        description="Câu hỏi hoặc yêu cầu hiện tại của người dùng đang bị mơ hồ hoặc không chắc chắn."
    )
    uncertainty_reason: str = Field(
        ...,
        description="Lý do chi tiết vì sao bạn không chắc chắn người dùng muốn gì (VD: câu hỏi có nhiều cách hiểu, thiếu chủ ngữ/thực thể tham chiếu)."
    )


class GuideAppTaskArgs(BaseModel):
    task_query: str = Field(
        ...,
        description="Mô tả tác vụ hoặc hành động người dùng muốn thực hiện trên ứng dụng VNPT Money (ví dụ: 'cách mua gói data', 'cách nạp tiền điện thoại', 'xem lịch sử giao dịch')."
    )
    current_screen: Optional[str] = Field(
        None,
        description="Mã hoặc tên màn hình hiện tại người dùng đang đứng (ví dụ: 'HOME'/'Trang chủ' nếu đang ở trang chủ, hoặc tên màn hình cụ thể đang mở). Không phải là màn hình đích cần hướng dẫn tới. Có thể để trống nếu không rõ."
    )


class GetTransactionHistoryArgs(BaseModel):
    query: Optional[str] = Field(
        None,
        description="Nội dung yêu cầu tra cứu lịch sử giao dịch cá nhân hoặc loại giao dịch cần tra cứu (ví dụ: 'chuyển tiền', 'nhận tiền', 'gần đây'). Có thể để trống."
    )
    user_consent: Optional[bool] = Field(
        None,
        description="Trạng thái cấp quyền truy cập thông tin cá nhân từ người dùng: True nếu người dùng thể hiện rõ sự đồng ý/cho phép (ví dụ 'tôi đồng ý', 'cho phép', 'ok'); False nếu từ chối; None nếu người dùng chỉ mới hỏi xem lịch sử."
    )


# ==========================================
# STANDARDIZED TYPED DOMAIN & RESULT MODELS
# ==========================================

@dataclass
class ToolResultItem:
    """Mô hình dữ liệu chuẩn hóa cho mỗi kết quả thực thi của Tool lưu trong retrieved_context."""
    tool: str
    context_block: str
    data: Any = None


class TelecomPackage(BaseModel):
    """Mô hình dữ liệu gói cước viễn thông chuẩn hóa."""
    package_name: str
    price_vnd: float = 0.0
    cycle_days: int = 0
    data_gb_per_day: float = 0.0


class TransactionRecord(BaseModel):
    """Mô hình bản ghi lịch sử giao dịch cá nhân."""
    date: str
    action: str
    amount: str
    target: str
    content: str
    type: str
    description: str


class TransactionHistoryResult(BaseModel):
    """Mô hình kết quả trả về của tool tra cứu lịch sử giao dịch."""
    status: str
    has_consent: bool
    message: Optional[str] = None
    transactions: List[TransactionRecord] = Field(default_factory=list)
    data_text: Optional[str] = None


class KnowledgeChunk(BaseModel):
    """Mô hình chunk tài liệu tri thức trả về từ tìm kiếm kiến thức chung."""
    source: str
    score: float
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResultItem(BaseModel):
    """Mô hình kết quả Hybrid Search và Rerank từ Qdrant & Parent Document Store."""
    parent_id: str
    score: float
    source: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    """Mô hình một lượt hội thoại lưu trữ trong SessionManager."""
    id: int
    user_query: str
    agent_output: str


class HistoryEvalResult(BaseModel):
    """Mô hình kết quả đánh giá liên quan lịch sử hội thoại từ HistoryScorer."""
    scored_messages: List[Dict[str, Any]] = Field(default_factory=list)
    valid_context: List[Dict[str, Any]] = Field(default_factory=list)
    context_text: str = ""
    debug_text: str = ""
