import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.invoice_document import InvoiceDocument
from app.models.payment_request import PaymentRequest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.schemas.invoice import (
    InvoiceDocumentResponse,
    InvoicePaymentCreationResponse,
    InvoiceReviewRequest,
    StructuredOCRResult,
    VendorMatchResult,
)
from app.schemas.payment import PaymentResponse
from app.services.audit_service import log_event
from app.services.ocr.ocr_engine import ocr_engine
from app.services.ocr.parser import parse_invoice_text
from app.services.ocr.vendor_matcher import match_vendor

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def ensure_upload_dir() -> str:
    """Ensures the upload directory exists and returns its canonical path."""
    upload_path = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(upload_path, exist_ok=True)
    return upload_path


def validate_file(file: UploadFile) -> str:
    """
    Validates uploaded file against extension, safe filename, and size.
    Returns the normalized file extension.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty.",
        )

    # Protect against path traversal in filenames
    clean_filename = os.path.basename(file.filename)
    ext = os.path.splitext(clean_filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file format '{ext}'. Allowed formats: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    return ext


def process_invoice_upload(
    db: Session,
    file: UploadFile,
    file_bytes: bytes,
    uploader_id: Optional[str] = "emp_accounts_01",
) -> InvoiceDocumentResponse:
    """
    Handles file upload, persistence, OCR text extraction, parsing, and vendor matching.
    """
    ext = validate_file(file)

    # Validate file size
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb} MB.",
        )

    # Generate persistent safe document ID and storage path
    document_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    safe_filename = f"{document_id}{ext}"
    upload_dir = ensure_upload_dir()
    file_path = os.path.join(upload_dir, safe_filename)

    # Write file to safe storage
    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist uploaded document: {str(e)}",
        )

    clean_orig_name = os.path.basename(file.filename or "invoice")

    # Record document in DB
    doc_record = InvoiceDocument(
        document_id=document_id,
        filename=safe_filename,
        original_filename=clean_orig_name,
        file_path=file_path,
        file_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        upload_timestamp=datetime.utcnow(),
        uploader_id=uploader_id,
        status="UPLOADED",
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # Append audit event: INVOICE_UPLOADED
    log_event(
        db=db,
        user_id=uploader_id or "anonymous_uploader",
        action="INVOICE_UPLOADED",
        result="SUCCESS",
        request_id=None,
        details={
            "document_id": document_id,
            "filename": clean_orig_name,
            "file_size_bytes": file_size,
            "file_type": doc_record.file_type,
        },
    )

    # Run OCR & Structured Extraction
    try:
        raw_text, base_conf, ocr_warnings = ocr_engine.extract_text(
            file_path=file_path,
            file_type=doc_record.file_type,
        )

        extracted = parse_invoice_text(
            raw_text=raw_text,
            source_filename=clean_orig_name,
            engine_confidence=base_conf,
        )
        if ocr_warnings:
            extracted.validation_warnings.extend(ocr_warnings)

        # Match vendor
        v_match = match_vendor(db, extracted)

        doc_record.extracted_data = extracted.model_dump_json()
        doc_record.vendor_match = v_match.model_dump_json()
        doc_record.status = "EXTRACTED"
        db.commit()
        db.refresh(doc_record)

        # Append audit event: INVOICE_EXTRACTED
        log_event(
            db=db,
            user_id="trustguard_ocr_extractor",
            action="INVOICE_EXTRACTED",
            result="SUCCESS",
            request_id=None,
            details={
                "document_id": document_id,
                "invoice_id": extracted.invoice_id,
                "vendor_name": extracted.vendor_name,
                "total_amount": extracted.total_amount,
                "confidence": extracted.confidence,
                "vendor_match_status": v_match.status,
            },
        )

        return InvoiceDocumentResponse(
            document_id=doc_record.document_id,
            filename=doc_record.filename,
            original_filename=doc_record.original_filename,
            file_type=doc_record.file_type,
            file_size=doc_record.file_size,
            upload_timestamp=doc_record.upload_timestamp,
            status=doc_record.status,
            extracted_data=extracted,
            vendor_match=v_match,
            payment_request_id=doc_record.payment_request_id,
            error_message=None,
        )
    except Exception as e:
        doc_record.status = "FAILED"
        doc_record.error_message = str(e)
        db.commit()

        log_event(
            db=db,
            user_id="trustguard_ocr_extractor",
            action="INVOICE_EXTRACTION_FAILED",
            result="FAILURE",
            request_id=None,
            details={
                "document_id": document_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR extraction encountered an error: {str(e)}",
        )


def review_invoice_document(
    db: Session,
    document_id: str,
    review_in: InvoiceReviewRequest,
) -> InvoiceDocumentResponse:
    """
    Allows a human reviewer to review and adjust extracted invoice values before payment request creation.
    """
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice document '{document_id}' not found.",
        )

    # Load existing extracted data or create fresh container
    extracted_dict = {}
    if doc.extracted_data:
        try:
            extracted_dict = json.loads(doc.extracted_data)
        except Exception:
            pass

    # Update extracted dict with reviewed fields
    extracted_dict["invoice_id"] = review_in.invoice_id
    extracted_dict["total_amount"] = review_in.amount
    extracted_dict["currency"] = review_in.currency
    if review_in.bank_account:
        extracted_dict["bank_account"] = review_in.bank_account
    if review_in.po_id:
        extracted_dict["po_id"] = review_in.po_id
    if review_in.vendor_name:
        extracted_dict["vendor_name"] = review_in.vendor_name
    if review_in.vendor_id:
        extracted_dict["vendor_id"] = review_in.vendor_id

    # Re-run vendor matching with reviewed fields
    temp_extracted = StructuredOCRResult(**extracted_dict)
    v_match = match_vendor(db, temp_extracted)

    doc.extracted_data = temp_extracted.model_dump_json()
    doc.vendor_match = v_match.model_dump_json()
    doc.status = "REVIEWED"
    db.commit()
    db.refresh(doc)

    log_event(
        db=db,
        user_id=review_in.requester_id or "human_reviewer",
        action="INVOICE_REVIEWED",
        result="SUCCESS",
        request_id=None,
        details={
            "document_id": document_id,
            "invoice_id": review_in.invoice_id,
            "amount": review_in.amount,
            "vendor_name": review_in.vendor_name,
            "vendor_id": review_in.vendor_id,
            "matched_status": v_match.status,
        },
    )

    return InvoiceDocumentResponse(
        document_id=doc.document_id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        upload_timestamp=doc.upload_timestamp,
        status=doc.status,
        extracted_data=temp_extracted,
        vendor_match=v_match,
        payment_request_id=doc.payment_request_id,
        error_message=None,
    )


def create_payment_request_from_invoice(
    db: Session,
    document_id: str,
    confirmation: Optional[InvoiceReviewRequest] = None,
) -> InvoicePaymentCreationResponse:
    """
    Creates a PaymentRequest from an extracted invoice document.
    Validates required fields, checks for duplicate invoice submissions,
    handles new/unregistered vendors safely (never marking them approved),
    and connects directly to the existing TrustGuard pipeline.
    """
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice document '{document_id}' not found.",
        )

    # Parse extracted data
    extracted: Optional[StructuredOCRResult] = None
    if doc.extracted_data:
        try:
            extracted = StructuredOCRResult(**json.loads(doc.extracted_data))
        except Exception:
            pass

    # Override with confirmation payload if provided
    invoice_id = confirmation.invoice_id if confirmation else (extracted.invoice_id if extracted else None)
    amount = confirmation.amount if confirmation else (extracted.total_amount if extracted else None)
    currency = confirmation.currency if confirmation else (extracted.currency if extracted else "INR")
    bank_account = confirmation.bank_account if confirmation else (extracted.bank_account if extracted else None)
    po_id = confirmation.po_id if confirmation else (extracted.po_id if extracted else None)
    
    if po_id:
        po_record = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
        if not po_record:
            po_id = None
            
    vendor_id = confirmation.vendor_id if confirmation else (extracted.vendor_id if extracted else None)
    vendor_name = confirmation.vendor_name if confirmation else (extracted.vendor_name if extracted else None)
    requester_id = (confirmation.requester_id if confirmation else None) or doc.uploader_id or "emp_accounts_01"
    quality_score = extracted.confidence if extracted else 0.85

    # 1. Validation of required payment fields
    if not invoice_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice ID / number is required to create a payment request.",
        )

    if amount is None or amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid positive payment amount is required.",
        )

    # 2. Vendor Identification & Safe Registration
    # Determine target vendor in vendor master
    resolved_vendor: Optional[Vendor] = None
    if vendor_id:
        resolved_vendor = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()

    if not resolved_vendor and vendor_name:
        # Check by name matching
        v_match = match_vendor(
            db,
            StructuredOCRResult(
                vendor_name=vendor_name,
                vendor_id=vendor_id,
                bank_account=bank_account,
            ),
        )
        if v_match.matched_vendor_id:
            resolved_vendor = db.query(Vendor).filter(Vendor.vendor_id == v_match.matched_vendor_id).first()

    is_new_vendor = False
    if not resolved_vendor:
        # ARCHITECTURE RULE:
        # Do NOT reject a legitimate new vendor merely because vendor_id is missing.
        # Register in Vendor master as UNAPPROVED (approved = False) so downstream
        # three-way match and policy engine can trigger appropriate escalation.
        is_new_vendor = True
        new_v_id = f"VEND-UNREG-{uuid.uuid4().hex[:6].upper()}"
        resolved_vendor = Vendor(
            vendor_id=new_v_id,
            vendor_name=vendor_name or "Unregistered Vendor",
            approved=False,  # CRITICAL: Always False!
            bank_account=bank_account or "UNKNOWN-ACCOUNT",
            onboarded_date=datetime.utcnow(),
            usual_amount_mean=0.0,
            usual_amount_std=0.0,
            usual_hour=12.0,
            usual_weekday=2,
        )
        db.add(resolved_vendor)
        db.commit()
        db.refresh(resolved_vendor)

        log_event(
            db=db,
            user_id="trustguard_vendor_matcher",
            action="VENDOR_UNMATCHED",
            result="FLAGGED",
            request_id=None,
            details={
                "vendor_id": new_v_id,
                "vendor_name": resolved_vendor.vendor_name,
                "approved": False,
                "status": "NEW_OR_UNREGISTERED",
            },
        )
    else:
        log_event(
            db=db,
            user_id="trustguard_vendor_matcher",
            action="VENDOR_MATCHED",
            result="SUCCESS",
            request_id=None,
            details={
                "vendor_id": resolved_vendor.vendor_id,
                "vendor_name": resolved_vendor.vendor_name,
                "approved": resolved_vendor.approved,
            },
        )

    # 3. Duplicate Invoice & Settlement Protection
    existing_payments = (
        db.query(PaymentRequest)
        .filter(
            PaymentRequest.vendor_id == resolved_vendor.vendor_id,
            PaymentRequest.invoice_id == invoice_id,
        )
        .all()
    )
    if existing_payments:
        settled = next((p for p in existing_payments if p.status in ("AUTHORIZED", "RELEASED")), None)
        if settled:
            log_event(
                db=db,
                user_id=requester_id,
                action="INVOICE_ALREADY_SETTLED",
                result="BLOCKED",
                request_id=settled.request_id,
                details={
                    "document_id": document_id,
                    "vendor_id": resolved_vendor.vendor_id,
                    "invoice_id": invoice_id,
                    "existing_status": settled.status,
                    "settled_amount": settled.amount,
                    "reason": "ALREADY_SETTLED",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Invoice already settled: Invoice '{invoice_id}' for vendor '{resolved_vendor.vendor_id}' "
                    f"has already been settled and paid (Existing Request ID: {settled.request_id}, Status: {settled.status}). "
                    f"Total remaining payable is 0."
                ),
            )

        pending = next((p for p in existing_payments if p.status in ("PENDING", "ON_HOLD", "MANUAL_REVIEW_REQUIRED")), None)
        if pending:
            log_event(
                db=db,
                user_id=requester_id,
                action="DUPLICATE_INVOICE_DETECTED",
                result="BLOCKED",
                request_id=pending.request_id,
                details={
                    "document_id": document_id,
                    "vendor_id": resolved_vendor.vendor_id,
                    "invoice_id": invoice_id,
                    "existing_status": pending.status,
                    "reason": "PENDING_DUPLICATE",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Duplicate invoice detected: Invoice '{invoice_id}' has already been registered "
                    f"for vendor '{resolved_vendor.vendor_id}' (Existing Request ID: {pending.request_id}, Status: {pending.status})."
                ),
            )

    # 4. Generate persistent Request ID and instantiate PaymentRequest
    request_id = f"REQ-OCR-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    channel = (confirmation.channel if confirmation and confirmation.channel else None) or "ocr_upload"

    new_payment = PaymentRequest(
        request_id=request_id,
        vendor_id=resolved_vendor.vendor_id,
        amount=amount,
        currency=(currency or "INR").upper(),
        bank_account=bank_account or resolved_vendor.bank_account,
        invoice_id=invoice_id,
        po_id=po_id,
        timestamp=now,
        channel=channel,
        document_quality_score=quality_score,
        status="PENDING",
        requester_id=requester_id,
        processor_id=None,
        fraud_probability=None,
        risk_score=None,
        risk_reasons=None,
        routing_tier=None,
        required_signatures=0,
    )

    db.add(new_payment)

    # Link Document to Payment Request
    doc.payment_request_id = request_id
    doc.status = "PAYMENT_CREATED"

    db.commit()
    db.refresh(new_payment)
    db.refresh(doc)

    # 5. Append audit event: PAYMENT_CREATED_FROM_INVOICE
    log_event(
        db=db,
        user_id=requester_id,
        action="PAYMENT_CREATED_FROM_INVOICE",
        result="SUCCESS",
        request_id=request_id,
        details={
            "document_id": document_id,
            "request_id": request_id,
            "vendor_id": resolved_vendor.vendor_id,
            "is_new_vendor": is_new_vendor,
            "amount": amount,
            "currency": currency,
            "invoice_id": invoice_id,
            "po_id": po_id,
            "document_quality_score": quality_score,
        },
    )

    return InvoicePaymentCreationResponse(
        document_id=document_id,
        payment_request_id=request_id,
        vendor_id=resolved_vendor.vendor_id,
        is_new_vendor=is_new_vendor,
        payment=PaymentResponse.model_validate(new_payment),
    )
