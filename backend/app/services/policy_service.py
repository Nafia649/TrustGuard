"""
Policy Engine Service for TrustGuard.

Translates Three-Way Match facts, ML risk scores, transaction amounts, and
enterprise policy rules into authoritative routing tiers and signature requirements.

Policy Hierarchy:
- TIER_0 / AUTO_APPROVE: Low risk (<30) + amount <= cap (50k) + matching 3-way facts.
- TIER_1 / ONE_SIGNATURE: Medium risk (30-70) or amount > 50k -> Requires 1 signature (senior_administrator).
- TIER_2 / TWO_SIGNATURES: Higher risk (70-90) or large amount (>100k) -> Requires 2 signatures (finance_head, senior_executive).
- TIER_3 / ANALYST_HOLD: Critical risk (>=90) or unapproved vendor / escalation -> Requires executive approval.
"""

from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.payment_request import PaymentRequest
from app.models.policy import PolicyVersion
from app.models.approver import Approver
from app.services.seed_service import DEFAULT_POLICY_CONFIG


@dataclass
class PolicyEvaluationResult:
    policy_version: int
    routing_tier: str
    required_signatures: int
    authorized_roles: List[str]
    escalation_reasons: List[str]
    auto_approvable: bool


def get_active_policy_config(db: Session) -> Dict[str, Any]:
    """Retrieves the active policy configuration dictionary from the database."""
    active_policy = (
        db.query(PolicyVersion)
        .filter(PolicyVersion.active.is_(True))
        .order_by(PolicyVersion.version.desc())
        .first()
    )
    if active_policy and active_policy.policy_json:
        try:
            return json.loads(active_policy.policy_json)
        except Exception:
            pass
    return DEFAULT_POLICY_CONFIG


def evaluate_payment_policy(
    db: Session,
    payment: PaymentRequest,
    policy_config: Optional[Dict[str, Any]] = None,
) -> PolicyEvaluationResult:
    """
    Authoritatively evaluates enterprise policy rules for a payment request.
    Determines routing tier, required signatures count, and authorized approver roles.
    """
    config = policy_config or get_active_policy_config(db)
    policy_version = config.get("version", 1)
    thresholds = config.get("thresholds", {})
    auto_approve_below = thresholds.get("auto_approve_below", 30.0)
    one_sig_below = thresholds.get("one_signature_below", 70.0)
    two_sig_below = thresholds.get("two_signature_below", 90.0)
    auto_approve_cap = config.get("auto_approve_cap_amount", 50000.0)
    signers_config = config.get("signers", {})
    one_sig_roles = signers_config.get("one_signature", ["senior_administrator"])
    two_sig_roles = signers_config.get("two_signatures", ["finance_head", "senior_executive"])

    escalations = []
    risk_score = payment.risk_score

    # Check vendor legitimacy
    if payment.vendor and not payment.vendor.approved:
        escalations.append("UNAPPROVED_VENDOR")

    # Tier decision logic
    if risk_score is not None and risk_score >= two_sig_below:
        routing_tier = "TIER_3"
        required_signatures = 2
        authorized_roles = ["senior_executive"]
    elif risk_score is not None and risk_score >= one_sig_below:
        routing_tier = "TIER_2"
        required_signatures = 2
        authorized_roles = list(set(two_sig_roles + ["senior_executive"]))
    elif payment.amount > 100000.0 or (risk_score is not None and risk_score >= auto_approve_below):
        routing_tier = "TIER_1"
        required_signatures = 1
        authorized_roles = list(set(one_sig_roles + two_sig_roles + ["senior_administrator", "finance_head", "senior_executive"]))
    elif payment.amount > auto_approve_cap:
        routing_tier = "TIER_1"
        required_signatures = 1
        authorized_roles = list(set(one_sig_roles + two_sig_roles + ["senior_administrator", "finance_head", "senior_executive"]))
    else:
        # Low risk and below amount cap
        routing_tier = "TIER_1" if payment.required_signatures > 0 else "AUTO_APPROVE"
        required_signatures = payment.required_signatures if payment.required_signatures > 0 else 1
        authorized_roles = list(set(one_sig_roles + two_sig_roles + ["senior_administrator", "finance_head", "senior_executive"]))

    # Use existing payment.routing_tier / required_signatures if already set
    effective_routing_tier = payment.routing_tier or routing_tier
    effective_required_sigs = payment.required_signatures if payment.required_signatures > 0 else required_signatures

    if not payment.routing_tier:
        payment.routing_tier = effective_routing_tier
    if payment.required_signatures == 0:
        payment.required_signatures = effective_required_sigs

    return PolicyEvaluationResult(
        policy_version=policy_version,
        routing_tier=effective_routing_tier,
        required_signatures=effective_required_sigs,
        authorized_roles=authorized_roles,
        escalation_reasons=escalations,
        auto_approvable=(risk_score is not None and risk_score < auto_approve_below and payment.amount <= auto_approve_cap and len(escalations) == 0),
    )


def is_approver_authorized_by_policy(
    approver: Approver,
    authorized_roles: List[str],
) -> bool:
    """Verifies that the approver possesses an authorized role for this policy routing tier."""
    if not authorized_roles:
        return True
    approver_roles = [r.strip().lower() for r in approver.role.split(",")]
    allowed_roles = [r.strip().lower() for r in authorized_roles]
    return any(r in allowed_roles for r in approver_roles)
