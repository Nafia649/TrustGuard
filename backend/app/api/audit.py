from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.audit import AuditLogResponse, AuditVerificationResponse
from app.services.audit_service import (
    get_audit_logs,
    get_audit_log_by_id,
    verify_chain,
)

router = APIRouter(prefix="/audit-log", tags=["Audit Log"])


@router.get(
    "",
    response_model=List[AuditLogResponse],
    summary="List all audit log entries",
    description="Retrieve immutable, hash-chained audit log records with optional filtering and pagination.",
)
def list_audit_logs(
    response: Response,
    request_id: Optional[str] = Query(None, description="Filter by payment request ID"),
    action: Optional[str] = Query(None, description="Filter by audit action (e.g. PAYMENT_CREATED, RISK_SCORED)"),
    user_id: Optional[str] = Query(None, description="Filter by user or actor ID"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order: 'desc' (newest first) or 'asc' (chronological)"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to retrieve"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    verify: bool = Query(False, description="When true, verifies chain integrity and adds verification headers"),
    db: Session = Depends(get_db),
):
    """
    List audit records. If verify=true, checks hash-chain integrity across the database.
    """
    if verify:
        v = verify_chain(db)
        response.headers["X-Audit-Chain-Valid"] = str(v["valid"]).lower()
        response.headers["X-Audit-Records-Checked"] = str(v["records_checked"])

    return get_audit_logs(
        db=db,
        request_id=request_id,
        action=action,
        user_id=user_id,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/verify",
    response_model=AuditVerificationResponse,
    summary="Verify cryptographic integrity of the audit hash chain",
    description="Validates the SHA-256 chain from genesis to head, detecting broken links, altered records, or corrupted hashes.",
)
def verify_audit_chain_endpoint(db: Session = Depends(get_db)):
    """
    Cryptographic verification endpoint.
    Recalculates SHA-256 hashes across all entries and verifies the chained hashes.
    """
    return verify_chain(db)


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    summary="Get single audit log entry by ID",
)
def get_single_audit_log(log_id: str, db: Session = Depends(get_db)):
    """Fetch a single audit log entry by its unique log_id."""
    entry = get_audit_log_by_id(db, log_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log entry '{log_id}' not found.",
        )
    return entry
