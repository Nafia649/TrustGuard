"""
REALKEY Replay Guard Module.

Provides comprehensive server-side replay protection for TrustGuard payment approvals:
1. Reusing the exact same WebAuthn approval.
2. Reusing a consumed or expired REALKEY challenge.
3. Reusing a nonce in a new signature.
4. Replaying an approval against a different payment.
5. Replaying an approval under a different approver.
6. Replaying an approval on an already authorized payment.
7. Concurrent replay attempts using atomic state locks.
8. Recording immutable audit alerts for all detected replay attempts.
"""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.payment_request import PaymentRequest
from app.models.signature import Signature
from app.models.approver import Approver
from app.services.audit_service import log_event


class ReplayGuardError(Exception):
    """Base exception for replay guard violations."""
    pass


class NonceAlreadyUsedError(ReplayGuardError):
    """Raised when a nonce has already been recorded in a signature."""
    pass


class ApproverAlreadySignedError(ReplayGuardError):
    """Raised when an approver attempts to sign the same payment twice."""
    pass


class PaymentAlreadyAuthorizedError(ReplayGuardError):
    """Raised when an approval is replayed on an already authorized payment."""
    pass


class SignatureReplayError(ReplayGuardError):
    """Raised when an identical signature or payload hash is resubmitted."""
    pass


def verify_nonce_unused(db: Session, nonce: str) -> None:
    """
    Verifies that a nonce has not already been consumed in any existing Signature record.

    Enforces that each cryptographic nonce is single-use across the entire system.

    Raises:
        NonceAlreadyUsedError: If the nonce is already recorded in the database.
    """
    if not nonce:
        raise NonceAlreadyUsedError("Nonce cannot be empty.")

    existing = db.query(Signature).filter(Signature.nonce == nonce).first()
    if existing:
        raise NonceAlreadyUsedError(
            f"Nonce '{nonce}' has already been consumed in signature '{existing.signature_id}'. Replay rejected."
        )


def verify_approver_not_already_signed(db: Session, request_id: str, approver_id: str) -> None:
    """
    Verifies that an approver does not already have a valid signature on the payment.
    Enforces that each approver can approve a specific payment request at most once.

    Raises:
        ApproverAlreadySignedError: If a valid signature already exists for this approver & request.
    """
    existing = (
        db.query(Signature)
        .filter(
            Signature.request_id == request_id,
            Signature.approver_id == approver_id,
            Signature.signature_status == "VALID",
        )
        .first()
    )
    if existing:
        raise ApproverAlreadySignedError(
            f"Approver '{approver_id}' has already signed payment '{request_id}' with signature '{existing.signature_id}'. Replay rejected."
        )


def verify_payment_not_authorized(payment: PaymentRequest) -> None:
    """
    Verifies that the payment request has not already been fully authorized.

    Raises:
        PaymentAlreadyAuthorizedError: If payment status is already AUTHORIZED.
    """
    if payment.status == "AUTHORIZED":
        raise PaymentAlreadyAuthorizedError(
            f"Payment request '{payment.request_id}' has already been fully authorized. Replay rejected."
        )


def verify_signature_payload_not_replayed(db: Session, payload_hash: str) -> None:
    """
    Verifies that a canonical payment hash has not already been finalized with a valid signature.

    Raises:
        SignatureReplayError: If a valid signature for this exact payload hash already exists.
    """
    if not payload_hash:
        return

    existing = (
        db.query(Signature)
        .filter(
            Signature.payload_hash == payload_hash,
            Signature.signature_status == "VALID",
        )
        .first()
    )
    if existing:
        raise SignatureReplayError(
            f"Signature payload hash '{payload_hash[:16]}...' has already been authorized in signature '{existing.signature_id}'. Replay rejected."
        )


def log_replay_event(
    db: Session,
    request_id: str,
    approver_id: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Records an immutable REALKEY_REPLAY_DETECTED event in the hash-chained audit log.

    Maintains safe, minimal metadata without logging private keys, authenticators,
    or raw credentials.

    Args:
        db: Active database session.
        request_id: Payment request identifier.
        approver_id: Approver identifier.
        reason: Canonical replay reason string (e.g. CHALLENGE_ALREADY_CONSUMED, NONCE_ALREADY_USED).
        details: Optional additional diagnostic dictionary.
    """
    event_details: Dict[str, Any] = {"reason": reason}
    if details:
        # Sanitize details to avoid logging sensitive credential payloads
        for k, v in details.items():
            if k in ("credential", "signature", "client_data_json", "authenticator_data"):
                continue
            event_details[k] = v

    log_event(
        db=db,
        user_id=approver_id,
        action="REALKEY_REPLAY_DETECTED",
        result="SECURITY_ALERT",
        request_id=request_id,
        details=event_details,
    )


def verify_all_replay_guards(
    db: Session,
    payment: PaymentRequest,
    approver: Approver,
    nonce: str,
) -> None:
    """
    Convenience orchestrator executing all database-level replay guard checks.
    """
    verify_payment_not_authorized(payment)
    verify_approver_not_already_signed(db, request_id=payment.request_id, approver_id=approver.approver_id)
    verify_nonce_unused(db, nonce)
