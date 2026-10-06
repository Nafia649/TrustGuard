import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.payment_request import PaymentRequest
from app.models.approver import Approver
from app.models.policy import PolicyVersion
from app.models.signature import Signature
from app.models.ledger import LedgerEntry
from app.schemas.payment import PaymentRequestCreate, PaymentResponse
from app.schemas.signature import (
    SigningChallengeRequest,
    SigningChallengeResponse,
    SignatureSubmissionRequest,
    PaymentApprovalResponse,
    TamperDemoRequest,
    TamperDemoResponse,
)
from app.services.audit_service import log_event
from app.services.policy_service import (
    evaluate_payment_policy,
    is_approver_authorized_by_policy,
)

from security.realkey.challenge import (
    ChallengeAlreadyUsedError,
    ChallengeExpiredError,
    ChallengeMismatchError,
    ChallengeNotFoundError,
    PaymentHashMismatchError,
    challenge_store,
)
from security.realkey.bundle import (
    REQUIRED_PAYMENT_BUNDLE_FIELDS,
    calculate_bundle_expiry,
    canonicalize_payment_bundle,
    create_payment_bundle,
    create_payment_bundle_from_model,
    format_utc_timestamp,
    generate_payment_nonce,
    hash_payment_bundle,
    is_bundle_expired,
)
from security.realkey.tamper_demo import demonstrate_tamper_detection
from security.realkey.replay_guard import (
    ApproverAlreadySignedError,
    NonceAlreadyUsedError,
    PaymentAlreadyAuthorizedError,
    SignatureReplayError,
    log_replay_event,
    verify_approver_not_already_signed,
    verify_nonce_unused,
    verify_payment_not_authorized,
)
from security.realkey.sod import (
    SeparationOfDutiesError,
    get_authoritative_preparer,
    log_sod_violation,
    verify_separation_of_duties,
)
from security.realkey.webauthn_verifier import (
    InvalidCredentialFormatError,
    InvalidSignatureError,
    SignCountReplayError,
    WebAuthnAuthenticationError,
    generate_authentication_options,
    verify_payment_approval,
)

router = APIRouter(tags=["Payments"])



@router.post(
    "/payment-requests",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment request",
)
def create_payment_request(
    payment_in: PaymentRequestCreate,
    db: Session = Depends(get_db),
):
    """
    Submits a new payment request for authorization.
    Performs server-side validation against vendors, purchase orders, and prevents duplicates.
    Never trusts client-provided risk scores.
    """
    # 1. Validate target vendor exists
    vendor = db.query(Vendor).filter(Vendor.vendor_id == payment_in.vendor_id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{payment_in.vendor_id}' not found in registered vendor database.",
        )

    # 2. Validate linked purchase order if specified
    if payment_in.po_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == payment_in.po_id).first()
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase Order '{payment_in.po_id}' not found.",
            )
        if po.vendor_id != payment_in.vendor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase Order '{payment_in.po_id}' does not belong to vendor '{payment_in.vendor_id}'.",
            )

    # 3. Check for duplicate invoice submission for this vendor
    existing_invoice = (
        db.query(PaymentRequest)
        .filter(
            PaymentRequest.vendor_id == payment_in.vendor_id,
            PaymentRequest.invoice_id == payment_in.invoice_id,
        )
        .first()
    )
    if existing_invoice:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Duplicate invoice detected: Invoice '{payment_in.invoice_id}' "
                f"has already been submitted for vendor '{payment_in.vendor_id}' "
                f"(Existing Request ID: {existing_invoice.request_id})."
            ),
        )

    # 4. Generate persistent request ID and create payment record
    request_id = f"REQ-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.utcnow()
    authoritative_preparer = payment_in.preparer_id or payment_in.requester_id or "emp_001"

    new_payment = PaymentRequest(
        request_id=request_id,
        vendor_id=payment_in.vendor_id,
        amount=payment_in.amount,
        currency=payment_in.currency.upper(),
        bank_account=payment_in.bank_account,
        invoice_id=payment_in.invoice_id,
        po_id=payment_in.po_id,
        timestamp=now,
        channel=payment_in.channel,
        document_quality_score=payment_in.document_quality_score,
        status="PENDING",
        requester_id=authoritative_preparer,
        processor_id=None,
        fraud_probability=None,
        risk_score=None,
        risk_reasons=None,
        routing_tier=None,
        required_signatures=0,
    )

    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    # 5. Append tamper-evident audit record
    log_event(
        db=db,
        user_id=authoritative_preparer,
        action="PAYMENT_CREATED",
        result="SUCCESS",
        request_id=request_id,
        details={
            "vendor_id": payment_in.vendor_id,
            "amount": payment_in.amount,
            "currency": payment_in.currency,
            "invoice_id": payment_in.invoice_id,
            "po_id": payment_in.po_id,
            "bank_account": payment_in.bank_account,
            "preparer_id": authoritative_preparer,
        },
    )

    return new_payment



@router.get(
    "/payments",
    response_model=List[PaymentResponse],
    summary="List all payment requests",
)
def list_payments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. PENDING, AUTHORIZED)"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve payment requests with optional filtering and pagination."""
    query = db.query(PaymentRequest)

    if status_filter:
        query = query.filter(PaymentRequest.status == status_filter.upper())
    if vendor_id:
        query = query.filter(PaymentRequest.vendor_id == vendor_id)

    payments = query.order_by(PaymentRequest.timestamp.desc()).offset(offset).limit(limit).all()
    return payments


@router.get(
    "/payments/{request_id}",
    response_model=PaymentResponse,
    summary="Get single payment request by ID",
)
def get_payment(
    request_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve detailed payment request information by unique identifier."""
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
    return payment


@router.post(
    "/payments/{request_id}/challenge",
    response_model=SigningChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate WebAuthn signing challenge bound to exact payment bundle",
)
def create_signing_challenge(
    request_id: str,
    challenge_in: Optional[SigningChallengeRequest] = None,
    approver_id: Optional[str] = Query(None, description="Approver ID if not provided in JSON body"),
    db: Session = Depends(get_db),
):
    """
    Initiates payment approval ceremony:
    1. Loads payment from database (authoritative source).
    2. Validates approver exists, is active, and has registered passkey.
    3. Resolves active policy version and routing tier from server authority.
    4. Constructs canonical 11-field payment bundle with fresh nonce & expiry.
    5. Computes SHA-256 canonical hash.
    6. Generates dedicated ApprovalChallenge with WebAuthn request options.
    """
    # 1. Authoritative payment lookup
    payment = (
        db.query(PaymentRequest)
        .filter(PaymentRequest.request_id == request_id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PAYMENT_NOT_FOUND: Payment request '{request_id}' not found.",
        )

    if payment.status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PAYMENT_REJECTED: Cannot issue signing challenge for rejected payment '{request_id}'.",
        )

    # 2. Approver lookup and validation
    target_approver_id = None
    if challenge_in and challenge_in.approver_id:
        target_approver_id = challenge_in.approver_id.strip()
    elif approver_id:
        target_approver_id = approver_id.strip()

    if not target_approver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="APPROVER_REQUIRED: approver_id is required to issue an approval challenge.",
        )

    approver = (
        db.query(Approver)
        .filter(Approver.approver_id == target_approver_id)
        .first()
    )
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"APPROVER_NOT_FOUND: Approver '{target_approver_id}' not found in registry.",
        )

    if not approver.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INACTIVE_APPROVER: Approver '{target_approver_id}' is inactive.",
        )

    if not approver.credential_id or not approver.public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CREDENTIAL_NOT_REGISTERED: Approver '{target_approver_id}' has not registered a passkey.",
        )

    # 2b. Separation of Duties enforcement: PREPARER ≠ APPROVER
    # Authoritatively resolved from the database; never trusts frontend overrides.
    authoritative_preparer = get_authoritative_preparer(payment)
    try:
        verify_separation_of_duties(
            preparer_id=authoritative_preparer,
            approver_id=approver.approver_id,
        )
    except SeparationOfDutiesError as err:
        log_sod_violation(
            db=db,
            request_id=payment.request_id,
            preparer_id=authoritative_preparer,
            attempted_approver_id=approver.approver_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SEPARATION_OF_DUTIES_VIOLATION: Approver '{approver.approver_id}' prepared this payment and cannot approve it.",
        )

    # 2c. Replay Guard: Verify approver has not already signed this payment
    try:
        verify_approver_not_already_signed(
            db, request_id=payment.request_id, approver_id=approver.approver_id
        )
    except ApproverAlreadySignedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"APPROVER_ALREADY_SIGNED: {err}",
        )

    # 3. Server authority for policy and routing
    policy_res = evaluate_payment_policy(db, payment)
    policy_version = policy_res.policy_version
    routing_tier = policy_res.routing_tier
    required_sigs = policy_res.required_signatures

    # 3b. Role Authorization check: Is approver authorized for this routing tier?
    if not is_approver_authorized_by_policy(approver, policy_res.authorized_roles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"APPROVER_ROLE_UNAUTHORIZED: Approver '{approver.approver_id}' with role '{approver.role}' "
                f"is not authorized to approve {routing_tier} payments. Authorized roles: {policy_res.authorized_roles}."
            ),
        )

    # 4. Generate server-side nonce and build exact bundle

    nonce = generate_payment_nonce()
    payment_bundle = create_payment_bundle_from_model(
        payment=payment,
        policy_version=policy_version,
        routing_tier=routing_tier,
        nonce=nonce,
        ttl_seconds=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS,
    )

    # 5. Canonicalize & hash
    canonical_json = canonicalize_payment_bundle(payment_bundle)
    canonical_hash = hash_payment_bundle(canonical_json)

    # 6. Create dedicated approval challenge bound to payment, approver, and preparer
    approval_chal = challenge_store.create_approval_challenge(
        request_id=payment.request_id,
        approver_id=approver.approver_id,
        canonical_payment_hash=canonical_hash,
        nonce=nonce,
        payment_bundle=payment_bundle,
        timeout_seconds=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS,
        preparer_id=authoritative_preparer,
    )


    # 7. Generate WebAuthn options
    webauthn_options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        challenge_bytes=approval_chal.challenge_bytes,
        allow_credentials=[approver.credential_id],
        timeout_ms=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS * 1000,
    )

    # 8. Audit logging
    log_event(
        db=db,
        user_id=approver.approver_id,
        action="APPROVAL_CHALLENGE_ISSUED",
        result="SUCCESS",
        request_id=payment.request_id,
        details={
            "challenge_id": approval_chal.challenge_id,
            "nonce": nonce,
            "canonical_hash": canonical_hash,
            "routing_tier": routing_tier,
            "policy_version": policy_version,
        },
    )

    existing_sigs = (
        db.query(Signature)
        .filter(
            Signature.request_id == payment.request_id,
            Signature.signature_status == "VALID",
        )
        .count()
    )

    return SigningChallengeResponse(
        request_id=payment.request_id,
        nonce=nonce,
        expires_at=approval_chal.expires_at,
        payment_bundle=payment_bundle,
        canonical_hash=canonical_hash,
        policy_version=policy_version,
        routing_tier=routing_tier,
        required_signatures=required_sigs,
        signatures_received=existing_sigs,
        authorized_roles=[approver.role],
        challenge_id=approval_chal.challenge_id,
        webauthn_options=webauthn_options,
    )


@router.post(
    "/payments/{request_id}/approve",
    response_model=PaymentApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Cryptographically verify WebAuthn assertion and approve exact payment",
)
def approve_payment(
    request_id: str,
    submission: SignatureSubmissionRequest,
    db: Session = Depends(get_db),
):
    """
    Executes REALKEY payment approval ceremony:
    1. Loads payment and approver from database.
    2. Retrieves active ApprovalChallenge and validates single-use & expiration.
    3. Verifies nonce.
    4. Reconstructs authoritative bundle from database and detects tampering.
    5. Verifies bundle expiration.
    6. Verifies WebAuthn assertion (signature, RP ID, origin, sign counter).
    7. Updates approver sign counter and persists Signature audit record.
    8. Updates payment status to AUTHORIZED if signature requirements met.
    """
    # 1. Authoritative payment lookup
    payment = (
        db.query(PaymentRequest)
        .filter(PaymentRequest.request_id == request_id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PAYMENT_NOT_FOUND: Payment request '{request_id}' not found.",
        )

    # 2. Approver lookup
    approver = (
        db.query(Approver)
        .filter(Approver.approver_id == submission.approver_id)
        .first()
    )
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"APPROVER_NOT_FOUND: Approver '{submission.approver_id}' not found in registry.",
        )

    if not approver.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INACTIVE_APPROVER: Approver '{submission.approver_id}' is inactive.",
        )

    if not approver.public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CREDENTIAL_NOT_REGISTERED: Approver '{submission.approver_id}' has no registered passkey.",
        )

    # 2b. Separation of Duties enforcement: PREPARER ≠ APPROVER
    # Authoritatively resolved from the database; never trusts frontend overrides.
    authoritative_preparer = get_authoritative_preparer(payment)
    try:
        verify_separation_of_duties(
            preparer_id=authoritative_preparer,
            approver_id=approver.approver_id,
        )
    except SeparationOfDutiesError as err:
        if submission.challenge_id:
            try:
                challenge_store.burn_approval_challenge(submission.challenge_id)
            except Exception:
                pass
        log_sod_violation(
            db=db,
            request_id=payment.request_id,
            preparer_id=authoritative_preparer,
            attempted_approver_id=approver.approver_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SEPARATION_OF_DUTIES_VIOLATION: Approver '{approver.approver_id}' prepared this payment and cannot approve it.",
        )

    # 3. Retrieve, validate and atomically claim ApprovalChallenge
    try:
        challenge = challenge_store.claim_approval_challenge(
            challenge_id=submission.challenge_id,
            request_id=request_id,
            approver_id=submission.approver_id,
        )
    except ChallengeAlreadyUsedError as err:
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="CHALLENGE_ALREADY_CONSUMED",
            details={"challenge_id": submission.challenge_id, "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_APPROVAL_CHALLENGE: CHALLENGE_ALREADY_CONSUMED: {err}",
        )
    except ChallengeMismatchError as err:
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="CHALLENGE_BINDING_MISMATCH",
            details={"challenge_id": submission.challenge_id, "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_APPROVAL_CHALLENGE: {err}",
        )
    except ChallengeExpiredError as err:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_APPROVAL_FAILED",
            result="FAILURE",
            request_id=request_id,
            details={"reason": "APPROVAL_CHALLENGE_EXPIRED", "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"APPROVAL_CHALLENGE_EXPIRED: {err}",
        )
    except ChallengeNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"APPROVAL_CHALLENGE_NOT_FOUND: {err}",
        )

    # 3b. Verify challenge preparer binding if set
    if challenge.preparer_id:
        try:
            verify_separation_of_duties(
                preparer_id=challenge.preparer_id,
                approver_id=approver.approver_id,
            )
        except SeparationOfDutiesError as err:
            challenge_store.burn_approval_challenge(challenge.challenge_id)
            log_sod_violation(
                db=db,
                request_id=payment.request_id,
                preparer_id=challenge.preparer_id,
                attempted_approver_id=approver.approver_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SEPARATION_OF_DUTIES_VIOLATION: Approver '{approver.approver_id}' prepared this payment and cannot approve it.",
            )

    # 4. Verify nonce matches issued challenge

    if submission.nonce != challenge.nonce:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_APPROVAL_FAILED",
            result="FAILURE",
            request_id=request_id,
            details={"reason": "NONCE_MISMATCH"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"NONCE_MISMATCH: Submitted nonce '{submission.nonce}' does not match challenge nonce '{challenge.nonce}'.",
        )

    # 4b. Replay Guard: Verify nonce has not already been consumed in the database
    try:
        verify_nonce_unused(db, submission.nonce)
    except NonceAlreadyUsedError as err:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="NONCE_ALREADY_USED",
            details={"nonce": submission.nonce},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"NONCE_ALREADY_USED: {err}",
        )

    # 4c. Replay Guard: Verify approver has not already signed this payment
    try:
        verify_approver_not_already_signed(db, request_id=payment.request_id, approver_id=approver.approver_id)
    except ApproverAlreadySignedError as err:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="APPROVER_ALREADY_SIGNED",
            details={"approver_id": approver.approver_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"APPROVER_ALREADY_SIGNED: {err}",
        )

    # 4d. Replay Guard: Verify payment is not already fully authorized
    try:
        verify_payment_not_authorized(payment)
    except PaymentAlreadyAuthorizedError as err:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="PAYMENT_ALREADY_AUTHORIZED",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PAYMENT_ALREADY_AUTHORIZED: {err}",
        )

    # 5. Reconstruct authoritative payment bundle from the database
    reconstructed_bundle = create_payment_bundle(
        vendor_id=payment.vendor_id,
        amount=payment.amount,
        currency=payment.currency,
        bank_account=payment.bank_account,
        invoice_id=payment.invoice_id,
        po_id=payment.po_id,
        timestamp=challenge.payment_bundle["timestamp"],
        nonce=challenge.nonce,
        expiry=challenge.payment_bundle["expiry"],
        policy_version=challenge.payment_bundle["policy_version"],
        routing_tier=payment.routing_tier or challenge.payment_bundle["routing_tier"],
    )

    # 6. Verify bundle has not expired
    if is_bundle_expired(reconstructed_bundle):
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_APPROVAL_FAILED",
            result="FAILURE",
            request_id=request_id,
            details={"reason": "APPROVAL_EXPIRED"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"APPROVAL_EXPIRED: Payment bundle expired at {reconstructed_bundle.get('expiry')}.",
        )

    # 7. Canonicalize & recompute hash to detect any tampering
    reconstructed_canonical_json = canonicalize_payment_bundle(reconstructed_bundle)
    reconstructed_canonical_hash = hash_payment_bundle(reconstructed_canonical_json)

    if reconstructed_canonical_hash != challenge.canonical_payment_hash:
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_APPROVAL_FAILED",
            result="FAILURE",
            request_id=request_id,
            details={
                "reason": "PAYMENT_HASH_MISMATCH",
                "authoritative_hash": reconstructed_canonical_hash,
                "challenge_hash": challenge.canonical_payment_hash,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"PAYMENT_HASH_MISMATCH: Authoritative payment hash '{reconstructed_canonical_hash}' "
                f"does not match challenge hash '{challenge.canonical_payment_hash}'. Payment was modified!"
            ),
        )

    # 8. Extract WebAuthn credential payload
    if submission.credential:
        credential_payload = submission.credential
    else:
        if not submission.signature or not submission.authenticator_data or not submission.client_data_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_WEBAUTHN_ASSERTION: Missing signature, authenticator_data, or client_data_json.",
            )
        credential_payload = {
            "id": approver.credential_id,
            "rawId": approver.credential_id,
            "response": {
                "signature": submission.signature,
                "authenticatorData": submission.authenticator_data,
                "clientDataJSON": submission.client_data_json,
            },
            "type": "public-key",
        }

    # Verify credential belongs to authorized approver
    submitted_cred_id = credential_payload.get("id") or credential_payload.get("rawId")
    if submitted_cred_id and approver.credential_id and submitted_cred_id != approver.credential_id:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="CREDENTIAL_NOT_AUTHORIZED",
            details={"submitted_cred_id": submitted_cred_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CREDENTIAL_NOT_AUTHORIZED: Credential does not belong to authorized approver.",
        )

    # 9. Cryptographic WebAuthn assertion verification
    try:
        approval_result = verify_payment_approval(
            credential_payload=credential_payload,
            expected_challenge=challenge.challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.cors_origins,
            public_key_pem=approver.public_key,
            current_sign_count=approver.sign_count,
            authoritative_payment_hash=reconstructed_canonical_hash,
            challenge_payment_hash=challenge.canonical_payment_hash,
            request_id=payment.request_id,
            approver_id=approver.approver_id,
            require_user_presence=True,
            require_user_verification=False,
        )
    except PaymentHashMismatchError as err:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_APPROVAL_FAILED",
            result="FAILURE",
            request_id=request_id,
            details={"reason": "PAYMENT_HASH_MISMATCH", "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PAYMENT_HASH_MISMATCH: {err}",
        )
    except SignCountReplayError as err:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_replay_event(
            db=db,
            request_id=request_id,
            approver_id=approver.approver_id,
            reason="SIGN_COUNT_REPLAY",
            details={"error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SIGN_COUNT_REPLAY: {err}",
        )
    except (InvalidSignatureError, InvalidCredentialFormatError, WebAuthnAuthenticationError) as err:
        challenge_store.burn_approval_challenge(challenge.challenge_id)
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_APPROVAL_FAILED",
            result="FAILURE",
            request_id=request_id,
            details={"reason": "INVALID_WEBAUTHN_ASSERTION", "error": str(err)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_WEBAUTHN_ASSERTION: {err}",
        )

    # 10. Single-use guarantee: consume challenge
    challenge_store.consume_approval_challenge(challenge.challenge_id)

    # 11. Update approver sign counter
    approver.sign_count = approval_result.new_sign_count

    # 12. Persist Signature record
    sig_id = f"SIG-{uuid.uuid4().hex[:12].upper()}"
    raw_sig_str = (
        credential_payload.get("response", {}).get("signature")
        or submission.signature
        or ""
    )
    new_signature = Signature(
        signature_id=sig_id,
        request_id=payment.request_id,
        approver_id=approver.approver_id,
        timestamp=datetime.utcnow(),
        signature_status="VALID",
        nonce=challenge.nonce,
        expires_at=challenge.expires_at,
        payload_hash=reconstructed_canonical_hash,
        signature_payload=reconstructed_canonical_json,
        raw_signature=raw_sig_str,
    )
    db.add(new_signature)

    # 13. Update payment status to AUTHORIZED if signature requirements met
    existing_sigs_count = (
        db.query(Signature)
        .filter(
            Signature.request_id == payment.request_id,
            Signature.signature_status == "VALID",
        )
        .count()
    )
    total_valid = existing_sigs_count + 1
    req_signatures = payment.required_signatures if payment.required_signatures > 0 else 1

    ledger_entry_id = None
    if total_valid >= req_signatures:
        payment.status = "AUTHORIZED"
        # Record financial ledger entry upon full cryptographic authorization
        ledger_entry = (
            db.query(LedgerEntry)
            .filter(LedgerEntry.request_id == payment.request_id)
            .first()
        )
        if not ledger_entry:
            ledger_entry = LedgerEntry(
                ledger_id=f"LED-{uuid.uuid4().hex[:10].upper()}",
                request_id=payment.request_id,
                amount=payment.amount,
                currency=payment.currency,
                status="AUTHORIZED",
                authorized_at=datetime.utcnow(),
            )
            db.add(ledger_entry)
        else:
            ledger_entry.status = "AUTHORIZED"
            ledger_entry.authorized_at = datetime.utcnow()
        db.flush()
        ledger_entry_id = ledger_entry.ledger_id

    db.commit()
    db.refresh(payment)
    db.refresh(new_signature)

    # 14. Audit log successful approval
    log_event(
        db=db,
        user_id=approver.approver_id,
        action="PAYMENT_APPROVED_REALKEY",
        result="SUCCESS",
        request_id=payment.request_id,
        details={
            "signature_id": new_signature.signature_id,
            "canonical_hash": reconstructed_canonical_hash,
            "payment_status": payment.status,
            "sign_count": approver.sign_count,
            "signatures_recorded": total_valid,
            "required_signatures": req_signatures,
        },
    )

    if payment.status == "AUTHORIZED":
        log_event(
            db=db,
            user_id=approver.approver_id,
            action="PAYMENT_AUTHORIZED",
            result="SUCCESS",
            request_id=payment.request_id,
            details={
                "payment_status": "AUTHORIZED",
                "total_signatures": total_valid,
                "required_signatures": req_signatures,
                "routing_tier": challenge.payment_bundle.get("routing_tier"),
                "ledger_id": ledger_entry_id,
            },
        )

    is_authorized = (payment.status == "AUTHORIZED")
    msg = (
        "Payment successfully and cryptographically approved with REALKEY."
        if is_authorized
        else f"Signature verified. {total_valid} of {req_signatures} required signatures received."
    )

    return PaymentApprovalResponse(
        authorized=is_authorized,
        signature_status="VERIFIED",
        request_id=payment.request_id,
        approver_id=approver.approver_id,
        signature_id=new_signature.signature_id,
        canonical_hash=reconstructed_canonical_hash,
        payment_binding_valid=True,
        payment_status=payment.status,
        timestamp=new_signature.timestamp,
        message=msg,
    )



@router.post(
    "/payments/{request_id}/sign",
    response_model=PaymentApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for /payments/{request_id}/approve",
)
def sign_payment(
    request_id: str,
    submission: SignatureSubmissionRequest,
    db: Session = Depends(get_db),
):
    """Direct alias endpoint for /payments/{request_id}/approve."""
    return approve_payment(request_id=request_id, submission=submission, db=db)


@router.post(
    "/payments/{request_id}/tamper-demo",
    response_model=TamperDemoResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate payment tampering and demonstrate REALKEY cryptographic detection",
)
def tamper_demo(
    request_id: str,
    payload: TamperDemoRequest,
    db: Session = Depends(get_db),
):
    """
    Demonstrates REALKEY tamper detection:
    1. Loads payment from the authoritative database.
    2. Retrieves the latest valid Signature record for this payment.
    3. Validates that the targeted field is one of the 11 security-critical fields.
    4. Reconstructs the exact original canonical payment bundle.
    5. Creates an in-memory modified copy with the attacker's value.
    6. Demonstrates that the cryptographic canonical hash differs.
    7. Verifies that the existing cryptographic approval signature is rejected.
    8. Records a TAMPER_DETECTED security alert in the immutable audit log.
    9. Guarantees zero side effects: original payment and signature DB records remain 100% untouched.
    """
    # 1. Authoritative payment lookup
    payment = (
        db.query(PaymentRequest)
        .filter(PaymentRequest.request_id == request_id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PAYMENT_NOT_FOUND: Payment request '{request_id}' not found.",
        )

    # 2. Signature lookup
    signature = (
        db.query(Signature)
        .filter(
            Signature.request_id == request_id,
            Signature.signature_status == "VALID",
        )
        .order_by(Signature.timestamp.desc())
        .first()
    )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PAYMENT_NOT_SIGNED: Payment request '{request_id}' has not been approved yet. Complete the signing ceremony before running tamper demo.",
        )

    # 3. Field validation
    target_field = payload.field.strip() if isinstance(payload.field, str) else ""
    if target_field not in REQUIRED_PAYMENT_BUNDLE_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_FIELD: Field '{payload.field}' is not one of the 11 security-critical bundle fields: {sorted(list(REQUIRED_PAYMENT_BUNDLE_FIELDS))}.",
        )

    # 4. Extract authoritative original bundle
    original_bundle = None
    if signature.signature_payload:
        try:
            original_bundle = json.loads(signature.signature_payload)
        except Exception:
            original_bundle = None

    if not original_bundle:
        original_bundle = create_payment_bundle(
            vendor_id=payment.vendor_id,
            amount=payment.amount,
            currency=payment.currency,
            bank_account=payment.bank_account,
            invoice_id=payment.invoice_id,
            po_id=payment.po_id,
            timestamp=format_utc_timestamp(payment.timestamp or signature.timestamp),
            nonce=signature.nonce,
            expiry=format_utc_timestamp(signature.expires_at) if signature.expires_at else calculate_bundle_expiry(),
            policy_version=1,
            routing_tier=payment.routing_tier or "TIER_1",
        )

    # 5. Execute cryptographic tamper detection simulation
    demo_result = demonstrate_tamper_detection(
        original_bundle=original_bundle,
        field=target_field,
        tampered_value=payload.tampered_value,
    )

    # 6. Log security alert in immutable audit log if tampering was detected
    audit_logged = False
    if demo_result.tamper_detected:
        log_event(
            db=db,
            user_id=signature.approver_id,
            action="TAMPER_DETECTED",
            result="SECURITY_ALERT",
            request_id=request_id,
            details={
                "field_modified": demo_result.field_modified,
                "original_value": demo_result.original_value,
                "tampered_value": demo_result.tampered_value,
                "original_hash": demo_result.original_hash,
                "tampered_hash": demo_result.tampered_hash,
                "reason": demo_result.reason,
                "signature_id": signature.signature_id,
            },
        )
        audit_logged = True

    # Note: DB records (payment and signature) are NEVER modified.

    return TamperDemoResponse(
        tamper_detected=demo_result.tamper_detected,
        field_modified=demo_result.field_modified,
        original_value=demo_result.original_value,
        tampered_value=demo_result.tampered_value,
        original_hash=demo_result.original_hash,
        tampered_hash=demo_result.tampered_hash,
        hash_match=demo_result.hash_match,
        approval_valid=demo_result.approval_valid,
        reason=demo_result.reason,
        message=demo_result.message,
        audit_logged=audit_logged,
    )

