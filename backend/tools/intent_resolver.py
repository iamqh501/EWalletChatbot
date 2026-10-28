import re
from backend.prompts import get_intent_resolver_prompt
from backend.tools.schemas import ToolResultItem


def execute_resolve_intent(
    query: str,
    uncertainty_reason: str,
    history_context_text: str,
    llm
) -> ToolResultItem:
    """Thực thi Intent Resolver 3 bước qua LLM để giải quyết sự không chắc chắn và đóng gói ToolResultItem."""
    intent_prompt = get_intent_resolver_prompt(
        query=query,
        uncertainty_reason=uncertainty_reason,
        history_context_text=history_context_text
    )

    response = llm.invoke([("user", intent_prompt)])
    content = response.content if hasattr(response, "content") else str(response)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

    ctx_block = f"[KẾT QUẢ PHÂN TÍCH Ý ĐỊNH]:\n{content}"
    tool_log = (
        f"**[GỌI TOOL: resolve_intent]**\n"
        f"- Lý do không chắc chắn: {uncertainty_reason}\n\n"
        f"```\n{content}\n```\n"
    )

    return ToolResultItem(
        tool="resolve_intent",
        context_block=ctx_block,
        tool_log=tool_log,
        data=content
    )
