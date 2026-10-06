import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

GENESIS_HASH = "0" * 64


def calculate_hash(
    log_id: str,
    timestamp: datetime,
    user_id: str,
    action: str,
    request_id: Optional[str],
    result: str,
    details_str: str,
    previous_hash: str,
) -> str:
    """Calculate SHA-256 hash chaining value for an audit record."""
    canonical_representation = (
        f"{log_id}|{timestamp.isoformat()}|{user_id}|{action}|"
        f"{request_id or ''}|{result}|{details_str}|{previous_hash}"
    )
    return hashlib.sha256(canonical_representation.encode("utf-8")).hexdigest()


def log_event(
    db: Session,
    user_id: str,
    action: str,
    result: str,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Append an immutable, hash-chained record to the audit log.
    Ensures that any tampering breaks the cryptographic chain.
    """
    # Fetch the most recent audit entry to link previous_hash and monotonic sequence
    last_log = (
        db.query(AuditLog)
        .order_by(AuditLog.sequence.desc(), AuditLog.timestamp.desc(), AuditLog.log_id.desc())
        .first()
    )
    previous_hash = last_log.current_hash if last_log else GENESIS_HASH
    sequence = (last_log.sequence + 1) if (last_log and last_log.sequence is not None) else 1

    log_id = f"LOG-{uuid.uuid4().hex[:12].upper()}"
    timestamp = datetime.utcnow()
    details_str = json.dumps(details, sort_keys=True) if details else ""

    current_hash = calculate_hash(
        log_id=log_id,
        timestamp=timestamp,
        user_id=user_id,
        action=action,
        request_id=request_id,
        result=result,
        details_str=details_str,
        previous_hash=previous_hash,
    )

    audit_entry = AuditLog(
        log_id=log_id,
        sequence=sequence,
        timestamp=timestamp,
        user_id=user_id,
        action=action,
        request_id=request_id,
        result=result,
        details=details_str,
        previous_hash=previous_hash,
        current_hash=current_hash,
    )

    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry


def get_audit_logs(
    db: Session,
    request_id: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> List[AuditLog]:
    """Retrieve filtered audit logs with pagination and deterministic sorting."""
    query = db.query(AuditLog)
    if request_id:
        query = query.filter(AuditLog.request_id == request_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if order.lower() == "asc":
        query = query.order_by(AuditLog.sequence.asc(), AuditLog.timestamp.asc(), AuditLog.log_id.asc())
    else:
        query = query.order_by(AuditLog.sequence.desc(), AuditLog.timestamp.desc(), AuditLog.log_id.desc())

    return query.offset(offset).limit(limit).all()


def get_audit_log_by_id(db: Session, log_id: str) -> Optional[AuditLog]:
    """Retrieve a single audit log entry by unique ID."""
    return db.query(AuditLog).filter(AuditLog.log_id == log_id).first()


def verify_chain(db: Session) -> Dict[str, Any]:
    """
    Verify the cryptographic integrity of the entire audit chain.
    Returns whether the chain is valid and identifies any corrupted entry.
    """
    records = (
        db.query(AuditLog)
        .order_by(AuditLog.sequence.asc(), AuditLog.timestamp.asc(), AuditLog.log_id.asc())
        .all()
    )
    if not records:
        return {"valid": True, "records_checked": 0, "corrupted_id": None, "reason": None}

    expected_prev = GENESIS_HASH
    for rec in records:
        if rec.previous_hash != expected_prev:
            return {
                "valid": False,
                "records_checked": len(records),
                "corrupted_id": rec.log_id,
                "reason": f"Broken link: expected previous_hash {expected_prev}, got {rec.previous_hash}",
            }

        recalculated = calculate_hash(
            log_id=rec.log_id,
            timestamp=rec.timestamp,
            user_id=rec.user_id,
            action=rec.action,
            request_id=rec.request_id,
            result=rec.result,
            details_str=rec.details or "",
            previous_hash=rec.previous_hash,
        )
        if recalculated != rec.current_hash:
            return {
                "valid": False,
                "records_checked": len(records),
                "corrupted_id": rec.log_id,
                "reason": f"Hash mismatch: calculated {recalculated} does not match current_hash {rec.current_hash}",
            }

        expected_prev = rec.current_hash

    return {"valid": True, "records_checked": len(records), "corrupted_id": None, "reason": None}
