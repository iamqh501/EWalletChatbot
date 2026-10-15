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
