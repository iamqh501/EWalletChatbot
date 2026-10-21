from typing import List, Optional
from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str = ""
    image: Optional[str] = None
    session_id: str = "default_session"


class HealthResponse(BaseModel):
    status: str
    is_ready: bool
    current_step: str
    loaded_components: List[str]
