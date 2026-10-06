import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.policy import PolicyVersion
from app.models.payment_request import PaymentRequest
from app.models.vendor import Vendor
from app.schemas.policy import (
    PolicyConfig,
    PolicyThresholds,
    PolicySigners,
    PolicyUpdateRequest,
    RoutingResult,
)
from app.services.audit_service import log_event


DEFAULT_POLICY_DICT = {
    "version": 1,
    "thresholds": {
        "auto_approve_below": 30.0,
        "one_signature_below": 70.0,
        "two_signature_below": 90.0,
    },
    "auto_approve_cap_amount": 50000.0,
    "monthly_auto_approved_cap_per_vendor": 200000.0,
    "signers": {
        "one_signature": ["senior_administrator"],
        "two_signatures": ["finance_head", "senior_executive"],
    },
    "always_escalate": ["new_vendor", "bank_detail_change"],
    "po_match_tolerance_percent": 2.0,
    "hold_time_limit_hours": 48,
    "windowed_total_days": 7,
}


def get_active_policy_record(db: Session) -> PolicyVersion:
    """Fetches the active PolicyVersion database entity."""
    record = (
        db.query(PolicyVersion)
        .filter(PolicyVersion.active.is_(True))
        .order_by(PolicyVersion.version.desc())
        .first()
    )
    if not record:
        # Initialize default policy version 1 if not present
        record = PolicyVersion(
            version=1,
            policy_json=json.dumps(DEFAULT_POLICY_DICT, indent=2),
            created_at=datetime.utcnow(),
            created_by="system_default",
            active=True,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def get_active_policy(db: Session) -> PolicyConfig:
    """Retrieves and parses the active PolicyConfig without hardcoding thresholds."""
    record = get_active_policy_record(db)
    data = json.loads(record.policy_json)
    return PolicyConfig(**data)


def update_policy_version(
    db: Session,
    update_data: PolicyUpdateRequest,
    user_id: str,
) -> PolicyVersion:
    """
    Creates a new policy version, deactivates historical active records,
    and logs an immutable audit event.
    """
    thresholds = update_data.policy.thresholds
    if not (thresholds.auto_approve_below < thresholds.one_signature_below <= thresholds.two_signature_below):
        raise ValueError(
            "Threshold validation failed: auto_approve_below must be < one_signature_below <= two_signature_below."
        )

    # Deactivate current active policy
    db.query(PolicyVersion).filter(PolicyVersion.active.is_(True)).update({"active": False})

    # Determine next version number
    max_ver = db.query(func.max(PolicyVersion.version)).scalar() or 0
    new_version_num = max_ver + 1
    update_data.policy.version = new_version_num

    new_policy_record = PolicyVersion(
        version=new_version_num,
        policy_json=update_data.policy.model_dump_json(indent=2),
        created_at=datetime.utcnow(),
        created_by=user_id or update_data.changed_by,
        active=True,
    )
    db.add(new_policy_record)
    db.commit()
    db.refresh(new_policy_record)

    # Log policy change in audit log
    log_event(
        db=db,
        user_id=user_id or update_data.changed_by,
        action="POLICY_CHANGED",
        result="SUCCESS",
        details={
            "new_version": new_version_num,
            "change_reason": update_data.change_reason,
            "thresholds": update_data.policy.thresholds.model_dump(),
            "auto_approve_cap": update_data.policy.auto_approve_cap_amount,
        },
    )

    return new_policy_record


def evaluate_routing(
    db: Session,
    payment: PaymentRequest,
    three_way_facts: Dict[str, Any],
    risk_score: float,
) -> RoutingResult:
    """
    Determines payment authorization routing tier based on configurable policy rules,
    ML risk score, and mandatory safety safeguards.

    Routing tiers:
    - AUTO_APPROVE (0 signatures, status: AUTHORIZED)
    - ONE_SIGNATURE (1 signature, status: PENDING_APPROVAL)
    - TWO_SIGNATURES (2 signatures, status: PENDING_APPROVAL)
    - HOLD (0 signatures, status: ON_HOLD)
    """
    policy = get_active_policy(db)
    thresholds = policy.thresholds
    escalation_reasons: List[str] = []

    # 1. Base tier selection according to dynamic policy thresholds
    if risk_score < thresholds.auto_approve_below:
        tier = "AUTO_APPROVE"
    elif risk_score < thresholds.one_signature_below:
        tier = "ONE_SIGNATURE"
    elif risk_score < thresholds.two_signature_below:
        tier = "TWO_SIGNATURES"
    else:
        tier = "HOLD"
        escalation_reasons.append(
            f"ML risk score ({risk_score}) exceeds hold threshold ({thresholds.two_signature_below})"
        )

    # 2. Mandatory Unconditional Escalations (Independent of ML score)

    # Check unapproved vendor -> Immediately HOLD
    if three_way_facts.get("vendor_approved") == 0:
        tier = "HOLD"
        escalation_reasons.append("Vendor is not approved in vendor registry")

    # Check duplicate invoice -> Immediately HOLD
    if three_way_facts.get("duplicate_invoice") == 1:
        tier = "HOLD"
        escalation_reasons.append("Duplicate invoice detected")

    # Check bank detail change -> Mandatory escalation to TWO_SIGNATURES or HOLD
    if "bank_detail_change" in policy.always_escalate and three_way_facts.get("bank_account_changed") == 1:
        if tier in ("AUTO_APPROVE", "ONE_SIGNATURE"):
            tier = "TWO_SIGNATURES"
        escalation_reasons.append(
            "Mandatory escalation: Beneficiary bank account changed from registered record"
        )

    # Check new vendor -> Mandatory escalation
    vendor = db.query(Vendor).filter(Vendor.vendor_id == payment.vendor_id).first()
    is_new_vendor = False
    if vendor and vendor.onboarded_date:
        is_new_vendor = (payment.timestamp - vendor.onboarded_date).days < 30

    if "new_vendor" in policy.always_escalate and is_new_vendor:
        if tier == "AUTO_APPROVE":
            tier = "ONE_SIGNATURE"
        escalation_reasons.append("Mandatory escalation: First-time/new vendor cannot be auto-approved")

    # 3. Auto-Approval Safety Safeguards (Section 12)
    if tier == "AUTO_APPROVE":
        # Check single payment auto-approve cap
        if payment.amount > policy.auto_approve_cap_amount:
            tier = "ONE_SIGNATURE"
            escalation_reasons.append(
                f"Amount {payment.amount} exceeds auto-approval cap ({policy.auto_approve_cap_amount})"
            )

        # Check vendor cumulative 30-day auto-approved cap
        thirty_days_ago = payment.timestamp - timedelta(days=30)
        recent_auto_approved_sum = (
            db.query(func.sum(PaymentRequest.amount))
            .filter(
                PaymentRequest.vendor_id == payment.vendor_id,
                PaymentRequest.request_id != payment.request_id,
                PaymentRequest.routing_tier == "AUTO_APPROVE",
                PaymentRequest.timestamp >= thirty_days_ago,
            )
            .scalar()
            or 0.0
        )
        if (recent_auto_approved_sum + payment.amount) > policy.monthly_auto_approved_cap_per_vendor:
            tier = "ONE_SIGNATURE"
            escalation_reasons.append(
                f"Vendor monthly auto-approved volume ({recent_auto_approved_sum + payment.amount}) "
                f"exceeds cap ({policy.monthly_auto_approved_cap_per_vendor})"
            )

        # Mandatory matching checks must be satisfied
        if three_way_facts.get("po_exists") == 0:
            tier = "ONE_SIGNATURE"
            escalation_reasons.append("Purchase Order does not exist")
        elif three_way_facts.get("po_approved") == 0:
            tier = "ONE_SIGNATURE"
            escalation_reasons.append("Purchase Order is not approved")
        elif three_way_facts.get("grn_exists") == 0:
            tier = "ONE_SIGNATURE"
            escalation_reasons.append("Goods receipt note not verified")
        elif not three_way_facts.get("amount_match", True):
            tier = "ONE_SIGNATURE"
            escalation_reasons.append("Invoice amount exceeds PO tolerance")

    # 4. Map final tier to status, signatures required, and authorized roles
    if tier == "AUTO_APPROVE":
        status_str = "AUTHORIZED"
        required_signatures = 0
        roles = []
    elif tier == "ONE_SIGNATURE":
        status_str = "PENDING_APPROVAL"
        required_signatures = 1
        roles = policy.signers.one_signature
    elif tier == "TWO_SIGNATURES":
        status_str = "PENDING_APPROVAL"
        required_signatures = 2
        roles = policy.signers.two_signatures
    else:  # HOLD
        status_str = "ON_HOLD"
        required_signatures = 0
        roles = []

    return RoutingResult(
        risk_score=risk_score,
        routing_tier=tier,
        required_signatures=required_signatures,
        status=status_str,
        authorized_roles=roles,
        escalation_reasons=escalation_reasons,
        policy_version=policy.version,
    )
