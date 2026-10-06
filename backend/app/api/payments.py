import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.payment_request import PaymentRequest
from app.schemas.payment import PaymentRequestCreate, PaymentResponse
from app.services.audit_service import log_event

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
        requester_id=payment_in.requester_id,
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
        user_id=payment_in.requester_id or "anonymous_requester",
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
