import re
from backend.prompts import get_intent_resolver_prompt


def execute_resolve_intent(
    query: str,
    uncertainty_reason: str,
    history_context_text: str,
    llm
) -> str:
    """Thực thi Intent Resolver 3 bước qua LLM để giải quyết sự không chắc chắn."""
    intent_prompt = get_intent_resolver_prompt(
        query=query,
        uncertainty_reason=uncertainty_reason,
        history_context_text=history_context_text
    )

    response = llm.invoke([("user", intent_prompt)])
    content = response.content if hasattr(response, "content") else str(response)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    return content
