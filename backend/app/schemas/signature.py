from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class SigningChallengeResponse(BaseModel):
    request_id: str
    nonce: str
    expires_at: datetime
    payment_bundle: Dict[str, Any]
    canonical_hash: str
    policy_version: int
    routing_tier: str
    required_signatures: int
    signatures_received: int
    authorized_roles: List[str]


class SignatureSubmissionRequest(BaseModel):
    approver_id: str
    nonce: str
    signature: str
    authenticator_data: Optional[str] = None
    client_data_json: Optional[str] = None


class SignatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signature_id: str
    request_id: str
    approver_id: str
    signature_status: str
    timestamp: datetime
    payment_status: str
