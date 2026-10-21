from typing import Optional
from pydantic import BaseModel, Field


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
        description="Mã hoặc tên màn hình hiện tại người dùng đang mở/đang đứng (ví dụ: 'HOME'/'Trang chủ' nếu đang ở trang chủ, hoặc tên màn hình cụ thể đang mở). Không phải là màn hình đích cần hướng dẫn tới. Có thể để trống nếu không rõ."
    )
