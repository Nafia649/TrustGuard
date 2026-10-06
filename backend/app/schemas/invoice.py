import json
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.payment import PaymentResponse


class InvoiceLineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


class StructuredOCRResult(BaseModel):
    """
    Structured data extracted from an invoice document.
    Important: Do not invent values when OCR cannot find something.
    Use null / missing fields instead.
    """
    vendor_name: Optional[str] = None
    vendor_id: Optional[str] = None
    invoice_id: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    po_id: Optional[str] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None
    bank_account: Optional[str] = None
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    source_filename: str = ""
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_text: Optional[str] = None
    validation_warnings: List[str] = Field(default_factory=list)


class VendorMatchResult(BaseModel):
    """
    Result of comparing extracted invoice details with the vendor master.
    OCR must NEVER automatically approve a vendor.
    If no match exists, status is NEW_OR_UNREGISTERED and is_approved is False.
    """
    status: str = Field(..., description="EXACT_ID, EXACT_NAME, NORMALIZED_NAME, or NEW_OR_UNREGISTERED")
    matched_vendor_id: Optional[str] = None
    matched_vendor_name: Optional[str] = None
    is_approved: bool = False
    bank_account_matches: Optional[bool] = None
    message: str = ""


class InvoiceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    upload_timestamp: datetime
    status: str
    extracted_data: Optional[StructuredOCRResult] = None
    vendor_match: Optional[VendorMatchResult] = None
    payment_request_id: Optional[str] = None
    error_message: Optional[str] = None

    @field_validator("extracted_data", mode="before")
    @classmethod
    def parse_extracted_data(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return v

    @field_validator("vendor_match", mode="before")
    @classmethod
    def parse_vendor_match(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return v


class InvoiceReviewRequest(BaseModel):
    """
    User review/confirmation payload allowing verification or correction
    of extracted invoice data before creating a payment request.
    """
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    invoice_id: str = Field(..., description="Invoice identifier / number")
    amount: float = Field(..., gt=0, description="Total amount to be paid")
    currency: str = Field(default="INR", description="Currency code")
    bank_account: Optional[str] = None
    po_id: Optional[str] = None
    requester_id: Optional[str] = "emp_001"
    channel: str = "portal"


class InvoicePaymentCreationResponse(BaseModel):
    """
    Response returned after creating a PaymentRequest from an invoice document.
    """
    document_id: str
    payment_request_id: str
    vendor_id: str
    is_new_vendor: bool
    payment: PaymentResponse


class InvoiceSettlementStatusResponse(BaseModel):
    """
    Settlement and payment obligation status for an invoice.
    Tracks whether an invoice is UNPAID, PENDING_APPROVAL, or SETTLED.
    """
    invoice_id: str
    vendor_id: Optional[str] = None
    settlement_status: str  # "UNPAID", "PENDING_APPROVAL", "SETTLED"
    invoice_total: float
    total_paid: float
    remaining_payable: float
    payment_requests: List[str] = Field(default_factory=list)
