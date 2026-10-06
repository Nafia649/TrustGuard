from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.payment_request import PaymentRequest
from app.models.signature import Signature
from app.schemas.signature import (
    SigningChallengeResponse,
    SignatureSubmissionRequest,
    SignatureResponse,
)
from app.services.signature_service import (
    create_signing_challenge,
    verify_and_record_signature,
    SignatureSecurityError,
)

router = APIRouter(tags=["Signing"])


@router.get(
    "/payments/{request_id}/challenge",
    response_model=SigningChallengeResponse,
    summary="Generate one-time cryptographic signing challenge and payment bundle",
)
def get_signing_challenge(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Creates a signing challenge for a payment requiring human approval.
    Constructs the canonical bundle, binds it to nonce and policy version,
    and returns authorized signer roles.
    """
    payment = (
        db.query(PaymentRequest)
        .filter(PaymentRequest.request_id == request_id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment request '{request_id}' not found.",
        )

    try:
        challenge = create_signing_challenge(db, payment)
    except SignatureSecurityError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail=err.detail,
        )

    return challenge


@router.post(
    "/payments/{request_id}/sign",
    response_model=SignatureResponse,
    summary="Submit and verify cryptographic signature for payment approval",
)
def sign_payment(
    request_id: str,
    submission: SignatureSubmissionRequest,
    db: Session = Depends(get_db),
):
    """
    Submits a cryptographic signature for payment authorization.
    Enforces server-side separation of duties, role verification, anti-tamper,
    anti-replay, and fail-closed security.
    """
    try:
        sig_record, new_status = verify_and_record_signature(
            db=db,
            payment_id=request_id,
            approver_id=submission.approver_id,
            nonce=submission.nonce,
            signature_str=submission.signature,
            signed_bundle=submission.signed_bundle,
        )
    except SignatureSecurityError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail=err.detail,
        )

    # Count distinct signatures
    valid_sigs = (
        db.query(Signature)
        .filter(
            Signature.request_id == request_id,
            Signature.signature_status == "VALID",
        )
        .all()
    )
    payment = db.query(PaymentRequest).filter(PaymentRequest.request_id == request_id).first()

    return SignatureResponse(
        signature_id=sig_record.signature_id,
        request_id=sig_record.request_id,
        approver_id=sig_record.approver_id,
        signature_status=sig_record.signature_status,
        timestamp=sig_record.timestamp,
        payment_status=new_status,
        distinct_signatures_count=len(set(s.approver_id for s in valid_sigs)),
        required_signatures=payment.required_signatures if payment else 1,
    )
