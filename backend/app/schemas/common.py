from typing import Any, Dict, Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    demo_mode: bool


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
