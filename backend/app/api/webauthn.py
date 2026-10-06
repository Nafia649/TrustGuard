import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.approver import Approver
from app.schemas.signature import (
    WebAuthnRegisterBeginRequest,
    WebAuthnRegisterBeginResponse,
    WebAuthnRegisterFinishRequest,
    WebAuthnRegisterFinishResponse,
)
from app.services.audit_service import log_event

router = APIRouter(prefix="/webauthn", tags=["WebAuthn"])

# Temporary in-memory challenge cache for registration challenges
REGISTRATION_CHALLENGES = {}


@router.post(
    "/register/begin",
    response_model=WebAuthnRegisterBeginResponse,
    summary="Begin WebAuthn credential registration for an approver",
)
def register_begin(
    req: WebAuthnRegisterBeginRequest,
    db: Session = Depends(get_db),
):
    """
    Generates WebAuthn registration options for the browser navigator.credentials.create().
    Exposes clean backend integration contract for Security teammate.
    """
    approver = db.query(Approver).filter(Approver.approver_id == req.approver_id).first()
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approver '{req.approver_id}' not found in registry.",
        )

    challenge = secrets.token_hex(32)
    REGISTRATION_CHALLENGES[req.approver_id] = challenge

    return WebAuthnRegisterBeginResponse(
        challenge=challenge,
        rp={
            "name": settings.WEBAUTHN_RP_NAME,
            "id": settings.WEBAUTHN_RP_ID,
        },
        user={
            "id": approver.approver_id,
            "name": approver.name,
            "displayName": f"{approver.name} ({approver.role})",
        },
        pubKeyCredParams=[
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257}, # RS256
        ],
        timeout=60000,
    )


@router.post(
    "/register/finish",
    response_model=WebAuthnRegisterFinishResponse,
    summary="Complete WebAuthn credential registration",
)
def register_finish(
    req: WebAuthnRegisterFinishRequest,
    db: Session = Depends(get_db),
):
    """
    Stores registered public key and credential ID for the authorized approver.
    Audits the registration event.
    """
    approver = db.query(Approver).filter(Approver.approver_id == req.approver_id).first()
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approver '{req.approver_id}' not found in registry.",
        )

    # Persist credential details
    approver.credential_id = req.credential_id
    approver.public_key = req.public_key
    db.commit()
    db.refresh(approver)

    # Clean up challenge
    REGISTRATION_CHALLENGES.pop(req.approver_id, None)

    # Log audit entry
    log_event(
        db=db,
        user_id=approver.approver_id,
        action="WEBAUTHN_REGISTERED",
        result="SUCCESS",
        details={
            "approver_id": approver.approver_id,
            "credential_id": req.credential_id,
            "role": approver.role,
        },
    )

    return WebAuthnRegisterFinishResponse(
        success=True,
        message=f"WebAuthn credential successfully registered for {approver.name}",
        approver_id=approver.approver_id,
        credential_id=req.credential_id,
    )
