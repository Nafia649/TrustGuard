"""
REALKEY WebAuthn Registration and Verification Router.

Provides API endpoints for WebAuthn/Passkey registration ceremonies,
issuing unpredictable challenges and verifying authenticator credentials server-side.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.approver import Approver
import json
from app.schemas.signature import (
    ApproverProfileResponse,
    RegistrationOptionsRequest,
    RegistrationOptionsResponse,
    RegistrationVerificationRequest,
    RegistrationVerificationResponse,
    AuthenticationOptionsRequest,
    AuthenticationOptionsResponse,
    AuthenticationVerificationRequest,
    AuthenticationVerificationResponse,
)
from app.services.audit_service import log_event
from webauthn.helpers import base64url_to_bytes
from security.realkey.challenge import (
    ChallengeAlreadyUsedError,
    ChallengeExpiredError,
    ChallengeMismatchError,
    ChallengeNotFoundError,
    challenge_store,
)
from security.realkey.webauthn_verifier import (
    InvalidCredentialFormatError,
    InvalidOriginError,
    InvalidRPIDError,
    InvalidSignatureError,
    SignCountReplayError,
    WebAuthnAuthenticationError,
    WebAuthnRegistrationError,
    generate_authentication_options,
    generate_registration_options,
    verify_authentication,
    verify_registration,
)

router = APIRouter(prefix="/auth/webauthn", tags=["REALKEY WebAuthn"])


@router.post(
    "/register/options",
    response_model=RegistrationOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate WebAuthn credential registration options and challenge",
)
def get_registration_options(
    request: RegistrationOptionsRequest,
    db: Session = Depends(get_db),
):
    """
    Initiates WebAuthn registration:
    1. Validates approver exists and is active.
    2. Generates unpredictable, single-use, time-bounded challenge.
    3. Builds PublicKeyCredentialCreationOptions compliant with W3C WebAuthn.
    """
    approver = db.query(Approver).filter(Approver.approver_id == request.approver_id).first()
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approver '{request.approver_id}' not found in registry.",
        )

    if not approver.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approver '{request.approver_id}' is inactive and cannot register credentials.",
        )

    # 1. Create secure challenge (TTL: configured seconds)
    challenge = challenge_store.create_registration_challenge(
        approver_id=approver.approver_id,
        timeout_seconds=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS,
    )

    # 2. Build W3C WebAuthn options
    options = generate_registration_options(
        approver_id=approver.approver_id,
        approver_name=approver.name,
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        challenge_bytes=challenge.challenge_bytes,
        timeout_ms=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS * 1000,
    )

    # 3. Audit log the challenge issuance
    log_event(
        db=db,
        user_id=approver.approver_id,
        action="WEBAUTHN_REGISTRATION_CHALLENGE_ISSUED",
        result="SUCCESS",
        details={
            "challenge_id": challenge.challenge_id,
            "expires_at": challenge.expires_at.isoformat(),
            "rp_id": settings.WEBAUTHN_RP_ID,
        },
    )

    return RegistrationOptionsResponse(
        approver_id=approver.approver_id,
        challenge_id=challenge.challenge_id,
        expires_at=challenge.expires_at,
        options=options,
    )


@router.post(
    "/register/verify",
    response_model=RegistrationVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify and store WebAuthn authenticator registration response",
)
def verify_registration_response(
    request: RegistrationVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Verifies client WebAuthn registration response:
    1. Validates approver.
    2. Validates and retrieves pending challenge (checks expiration and single-use).
    3. Performs cryptographic server-side verification of origin, RP ID, and attestation.
    4. Validates duplicate credential detection across approvers.
    5. Stores credential_id and public_key PEM (NEVER private key).
    6. Consumes challenge to prevent replay.
    """
    approver = db.query(Approver).filter(Approver.approver_id == request.approver_id).first()
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approver '{request.approver_id}' not found.",
        )

    if not approver.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approver '{request.approver_id}' is inactive.",
        )

    # 1. Retrieve active challenge
    try:
        challenge = challenge_store.get_valid_registration_challenge(approver_id=approver.approver_id)
    except ChallengeNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )
    except ChallengeExpiredError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration rejected: {err}",
        )
    except ChallengeAlreadyUsedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration rejected: {err}",
        )
    except ChallengeMismatchError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration rejected: {err}",
        )

    # 2. Cryptographic verification server-side
    try:
        verified = verify_registration(
            credential_payload=request.credential,
            expected_challenge=challenge.challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.cors_origins,
            require_user_presence=True,
            require_user_verification=False,
        )
    except InvalidOriginError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_REGISTRATION_FAILED",
            result="FAILURE",
            details={"reason": "InvalidOrigin", "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Origin verification failed: {err}",
        )
    except InvalidRPIDError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_REGISTRATION_FAILED",
            result="FAILURE",
            details={"reason": "InvalidRPID", "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"RP ID verification failed: {err}",
        )
    except (InvalidCredentialFormatError, WebAuthnRegistrationError) as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_REGISTRATION_FAILED",
            result="FAILURE",
            details={"reason": "VerificationError", "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WebAuthn verification rejected: {err}",
        )

    # 3. Check for duplicate credential already registered to another approver
    duplicate_approver = (
        db.query(Approver)
        .filter(
            Approver.credential_id == verified.credential_id,
            Approver.approver_id != approver.approver_id,
        )
        .first()
    )
    if duplicate_approver:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Credential ID '{verified.credential_id}' is already registered "
                f"to approver '{duplicate_approver.approver_id}'."
            ),
        )

    # 4. Consume challenge (enforce single-use)
    challenge_store.consume_registration_challenge(
        approver_id=approver.approver_id,
        challenge_id=challenge.challenge_id,
    )

    # 5. Store credential metadata and public key (NO private key)
    approver.credential_id = verified.credential_id
    approver.public_key = verified.public_key_pem
    approver.sign_count = verified.sign_count
    db.commit()
    db.refresh(approver)

    # 6. Audit log successful registration
    log_event(
        db=db,
        user_id=approver.approver_id,
        action="WEBAUTHN_CREDENTIAL_REGISTERED",
        result="SUCCESS",
        details={
            "credential_id": verified.credential_id,
            "role": approver.role,
            "sign_count": verified.sign_count,
            "aaguid": verified.aaguid,
        },
    )

    return RegistrationVerificationResponse(
        status="success",
        approver_id=approver.approver_id,
        credential_id=verified.credential_id,
        role=approver.role,
        message="WebAuthn passkey credential successfully verified and registered.",
    )


@router.get(
    "/approvers/{approver_id}",
    response_model=ApproverProfileResponse,
    summary="Get approver registration and public key status",
)
def get_approver_profile(
    approver_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves approver registration status without leaking private keys."""
    approver = db.query(Approver).filter(Approver.approver_id == approver_id).first()
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approver '{approver_id}' not found.",
        )

    return ApproverProfileResponse(
        approver_id=approver.approver_id,
        name=approver.name,
        role=approver.role,
        active=approver.active,
        credential_registered=bool(approver.credential_id and approver.public_key),
        credential_id=approver.credential_id,
        sign_count=approver.sign_count,
    )


@router.get(
    "/approvers",
    response_model=List[ApproverProfileResponse],
    summary="List all approvers and their passkey registration status",
)
def list_approver_profiles(
    db: Session = Depends(get_db),
):
    """Lists all approvers in the system."""
    approvers = db.query(Approver).all()
    return [
        ApproverProfileResponse(
            approver_id=app.approver_id,
            name=app.name,
            role=app.role,
            active=app.active,
            credential_registered=bool(app.credential_id and app.public_key),
            credential_id=app.credential_id,
            sign_count=app.sign_count,
        )
        for app in approvers
    ]


# ---------------------------------------------------------
# AUTHENTICATION / ASSERTION ENDPOINTS
# ---------------------------------------------------------

@router.post(
    "/authenticate/options",
    response_model=AuthenticationOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate WebAuthn authentication/assertion challenge and options",
)
def get_authentication_options(
    request: AuthenticationOptionsRequest,
    db: Session = Depends(get_db),
):
    """
    Initiates WebAuthn authentication:
    1. Validates approver exists and is active (if approver_id provided).
    2. Validates approver has a registered credential.
    3. Generates unpredictable, single-use, time-bounded challenge.
    4. Builds PublicKeyCredentialRequestOptions for navigator.credentials.get().
    """
    allowed_credentials = None
    if request.approver_id:
        approver = db.query(Approver).filter(Approver.approver_id == request.approver_id).first()
        if not approver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approver '{request.approver_id}' not found.",
            )
        if not approver.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approver '{request.approver_id}' is inactive.",
            )
        if not approver.credential_id or not approver.public_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approver '{request.approver_id}' has no registered WebAuthn credential.",
            )
        allowed_credentials = [base64url_to_bytes(approver.credential_id)]

    # 1. Create fresh unpredictable challenge
    challenge = challenge_store.create_authentication_challenge(
        approver_id=request.approver_id,
        timeout_seconds=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS,
    )

    # 2. Build WebAuthn request options
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        challenge_bytes=challenge.challenge_bytes,
        allowed_credential_ids=allowed_credentials,
        timeout_ms=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS * 1000,
    )

    # 3. Audit log challenge issuance
    log_event(
        db=db,
        user_id=request.approver_id or "anonymous_authenticator",
        action="WEBAUTHN_AUTH_CHALLENGE_ISSUED",
        result="SUCCESS",
        details={
            "challenge_id": challenge.challenge_id,
            "expires_at": challenge.expires_at.isoformat(),
            "rp_id": settings.WEBAUTHN_RP_ID,
        },
    )

    return AuthenticationOptionsResponse(
        challenge_id=challenge.challenge_id,
        expires_at=challenge.expires_at,
        options=options,
        approver_id=request.approver_id,
    )


@router.post(
    "/authenticate/verify",
    response_model=AuthenticationVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cryptographically verify WebAuthn passkey assertion response",
)
def verify_authentication_response(
    request: AuthenticationVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Verifies client WebAuthn authentication assertion response:
    1. Looks up credential_id and identifies the registered approver.
    2. Validates approver is active and has registered public key.
    3. Validates and retrieves pending challenge (checks expiration and single-use).
    4. Performs cryptographic server-side verification of signature, RP ID, and origin.
    5. Enforces sign-count replay protection (monotonicity check).
    6. Consumes challenge to prevent replay.
    7. Updates stored sign_count.
    """
    if not isinstance(request.credential, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed credential: payload must be a JSON object.",
        )

    cred_id_str = request.credential.get("id")
    if not cred_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed credential payload: missing credential 'id'.",
        )

    # 1. Identify and validate approver
    if request.approver_id:
        approver = db.query(Approver).filter(Approver.approver_id == request.approver_id).first()
        if not approver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approver '{request.approver_id}' not found.",
            )
        if approver.credential_id != cred_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential does not belong to approver '{request.approver_id}'.",
            )
    else:
        approver = db.query(Approver).filter(Approver.credential_id == cred_id_str).first()
        if not approver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown credential: no registered approver found for this credential ID.",
            )

    if not approver.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approver '{approver.approver_id}' is inactive and cannot authenticate.",
        )

    if not approver.public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approver '{approver.approver_id}' has no registered public key.",
        )

    # 2. Extract challenge from clientDataJSON
    response_obj = request.credential.get("response")
    if not isinstance(response_obj, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed assertion response: missing 'response' dictionary.",
        )

    client_data_b64 = response_obj.get("clientDataJSON")
    if not client_data_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed assertion response: missing 'clientDataJSON'.",
        )

    try:
        client_data_bytes = base64url_to_bytes(client_data_b64)
        client_data_dict = json.loads(client_data_bytes.decode("utf-8"))
        client_challenge_b64 = client_data_dict.get("challenge")
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse clientDataJSON: {err}",
        )

    # 3. Retrieve and validate active challenge
    try:
        challenge = challenge_store.get_valid_authentication_challenge(
            challenge_b64=client_challenge_b64,
            approver_id=approver.approver_id,
        )
    except ChallengeNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (ChallengeExpiredError, ChallengeAlreadyUsedError, ChallengeMismatchError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Authentication rejected: {err}")

    # 4. Cryptographic assertion verification
    try:
        verified = verify_authentication(
            credential_payload=request.credential,
            expected_challenge=challenge.challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.cors_origins,
            public_key_pem=approver.public_key,
            current_sign_count=approver.sign_count,
            require_user_presence=True,
            require_user_verification=False,
        )
    except InvalidOriginError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_AUTHENTICATION_FAILED",
            result="FAILURE",
            details={"reason": "InvalidOrigin", "error": str(err)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Origin verification failed: {err}")
    except InvalidRPIDError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_AUTHENTICATION_FAILED",
            result="FAILURE",
            details={"reason": "InvalidRPID", "error": str(err)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"RP ID verification failed: {err}")
    except InvalidSignatureError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_AUTHENTICATION_FAILED",
            result="FAILURE",
            details={"reason": "InvalidSignature", "error": str(err)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cryptographic signature invalid: {err}")
    except SignCountReplayError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_AUTHENTICATION_FAILED",
            result="FAILURE",
            details={"reason": "SignCountReplay", "error": str(err)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sign count replay detected: {err}")
    except (InvalidCredentialFormatError, WebAuthnAuthenticationError) as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="WEBAUTHN_AUTHENTICATION_FAILED",
            result="FAILURE",
            details={"reason": "VerificationRejected", "error": str(err)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"WebAuthn assertion rejected: {err}")

    # 5. Enforce single-use: consume challenge
    challenge_store.consume_authentication_challenge(challenge.challenge_id)

    # 6. Update sign_count in Approver model
    approver.sign_count = verified.new_sign_count
    db.commit()
    db.refresh(approver)

    # 7. Audit log successful authentication
    log_event(
        db=db,
        user_id=approver.approver_id,
        action="WEBAUTHN_AUTHENTICATION_SUCCESS",
        result="SUCCESS",
        details={
            "credential_id": verified.credential_id,
            "role": approver.role,
            "new_sign_count": verified.new_sign_count,
        },
    )

    return AuthenticationVerificationResponse(
        status="authenticated",
        approver_id=approver.approver_id,
        name=approver.name,
        role=approver.role,
        credential_id=verified.credential_id,
        sign_count=verified.new_sign_count,
        message="WebAuthn passkey assertion cryptographically verified.",
    )
