from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool

from backend.tools.schemas import (
    SearchGeneralKnowledgeArgs,
    SearchTelecomPackagesArgs,
    ResolveIntentArgs
)
from backend.tools.general_knowledge import (
    execute_search_general_knowledge,
    format_chunks_summary_for_thinking
)
from backend.tools.telecom_packages import execute_search_telecom_packages
from backend.tools.intent_resolver import execute_resolve_intent


@dataclass
class AgentToolContext:
    """
    Ngữ cảnh và bộ nhớ thu thập dữ liệu / log cho lượt gọi tool của Agent.
    """
    app_state: Any = None
    llm: Any = None
    history_context_text: str = ""
    limits: Dict[str, int] = field(default_factory=lambda: {
        "search_general_knowledge": 1,
        "search_telecom_packages": 1,
        "resolve_intent": 1
    })
    tool_logs: List[str] = field(default_factory=list)
    retrieved_context: List[Dict[str, Any]] = field(default_factory=list)


def create_search_general_knowledge_tool(context: AgentToolContext):
    """Tạo LangChain tool tra cứu kiến thức chung về ví điện tử gắn với context."""
    @tool(args_schema=SearchGeneralKnowledgeArgs, return_direct=True)
    def search_general_knowledge(query: str) -> List[Dict[str, Any]]:
        """Tìm kiếm thông tin hướng dẫn sử dụng, chính sách chung về ví điện tử."""
        if context.limits.get("search_general_knowledge", 0) <= 0:
            return [{"error": "[HỆ THỐNG] Bạn đã hết lượt gọi tool này. Hãy sử dụng thông tin hiện có để trả lời."}]
        context.limits["search_general_knowledge"] -= 1

        res = execute_search_general_knowledge(
            query=query,
            dense_model=getattr(context.app_state, "dense_model", None),
            sparse_model=getattr(context.app_state, "sparse_model", None),
            client=getattr(context.app_state, "qdrant_client", None),
            store=getattr(context.app_state, "store", None)
        )
        context.retrieved_context.append({"tool": "search_general_knowledge", "data": res})
        tool_summary = format_chunks_summary_for_thinking(res)
        context.tool_logs.append(
            f"**[GỌI TOOL]**\n\n`search_general_knowledge(query=\"{query}\")`\n\n```\n{tool_summary}\n```\n"
        )
        return res

    return search_general_knowledge


def create_search_telecom_packages_tool(context: AgentToolContext):
    """Tạo LangChain tool tra cứu và đề xuất gói cước viễn thông gắn với context."""
    @tool(args_schema=SearchTelecomPackagesArgs, return_direct=True)
    def search_telecom_packages(
        package_name: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        cycle_days_min: Optional[int] = None,
        cycle_days_max: Optional[int] = None,
        data_gb_per_day_min: Optional[float] = None,
        data_gb_per_day_max: Optional[float] = None,
    ) -> str:
        """Tìm kiếm và đề xuất các gói cước điện thoại dựa trên các tiêu chí."""
        if context.limits.get("search_telecom_packages", 0) <= 0:
            return "[HỆ THỐNG] Bạn đã hết lượt gọi tool này. Hãy sử dụng thông tin hiện có để trả lời."
        context.limits["search_telecom_packages"] -= 1

        args_dict = {
            "package_name": package_name,
            "price_min": price_min,
            "price_max": price_max,
            "cycle_days_min": cycle_days_min,
            "cycle_days_max": cycle_days_max,
            "data_gb_per_day_min": data_gb_per_day_min,
            "data_gb_per_day_max": data_gb_per_day_max
        }
        res = execute_search_telecom_packages(**args_dict)
        context.retrieved_context.append({"tool": "search_telecom_packages", "data": res})

        args_str = ", ".join([f"{k}={repr(v)}" for k, v in args_dict.items() if v is not None])
        short_res = res[:2500] + "..." if len(res) > 2500 else res
        context.tool_logs.append(
            f"**[GỌI TOOL]**\n\n`search_telecom_packages({args_str})`\n\n```\n{short_res}\n```\n"
        )
        return res

    return search_telecom_packages


def create_resolve_intent_tool(context: AgentToolContext):
    """Tạo LangChain tool giải quyết sự không chắc chắn về ý định người dùng gắn với context."""
    @tool(args_schema=ResolveIntentArgs)
    def resolve_intent(query: str, uncertainty_reason: str) -> str:
        """Sử dụng tool này khi bạn KHÔNG CHẮC CHẮN người dùng muốn gì."""
        if context.limits.get("resolve_intent", 0) <= 0:
            return "[HỆ THỐNG] Bạn đã hết lượt gọi tool resolve_intent."
        context.limits["resolve_intent"] -= 1

        content = execute_resolve_intent(
            query=query,
            uncertainty_reason=uncertainty_reason,
            history_context_text=context.history_context_text,
            llm=context.llm
        )
        context.retrieved_context.append({"tool": "resolve_intent", "data": content})
        context.tool_logs.append(
            f"**[GỌI TOOL: resolve_intent]**\n- Lý do không chắc chắn: {uncertainty_reason}\n\n```\n{content}\n```\n"
        )
        return content

    return resolve_intent


def create_agent_tools(context: Optional[AgentToolContext] = None) -> List[Any]:
    """
    Factory khởi tạo danh sách tất cả LangChain Tools phục vụ AgentOrchestrator.
    """
    if context is None:
        context = AgentToolContext()

    return [
        create_search_general_knowledge_tool(context),
        create_search_telecom_packages_tool(context),
        create_resolve_intent_tool(context)
    ]
