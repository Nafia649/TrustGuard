from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class SigningChallengeRequest(BaseModel):
    approver_id: str


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
    challenge_id: Optional[str] = None
    webauthn_options: Optional[Dict[str, Any]] = None


class SignatureSubmissionRequest(BaseModel):
    approver_id: str
    nonce: str
    signature: Optional[str] = None
    authenticator_data: Optional[str] = None
    client_data_json: Optional[str] = None
    credential: Optional[Dict[str, Any]] = None
    challenge_id: Optional[str] = None


class SignatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signature_id: str
    request_id: str
    approver_id: str
    signature_status: str
    timestamp: datetime
    payment_status: str


class PaymentApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    authorized: bool = True
    signature_status: str = "VERIFIED"
    request_id: str
    approver_id: str
    signature_id: str
    canonical_hash: str
    payment_binding_valid: bool = True
    payment_status: str
    timestamp: datetime
    message: str = "Payment successfully and cryptographically approved with REALKEY."


class RegistrationOptionsRequest(BaseModel):
    approver_id: str


class RegistrationOptionsResponse(BaseModel):
    approver_id: str
    challenge_id: str
    expires_at: datetime
    options: Dict[str, Any]


class RegistrationVerificationRequest(BaseModel):
    approver_id: str
    credential: Dict[str, Any]


class RegistrationVerificationResponse(BaseModel):
    status: str = "success"
    approver_id: str
    credential_id: str
    role: str
    message: str


class ApproverProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approver_id: str
    name: str
    role: str
    active: bool
    credential_registered: bool
    credential_id: Optional[str] = None
    sign_count: int


class AuthenticationOptionsRequest(BaseModel):
    approver_id: Optional[str] = None


class AuthenticationOptionsResponse(BaseModel):
    challenge_id: str
    expires_at: datetime
    options: Dict[str, Any]
    approver_id: Optional[str] = None


class AuthenticationVerificationRequest(BaseModel):
    credential: Dict[str, Any]
    approver_id: Optional[str] = None


class AuthenticationVerificationResponse(BaseModel):
    status: str = "authenticated"
    approver_id: str
    name: str
    role: str
    credential_id: str
    sign_count: int
    message: str


class TamperDemoRequest(BaseModel):
    field: str
    tampered_value: Any


class TamperDemoResponse(BaseModel):
    tamper_detected: bool
    field_modified: str
    original_value: Any
    tampered_value: Any
    original_hash: str
    tampered_hash: str
    hash_match: bool
    approval_valid: bool
    reason: str
    message: str
    audit_logged: bool

