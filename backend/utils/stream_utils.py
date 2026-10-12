import sys
import time
import os

# Tầng 1: Cấu hình môi trường (Environment Setup)
def setup_environment():
    """
    Ép hệ thống nhận diện terminal có hỗ trợ màu, vô hiệu hóa đệm I/O
    và ép kiểu encoding của sys.stdout sang utf-8 để tránh UnicodeEncodeError.
    """
    os.environ["FORCE_COLOR"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

# Kích hoạt cấu hình môi trường ngay khi module được import
setup_environment()

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.theme import Theme
except ImportError:
    print("Vui lòng cài đặt thư viện rich: pip install rich")
    sys.exit(1)


class RichLLMStreamer:
    """
    Trình hiển thị stream cho LLM sử dụng thư viện rich.
    Chỉ chịu trách nhiệm format và render UI (không dính dáng đến cấu trúc Agent hay Call API).
    Cho phép tuỳ biến màu sắc và giao diện để tích hợp dễ dàng với mọi framework.
    """
    def __init__(
        self, 
        reasoning_color: str = "grey50", 
        stats_color: str = "bold purple",
        refresh_rate: int = 20
    ):
        self.console = Console(highlight=False)
        self.reasoning_theme = Theme({
            "markdown.item.number": reasoning_color,
            "markdown.item.bullet": reasoning_color,
            "markdown.link": reasoning_color
        })
        self.reasoning_console = Console(
            highlight=False,
            theme=self.reasoning_theme
        )
        self.reasoning_color = reasoning_color
        self.stats_color = stats_color
        self.refresh_rate = refresh_rate

    def render_stream(self, chunk_iterator, max_reasoning_chars=None) -> dict:
        """
        Tiêu thụ một generator/iterator trả về các chunk dữ liệu.
        Lý tưởng để bọc luồng stream của LangChain (hoặc bất kỳ LLM Client nào).
        
        Yêu cầu `chunk_iterator` yield các dictionary có dạng:
        {
            "content": str,         # nội dung chính (mặc định "")
            "reasoning": str,       # nội dung suy nghĩ (mặc định "")
            "usage": dict           # (tuỳ chọn) {"prompt_tokens": int, "completion_tokens": int}
        }
        
        Trả về dict chứa toàn bộ kết quả văn bản và metrics sau khi stream xong.
        """
        start_time = time.time()
        first_token_time = None
        input_tokens = output_tokens = 0
        
        full_reasoning = ""
        full_content = ""
        in_thinking = True
        
        try:
            with Live(console=self.console, refresh_per_second=self.refresh_rate) as live:
                for chunk in chunk_iterator:
                    content = chunk.get("content", "")
                    reasoning = chunk.get("reasoning", "")
                    usage = chunk.get("usage", None)
                    
                    if first_token_time is None and (content or reasoning):
                        first_token_time = time.time()
                        
                    if reasoning:
                        full_reasoning += reasoning.replace("\r", "")
                        
                    if content:
                        full_content += content.replace("\r", "")
                        in_thinking = False
                            
                    renderables = []
                    
                    # Render phần suy nghĩ
                    if full_reasoning:
                        from rich.text import Text
                        
                        if max_reasoning_chars is None or max_reasoning_chars > 0:
                            display_reasoning = full_reasoning
                            is_truncated = False
                            
                            if max_reasoning_chars is not None and len(full_reasoning) > max_reasoning_chars:
                                display_reasoning = full_reasoning[:max_reasoning_chars]
                                is_truncated = True
                                
                            renderables.append(Text("\n[Start thinking]\n", style=self.reasoning_color))
                            
                            # Cập nhật width để capture() cắt dòng chuẩn
                            current_width = self.console.width
                            if current_width:
                                self.reasoning_console.width = current_width
                                
                            with self.reasoning_console.capture() as cap:
                                self.reasoning_console.print(Markdown(display_reasoning, style=self.reasoning_color))
                                
                            captured_text = Text.from_ansi(cap.get().strip('\n'))
                            renderables.append(captured_text)
                            
                            if is_truncated:
                                renderables.append(Text("\n... (Phần suy nghĩ đã được cắt gọn) ...", style="italic " + self.reasoning_color))
                                
                            if not in_thinking:
                                renderables.append(Text("\n\n[End thinking]\n", style=self.reasoning_color))
                        else:
                            if in_thinking:
                                renderables.append(Text("\n💭 Model is thinking...\n", style="italic " + self.reasoning_color))
                        
                    # Render phần nội dung chính
                    if full_content:
                        renderables.append(Markdown(full_content))
                        
                    # Gom nhóm để update khung Live
                    if renderables:
                        live.update(Group(*renderables))
                        
                    # Parse telemetry data (nếu có)
                    if usage:
                        input_tokens = usage.get("prompt_tokens", input_tokens)
                        output_tokens = usage.get("completion_tokens", output_tokens)
                        
        except Exception as e:
            self.console.print(f"\n[Lỗi hiển thị stream]: {e}", style="bold red")
            
        # Đo lường tính toán
        total_time = time.time() - start_time
        time_to_first_token = (first_token_time - start_time) if first_token_time else 0
        generation_time = total_time - time_to_first_token
        
        prompt_speed = input_tokens / time_to_first_token if time_to_first_token > 0 else 0
        gen_speed = output_tokens / generation_time if generation_time > 0 else 0
        
        stats_msg = f"\n\nTTFT: {time_to_first_token:.2f}s | Prompt: {prompt_speed:.1f} t/s ({input_tokens}t) | Gen: {gen_speed:.1f} t/s ({output_tokens}t) | Total: {total_time:.2f}s"
        self.console.print(stats_msg, style=self.stats_color, highlight=False)
        
        return {
            "reasoning": full_reasoning,
            "content": full_content,
            "metrics": {
                "ttft": time_to_first_token,
                "prompt_speed": prompt_speed,
                "gen_speed": gen_speed,
                "total_time": total_time,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        }


def print_user_prompt(prompt: str, color: str = "cyan"):
    """Tiện ích in lại câu hỏi của user cho đẹp"""
    console = Console(highlight=False, force_terminal=True, legacy_windows=False)
    console.print(f"\nBạn vừa hỏi: [{color}]{prompt}[/{color}]")
    console.print("\n[Kết quả từ LLM]:", style="bold")

def langchain_stream_adapter(llm_response_stream):
    """Bóc tách dữ liệu từ LangChain Chunk (hoặc string chunk) để đưa về format chuẩn cho Streamer"""
    for chunk in llm_response_stream:
        if isinstance(chunk, str):
            yield {"content": chunk, "reasoning": ""}
        else:
            reasoning = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            
            usage = None
            if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata is not None:
                usage = {
                    "prompt_tokens": chunk.usage_metadata.get("input_tokens", 0),
                    "completion_tokens": chunk.usage_metadata.get("output_tokens", 0)
                }
                
            yield {
                "content": content,
                "reasoning": reasoning,
                "usage": usage
            }

def print_step_header(title: str):
    """In tiêu đề nổi bật cho một phần/module"""
    console = Console(highlight=False, force_terminal=True, legacy_windows=False)
    console.print(f"\n[bold magenta]=== {title} ===[/bold magenta]")

def print_info(msg: str):
    """In thông báo thông tin thông thường"""
    console = Console(highlight=False, force_terminal=True, legacy_windows=False)
    console.print(f"[cyan]ℹ {msg}[/cyan]")

def print_success(msg: str):
    """In thông báo thành công"""
    console = Console(highlight=False, force_terminal=True, legacy_windows=False)
    console.print(f"[bold green]✔ {msg}[/bold green]")

def print_error(msg: str):
    """In thông báo lỗi"""
    console = Console(highlight=False, force_terminal=True, legacy_windows=False)
    console.print(f"[bold red]✖ {msg}[/bold red]")

def print_result(label: str, content: str):
    """In kết quả với label in đậm"""
    console = Console(highlight=False, force_terminal=True, legacy_windows=False)
    console.print(f"[bold yellow]{label}:[/bold yellow] {content}")


def lcel_rag_stream_adapter(lcel_stream):
    """Bóc tách dữ liệu từ luồng stream của create_retrieval_cha để đưa về format chuẩn cho Streamer"""
    for chunk in lcel_stream:
        if isinstance(chunk, dict) and 'answer' in chunk:
            answer = chunk['answer']
            content = answer.content if hasattr(answer, "content") else str(answer)
            usage = None
            if hasattr(answer, "usage_metadata") and answer.usage_metadata is not None:
                usage = {
                    "prompt_tokens": answer.usage_metadata.get("input_tokens", 0),
                    "completion_tokens": answer.usage_metadata.get("output_tokens", 0)
                }
            yield {
                "content": content,
                "reasoning": "",
                "usage": usage
            }
