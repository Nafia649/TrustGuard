from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

import json
from app.database import get_db
from app.models.invoice_document import InvoiceDocument
from app.models.payment_request import PaymentRequest
from app.schemas.invoice import (
    InvoiceDocumentResponse,
    InvoicePaymentCreationResponse,
    InvoiceReviewRequest,
    InvoiceSettlementStatusResponse,
)
from app.services.document_service import (
    create_payment_request_from_invoice,
    process_invoice_upload,
    review_invoice_document,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "/upload",
    response_model=InvoiceDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an invoice document (PDF, PNG, JPG) and perform OCR extraction",
)
async def upload_invoice(
    file: UploadFile = File(..., description="Invoice document file (PDF, PNG, JPG/JPEG)"),
    uploader_id: Optional[str] = Form(default="emp_accounts_01", description="Identifier of uploading employee"),
    db: Session = Depends(get_db),
):
    """
    Accepts an invoice document (PDF, PNG, JPG), validates file size and format,
    stores it securely, and runs OCR / structured text extraction and vendor matching.
    """
    file_bytes = await file.read()
    return process_invoice_upload(
        db=db,
        file=file,
        file_bytes=file_bytes,
        uploader_id=uploader_id,
    )


@router.get(
    "",
    response_model=List[InvoiceDocumentResponse],
    summary="List uploaded invoice documents",
)
def list_invoices(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. EXTRACTED, PAYMENT_CREATED)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Returns a list of uploaded invoices with extraction status and pagination."""
    query = db.query(InvoiceDocument)
    if status_filter:
        query = query.filter(InvoiceDocument.status == status_filter.upper())
    docs = query.order_by(InvoiceDocument.upload_timestamp.desc()).offset(offset).limit(limit).all()
    return docs


@router.get(
    "/{document_id}",
    response_model=InvoiceDocumentResponse,
    summary="Get invoice document and extracted OCR data by ID",
)
def get_invoice(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Fetches metadata, structured OCR results, and vendor match details for a document."""
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice document '{document_id}' not found.",
        )
    return doc


@router.post(
    "/{document_id}/review",
    response_model=InvoiceDocumentResponse,
    summary="Review and edit extracted invoice values before payment request creation",
)
def review_invoice(
    document_id: str,
    review_data: InvoiceReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Allows a human operator to verify or correct OCR-extracted invoice attributes.
    Re-evaluates vendor matching against the vendor master.
    """
    return review_invoice_document(db, document_id, review_data)


@router.post(
    "/{document_id}/create-payment-request",
    response_model=InvoicePaymentCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convert validated invoice into a PaymentRequest for the TrustGuard pipeline",
)
def create_payment_request(
    document_id: str,
    confirmation: Optional[InvoiceReviewRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Creates a PaymentRequest from an extracted invoice document.
    Prevents duplicate submissions and feeds the payment into the TrustGuard
    three-way matching, fraud risk scoring, policy routing, and REALKEY pipeline.
    """
    return create_payment_request_from_invoice(db, document_id, confirmation)


@router.get(
    "/{invoice_id}/settlement-status",
    response_model=InvoiceSettlementStatusResponse,
    summary="Get settlement and payment status for an invoice number",
)
def get_invoice_settlement_status(
    invoice_id: str,
    vendor_id: Optional[str] = Query(None, description="Optional vendor ID for scoped settlement query"),
    db: Session = Depends(get_db),
):
    """
    Checks whether an invoice is UNPAID, PENDING_APPROVAL, or fully SETTLED.
    Enforces that an invoice obligation cannot be paid more than once.
    """
    query = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == invoice_id)
    if vendor_id:
        query = query.filter(PaymentRequest.vendor_id == vendor_id)
    payments = query.all()

    if not payments:
        # Check if an uploaded document exists with this invoice_id
        invoice_total = 0.0
        doc = db.query(InvoiceDocument).filter(InvoiceDocument.extracted_data.like(f"%{invoice_id}%")).first()
        if doc and doc.extracted_data:
            try:
                data = json.loads(doc.extracted_data)
                invoice_total = float(data.get("total_amount") or 0.0)
            except Exception:
                pass

        return InvoiceSettlementStatusResponse(
            invoice_id=invoice_id,
            vendor_id=vendor_id,
            settlement_status="UNPAID",
            invoice_total=invoice_total,
            total_paid=0.0,
            remaining_payable=invoice_total,
            payment_requests=[],
        )

    settled_payments = [p for p in payments if p.status in ("AUTHORIZED", "RELEASED")]
    total_paid = sum(p.amount for p in settled_payments)
    first_payment = payments[0]
    invoice_total = first_payment.amount
    v_id = vendor_id or first_payment.vendor_id

    if settled_payments:
        settlement_status = "SETTLED"
        remaining = 0.0
    elif any(p.status in ("PENDING", "ON_HOLD", "MANUAL_REVIEW_REQUIRED") for p in payments):
        settlement_status = "PENDING_APPROVAL"
        remaining = max(0.0, invoice_total - total_paid)
    else:
        settlement_status = "UNPAID"
        remaining = max(0.0, invoice_total - total_paid)

    return InvoiceSettlementStatusResponse(
        invoice_id=invoice_id,
        vendor_id=v_id,
        settlement_status=settlement_status,
        invoice_total=invoice_total,
        total_paid=total_paid,
        remaining_payable=remaining,
        payment_requests=[p.request_id for p in payments],
    )

