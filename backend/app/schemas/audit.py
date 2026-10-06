import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditLogResponse(BaseModel):
    """Schema representing an immutable, hash-chained audit record."""
    model_config = ConfigDict(from_attributes=True)

    log_id: str
    sequence: Optional[int] = None
    timestamp: datetime
    user_id: str
    action: str
    request_id: Optional[str] = None
    result: str
    details: Optional[Any] = None
    previous_hash: str
    current_hash: str

    @field_validator("details", mode="before")
    @classmethod
    def parse_details_json(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip().startswith(("{", "[")):
            try:
                return json.loads(v)
            except Exception:
                return v
        return v


class AuditVerificationResponse(BaseModel):
    """Schema representing cryptographic audit hash-chain verification results."""
    valid: bool
    records_checked: int
    corrupted_id: Optional[str] = None
    reason: Optional[str] = None
