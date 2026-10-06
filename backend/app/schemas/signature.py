from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


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
    approver_id: str = Field(..., description="ID of approver submitting signature")
    nonce: str = Field(..., description="One-time challenge nonce")
    signature: str = Field(..., description="Cryptographic signature string")
    signed_bundle: Optional[Dict[str, Any]] = Field(default=None, description="Exact payment bundle signed by client")
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
    distinct_signatures_count: int = 1
    required_signatures: int = 1


# WebAuthn Registration Schemas
class WebAuthnRegisterBeginRequest(BaseModel):
    approver_id: str = Field(..., description="Approver ID to register WebAuthn credential for")


class WebAuthnRegisterBeginResponse(BaseModel):
    challenge: str
    rp: Dict[str, str]
    user: Dict[str, Any]
    pubKeyCredParams: List[Dict[str, Any]]
    timeout: int = 60000


class WebAuthnRegisterFinishRequest(BaseModel):
    approver_id: str
    credential_id: str
    public_key: str
    raw_id: Optional[str] = None
    attestation_object: Optional[str] = None
    client_data_json: Optional[str] = None


class WebAuthnRegisterFinishResponse(BaseModel):
    success: bool
    message: str
    approver_id: str
    credential_id: str
