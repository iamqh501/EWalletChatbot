import time
import sys
from typing import Optional, Dict, Any

# Đảm bảo UTF-8 encoding trên Windows CMD (Rule 8)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


class StreamMetricsTracker:
    """
    Theo dõi và tính toán các chỉ số hiệu năng (Latency & Token Speeds) trong luồng streaming LLM.
    Sử dụng time.perf_counter() để đảm bảo độ chính xác vi giây (microsecond) và tính đơn điệu (monotonic).
    """

    def __init__(self):
        self.t_start: float = 0.0
        self.t_end: float = 0.0
        self.first_token_time: Optional[float] = None

        # Trạng thái tracking
        self.last_mark: float = 0.0
        self.in_generation: bool = False

        # Thời gian tích lũy theo từng pha (giây)
        self.total_prompt_time: float = 0.0
        self.total_gen_time: float = 0.0
        self.total_tool_time: float = 0.0

        # Số lượng token
        self.input_tokens: int = 0
        self.output_tokens: int = 0

    def start(self):
        """Bắt đầu đo lường khi bắt đầu lượt truy vấn."""
        self.t_start = time.perf_counter()
        self.last_mark = self.t_start
        self.first_token_time = None
        self.in_generation = False
        self.total_prompt_time = 0.0
        self.total_gen_time = 0.0
        self.total_tool_time = 0.0
        self.input_tokens = 0
        self.output_tokens = 0

    def on_token(self, has_content: bool = True):
        """
        Ghi nhận khi nhận được token (reasoning hoặc text content) từ model.
        Nếu đang ở phase chuẩn bị (prompt evaluation), ghi nhận prompt time và chuyển sang phase generation.
        """
        now = time.perf_counter()
        if not self.in_generation:
            if has_content:
                self.in_generation = True
                self.total_prompt_time += (now - self.last_mark)
                self.last_mark = now
                if self.first_token_time is None:
                    self.first_token_time = now
        else:
            self.total_gen_time += (now - self.last_mark)
            self.last_mark = now

    def on_tool_start(self):
        """Ghi nhận khi model quyết định gọi Tool (kết thúc phase generation trước đó)."""
        now = time.perf_counter()
        if self.in_generation:
            self.total_gen_time += (now - self.last_mark)
            self.in_generation = False
        self.last_mark = now

    def on_tool_end(self):
        """Ghi nhận khi Tool thực thi xong (bắt đầu lại phase prompt evaluation cho lượt kế tiếp)."""
        now = time.perf_counter()
        self.total_tool_time += (now - self.last_mark)
        self.in_generation = False
        self.last_mark = now

    def update_usage(self, usage: Optional[Dict[str, Any]]):
        """Cập nhật số lượng input và output token từ usage metadata của chunk."""
        if usage:
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)

    def stop(self):
        """Kết thúc đo lường khi luồng stream hoàn tất."""
        self.t_end = time.perf_counter()
        now = self.t_end
        if self.in_generation:
            self.total_gen_time += (now - self.last_mark)
            self.in_generation = False

    @property
    def total_time(self) -> float:
        """Tổng thời gian xử lý toàn bộ truy vấn (giây)."""
        return (self.t_end - self.t_start) if self.t_end > 0 else (time.perf_counter() - self.t_start)

    @property
    def ttft(self) -> float:
        """Time to First Token (giây)."""
        return (self.first_token_time - self.t_start) if self.first_token_time else 0.0

    @property
    def prompt_speed(self) -> float:
        """Tốc độ xử lý Prompt (tokens/giây)."""
        return (self.input_tokens / self.total_prompt_time) if self.total_prompt_time > 0 else 0.0

    @property
    def gen_speed(self) -> float:
        """Tốc độ sinh phản hồi (tokens/giây)."""
        return (self.output_tokens / self.total_gen_time) if self.total_gen_time > 0 else 0.0

    def get_stats_message(self) -> str:
        """Tạo chuỗi thông điệp thống kê chuẩn để gửi qua SSE event 'stats'."""
        if self.input_tokens > 0 or self.output_tokens > 0:
            return (
                f"\n\nTTFT: {self.ttft:.2f}s | "
                f"Prompt: {self.prompt_speed:.1f} t/s ({self.input_tokens}t) | "
                f"Gen: {self.gen_speed:.1f} t/s ({self.output_tokens}t) | "
                f"Total: {self.total_time:.2f}s"
            )
        return f"\n\nTTFT: {self.ttft:.2f}s | Total: {self.total_time:.2f}s"
