from dataclasses import dataclass, field
from typing import List, Any, Optional
from langchain_core.tools import tool

from backend.tools.schemas import (
    SearchGeneralKnowledgeArgs,
    SearchTelecomPackagesArgs,
    ResolveIntentArgs,
    GuideAppTaskArgs,
    GetTransactionHistoryArgs,
    ToolResultItem
)
from backend.tools.general_knowledge import execute_search_general_knowledge
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
    tool_logs: List[str] = field(default_factory=list)
    retrieved_context: List[ToolResultItem] = field(default_factory=list)

    def record(self, result: ToolResultItem) -> Any:
        """Ghi nhận kết quả chuẩn hóa của tool vào context_block, tool_logs và trạng thái consent."""
        self.retrieved_context.append(result)
        if result.tool_log:
            self.tool_logs.append(result.tool_log)
        if result.consent_required:
            self.transaction_history_consent = True
        return result.data


def create_search_general_knowledge_tool(context: AgentToolContext):
    """Tạo LangChain tool tra cứu kiến thức chung về ví điện tử gắn với context."""
    @tool(args_schema=SearchGeneralKnowledgeArgs, return_direct=True)
    def search_general_knowledge(query: str) -> Any:
        """Tìm kiếm thông tin hướng dẫn sử dụng, chính sách chung về ví điện tử."""
        result = execute_search_general_knowledge(
            query=query,
            dense_model=context.app_state.dense_model,
            sparse_model=context.app_state.sparse_model,
            client=context.app_state.qdrant_client,
            store=context.app_state.store
        )
        return context.record(result)

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
        result = execute_search_telecom_packages(
            package_name=package_name,
            price_min=price_min,
            price_max=price_max,
            cycle_days_min=cycle_days_min,
            cycle_days_max=cycle_days_max,
            data_gb_per_day_min=data_gb_per_day_min,
            data_gb_per_day_max=data_gb_per_day_max,
            packages=context.app_state.telecom_packages
        )
        return context.record(result)

    return search_telecom_packages


def create_resolve_intent_tool(context: AgentToolContext):
    """Tạo LangChain tool giải quyết sự không chắc chắn về ý định người dùng gắn với context."""
    @tool(args_schema=ResolveIntentArgs)
    def resolve_intent(query: str, uncertainty_reason: str) -> str:
        """Sử dụng tool này khi bạn KHÔNG CHẮC CHẮN người dùng muốn gì."""
        result = execute_resolve_intent(
            query=query,
            uncertainty_reason=uncertainty_reason,
            history_context_text=context.history_context_text,
            llm=context.llm
        )
        return context.record(result)

    return resolve_intent


def create_guide_app_task_tool(context: AgentToolContext):
    """Tạo LangChain tool hướng dẫn thao tác và điều hướng trên ứng dụng VNPT Money."""
    @tool(args_schema=GuideAppTaskArgs, return_direct=True)
    def guide_app_task(task_query: str, current_screen: Optional[str] = None) -> str:
        """Hướng dẫn cách thực hiện một tác vụ trên app (nạp điện thoại, mua data, xem lịch sử...) và cách điều hướng màn hình."""
        result = execute_guide_app_task(
            task_query=task_query,
            current_screen=current_screen,
            nav_map=context.app_state.nav_map,
            dense_model=context.app_state.dense_model,
            sparse_model=context.app_state.sparse_model,
            client=context.app_state.qdrant_client,
            store=context.app_state.store
        )
        return context.record(result)

    return guide_app_task


def create_get_transaction_history_tool(context: AgentToolContext):
    """Tạo LangChain tool tra cứu lịch sử giao dịch cá nhân gắn với context và session."""
    @tool(args_schema=GetTransactionHistoryArgs, return_direct=True)
    def get_transaction_history(
        query: Optional[str] = None,
        user_consent: Optional[bool] = None
    ) -> Any:
        """Tra cứu lịch sử biến động số dư và giao dịch cá nhân của người dùng (chuyển tiền, nhận tiền, thanh toán). Cần quyền truy cập thông tin cá nhân."""
        result = execute_get_transaction_history(
            session_id=context.session_id,
            user_consent=user_consent,
            query=query
        )
        return context.record(result)

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
