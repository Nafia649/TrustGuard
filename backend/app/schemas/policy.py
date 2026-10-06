from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PolicyThresholds(BaseModel):
    auto_approve_below: float = Field(default=30.0, ge=0, le=100)
    one_signature_below: float = Field(default=70.0, ge=0, le=100)
    two_signature_below: float = Field(default=90.0, ge=0, le=100)


class PolicySigners(BaseModel):
    one_signature: List[str] = ["senior_administrator"]
    two_signatures: List[str] = ["finance_head", "senior_executive"]


class PolicyConfig(BaseModel):
    version: int = 1
    thresholds: PolicyThresholds = Field(default_factory=PolicyThresholds)
    auto_approve_cap_amount: float = 50000.0
    monthly_auto_approved_cap_per_vendor: float = 200000.0
    signers: PolicySigners = Field(default_factory=PolicySigners)
    always_escalate: List[str] = ["new_vendor", "bank_detail_change"]
    po_match_tolerance_percent: float = 2.0
    hold_time_limit_hours: int = 48
    windowed_total_days: int = 7


class PolicyUpdateRequest(BaseModel):
    policy: PolicyConfig
    changed_by: str = Field(..., description="User ID or role initiating the policy modification")
    change_reason: Optional[str] = "Policy threshold adjustment"


class PolicyResponse(BaseModel):
    version: int
    policy: PolicyConfig
    created_at: datetime
    created_by: str
    active: bool


class RoutingResult(BaseModel):
    risk_score: float
    routing_tier: str
    required_signatures: int
    status: str
    authorized_roles: List[str]
    escalation_reasons: List[str]
    policy_version: int
