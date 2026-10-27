from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool

from backend.tools.schemas import (
    SearchGeneralKnowledgeArgs,
    SearchTelecomPackagesArgs,
    ResolveIntentArgs,
    GuideAppTaskArgs,
    GetTransactionHistoryArgs,
    ToolResultItem
)
from backend.tools.general_knowledge import (
    execute_search_general_knowledge,
    format_chunks_summary_for_thinking
)
from backend.tools.telecom_packages import execute_search_telecom_packages
from backend.tools.intent_resolver import execute_resolve_intent
from backend.tools.app_navigation import execute_guide_app_task
from backend.tools.transaction_history import execute_get_transaction_history


@dataclass
class AgentToolContext:
    """
    Ngữ cảnh và bộ nhớ thu thập dữ liệu / log cho lượt gọi tool của Agent.
    """
    app_state: Any = None
    llm: Any = None
    session_id: str = "default_session"
    history_context_text: str = ""
    transaction_history_consent: bool = False
    limits: Dict[str, int] = field(default_factory=lambda: {
        "search_general_knowledge": 1,
        "search_telecom_packages": 1,
        "resolve_intent": 1,
        "guide_app_task": 1,
        "get_transaction_history": 1
    })
    tool_logs: List[str] = field(default_factory=list)
    retrieved_context: List[ToolResultItem] = field(default_factory=list)


def create_search_general_knowledge_tool(context: AgentToolContext):
    """Tạo LangChain tool tra cứu kiến thức chung về ví điện tử gắn với context."""
    @tool(args_schema=SearchGeneralKnowledgeArgs, return_direct=True)
    def search_general_knowledge(query: str) -> List[Any]:
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

        if not res:
            ctx_block = "Kết quả tra cứu kiến thức chung: Không tìm thấy tài liệu phù hợp."
        else:
            doc_texts = [f"[Tài liệu {i} - Nguồn: {ch.get('source', '')}]\n{ch.get('content', '')}" for i, ch in enumerate(res, 1)]
            ctx_block = "Kết quả tra cứu kiến thức chung:\n" + "\n\n".join(doc_texts)

        context.retrieved_context.append(ToolResultItem(
            tool="search_general_knowledge",
            context_block=ctx_block,
            data=res
        ))
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
        ctx_block = f"Kết quả tra cứu gói cước viễn thông:\n{res}"
        context.retrieved_context.append(ToolResultItem(
            tool="search_telecom_packages",
            context_block=ctx_block,
            data=res
        ))

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
        ctx_block = f"[KẾT QUẢ PHÂN TÍCH Ý ĐỊNH]:\n{content}"
        context.retrieved_context.append(ToolResultItem(
            tool="resolve_intent",
            context_block=ctx_block,
            data=content
        ))
        context.tool_logs.append(
            f"**[GỌI TOOL: resolve_intent]**\n- Lý do không chắc chắn: {uncertainty_reason}\n\n```\n{content}\n```\n"
        )
        return content

    return resolve_intent


def create_guide_app_task_tool(context: AgentToolContext):
    """Tạo LangChain tool hướng dẫn thao tác và điều hướng trên ứng dụng VNPT Money."""
    @tool(args_schema=GuideAppTaskArgs, return_direct=True)
    def guide_app_task(task_query: str, current_screen: Optional[str] = None) -> str:
        """Hướng dẫn cách thực hiện một tác vụ trên app (nạp điện thoại, mua data, xem lịch sử...) và cách điều hướng màn hình."""
        if context.limits.get("guide_app_task", 0) <= 0:
            return "[HỆ THỐNG] Bạn đã hết lượt gọi tool guide_app_task."
        context.limits["guide_app_task"] -= 1

        res = execute_guide_app_task(
            task_query=task_query,
            current_screen=current_screen,
            dense_model=getattr(context.app_state, "dense_model", None),
            sparse_model=getattr(context.app_state, "sparse_model", None),
            client=getattr(context.app_state, "qdrant_client", None),
            store=getattr(context.app_state, "store", None)
        )
        ctx_block = f"[KẾT QUẢ ĐIỀU HƯỚNG VÀ HƯỚNG DẪN TÁC VỤ APP]:\n{res}"
        context.retrieved_context.append(ToolResultItem(
            tool="guide_app_task",
            context_block=ctx_block,
            data=res
        ))

        short_res = res[:2500] + "..." if len(res) > 2500 else res
        context.tool_logs.append(
            f"**[GỌI TOOL: guide_app_task]**\n- Tác vụ: {task_query}\n- Màn hình hiện tại: {current_screen or 'Chưa xác định'}\n\n```\n{short_res}\n```\n"
        )
        return res

    return guide_app_task


def create_get_transaction_history_tool(context: AgentToolContext):
    """Tạo LangChain tool tra cứu lịch sử giao dịch cá nhân gắn với context và session."""
    @tool(args_schema=GetTransactionHistoryArgs, return_direct=True)
    def get_transaction_history(
        query: Optional[str] = None,
        user_consent: Optional[bool] = None
    ) -> Any:
        """Tra cứu lịch sử biến động số dư và giao dịch cá nhân của người dùng (chuyển tiền, nhận tiền, thanh toán). Cần quyền truy cập thông tin cá nhân."""
        if context.limits.get("get_transaction_history", 0) <= 0:
            return {"error": "[HỆ THỐNG] Bạn đã hết lượt gọi tool get_transaction_history."}
        context.limits["get_transaction_history"] -= 1

        res = execute_get_transaction_history(
            session_id=context.session_id,
            user_consent=user_consent,
            query=query
        )

        status = getattr(res, "status", None) or (res.get("status") if isinstance(res, dict) else "")
        if status == "consent_required":
            context.transaction_history_consent = True
            msg_text = getattr(res, "message", None) or (res.get("message", "") if isinstance(res, dict) else "")
            log_detail = "Trạng thái: Chưa có quyền (Consent required). Cần người dùng xác nhận Cho phép/Không cho phép."
            ctx_block = (
                "[YÊU CẦU QUYỀN TRUY CẬP THÔNG TIN CÁ NHÂN]:\n"
                f"{msg_text}\n"
                "- Tình trạng: Người dùng chưa cấp quyền truy cập thông tin cá nhân trong phiên này.\n"
                "- Yêu cầu: Hãy giải thích ngắn gọn, lịch sự rằng hệ thống cần được người dùng cho phép truy cập thông tin cá nhân để xem lịch sử giao dịch, và mời người dùng bấm lựa chọn 'Cho phép' hoặc 'Không cho phép' ngay ở khung chat bên dưới."
            )
        elif status == "success":
            tx_list = getattr(res, "transactions", None) or (res.get("transactions", []) if isinstance(res, dict) else [])
            data_text = getattr(res, "data_text", None) or (res.get("data_text", "") if isinstance(res, dict) else "")
            log_detail = f"Trạng thái: Đã có quyền truy cập. Lấy thành công {len(tx_list)} giao dịch mẫu."
            ctx_block = f"[KẾT QUẢ TRA CỨU LỊCH SỬ GIAO DỊCH CỦA NGƯỜI DÙNG]:\n{data_text}"
        else:
            log_detail = "Trạng thái: Đã tra cứu dữ liệu."
            ctx_block = f"[KẾT QUẢ TRA CỨU LỊCH SỬ GIAO DỊCH]:\n{res}"

        context.retrieved_context.append(ToolResultItem(
            tool="get_transaction_history",
            context_block=ctx_block,
            data=res
        ))

        context.tool_logs.append(
            f"**[GỌI TOOL: get_transaction_history]**\n- Query: {query or 'Mặc định'}\n- User Consent: {user_consent}\n- {log_detail}\n"
        )
        return res if isinstance(res, dict) else res.model_dump()

    return get_transaction_history


def create_agent_tools(context: Optional[AgentToolContext] = None) -> List[Any]:
    """
    Factory khởi tạo danh sách tất cả LangChain Tools phục vụ AgentOrchestrator.
    """
    if context is None:
        context = AgentToolContext()

    return [
        create_get_transaction_history_tool(context),
        create_search_general_knowledge_tool(context),
        create_search_telecom_packages_tool(context),
        create_guide_app_task_tool(context),
        create_resolve_intent_tool(context),
    ]
