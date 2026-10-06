"""
REALKEY Separation of Duties (SoD) Module.

Enforces the core security invariant:
    PREPARER ≠ APPROVER

The person who prepares, creates, or submits a payment request must never be
the same person who approves or signs that payment.

Key architectural properties:
1. Authoritative Identity:
   The preparer identity is resolved authoritatively from the backend database
   (PaymentRequest.requester_id / PaymentRequest.preparer_id). Frontend-supplied
   preparer overrides are strictly ignored during challenge creation and approval.
2. Fail-Closed Enforcement:
   If payment.preparer_id == approver_id, approval is strictly blocked.
   Canonical security reason: SEPARATION_OF_DUTIES_VIOLATION.
3. Defense in Depth:
   SoD is enforced:
   - At challenge generation (POST /payments/{request_id}/challenge) to reject self-approval
     before any WebAuthn signing options are issued.
   - At approval ceremony execution (POST /payments/{request_id}/approve) before any signature
     is persisted or payment status is updated.
4. Independent Evaluator:
   Separation of duties is evaluated per-payment, not globally. A preparer of Payment A
   is permitted to approve an independent Payment B if policy allows.
5. Role Independence:
   Even if a user holds dual roles (e.g. PREPARER and APPROVER), the identity comparison
   preparer_id == approver_id takes precedence and blocks self-approval.
6. Hash-Chained Audit Security:
   Any self-approval attempt logs a SECURITY_ALERT in the tamper-evident audit log
   with action SEPARATION_OF_DUTIES_VIOLATION, result SECURITY_ALERT, and safe metadata.
"""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.payment_request import PaymentRequest
from app.models.approver import Approver
from app.services.audit_service import log_event


class SeparationOfDutiesError(Exception):
    """Raised when an approver attempts to approve their own payment (preparer == approver)."""
    pass


def get_authoritative_preparer(payment: PaymentRequest) -> Optional[str]:
    """
    Retrieves the authoritative preparer identity from the persistent database record.
    Never trusts client-supplied overrides at approval/challenge time.

    Args:
        payment: The database PaymentRequest instance.

    Returns:
        The authoritative preparer/requester ID string, or None if not set.
    """
    if hasattr(payment, "preparer_id") and payment.preparer_id:
        return payment.preparer_id.strip()
    if hasattr(payment, "requester_id") and payment.requester_id:
        return payment.requester_id.strip()
    return None


def verify_separation_of_duties(
    preparer_id: Optional[str],
    approver_id: str,
) -> None:
    """
    Verifies that the approver identity is distinct from the preparer identity.

    Args:
        preparer_id: The authoritative preparer/requester identity of the payment.
        approver_id: The identity of the approver attempting to sign.

    Raises:
        SeparationOfDutiesError: If approver_id matches preparer_id (case-insensitive).
    """
    if not approver_id or not approver_id.strip():
        raise SeparationOfDutiesError("Approver ID cannot be empty.")

    if preparer_id is not None:
        norm_preparer = preparer_id.strip().lower()
        norm_approver = approver_id.strip().lower()
        if norm_preparer and norm_approver and norm_preparer == norm_approver:
            raise SeparationOfDutiesError(
                f"SEPARATION_OF_DUTIES_VIOLATION: Approver '{approver_id}' prepared this payment and cannot approve it."
            )


def log_sod_violation(
    db: Session,
    request_id: str,
    preparer_id: Optional[str],
    attempted_approver_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Logs an immutable security alert in the tamper-evident audit log
    for a Separation of Duties violation.

    Ensures zero leak of private keys, signatures, or credentials.

    Args:
        db: Active database session.
        request_id: Payment request identifier.
        preparer_id: Authoritative preparer ID.
        attempted_approver_id: The identity that attempted the self-approval.
        details: Optional additional non-sensitive context.
    """
    event_details: Dict[str, Any] = {
        "reason": "SEPARATION_OF_DUTIES_VIOLATION",
        "preparer_id": preparer_id,
        "attempted_approver_id": attempted_approver_id,
    }
    if details:
        for k, v in details.items():
            if k in ("credential", "signature", "client_data_json", "authenticator_data", "private_key"):
                continue
            event_details[k] = v

    log_event(
        db=db,
        user_id=attempted_approver_id,
        action="SEPARATION_OF_DUTIES_VIOLATION",
        result="SECURITY_ALERT",
        request_id=request_id,
        details=event_details,
    )
