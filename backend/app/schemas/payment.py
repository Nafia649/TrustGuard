from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PaymentRequestCreate(BaseModel):
    vendor_id: str = Field(..., description="Target vendor identifier")
    amount: float = Field(..., gt=0, description="Payment amount (must be positive)")
    currency: str = Field(default="INR", description="Currency ISO code")
    bank_account: str = Field(..., description="Beneficiary bank account number")
    invoice_id: str = Field(..., description="Invoice reference ID")
    po_id: Optional[str] = Field(default=None, description="Optional linked Purchase Order ID")
    channel: str = Field(default="portal", description="Payment channel/source")
    document_quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Quality score of invoice doc")
    requester_id: Optional[str] = Field(default="emp_001", description="Employee creating the request")
    preparer_id: Optional[str] = Field(default=None, description="Alias for requester_id (payment preparer)")


class RiskReason(BaseModel):
    feature: str
    impact: str
    description: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    vendor_id: str
    amount: float
    currency: str
    bank_account: str
    invoice_id: str
    po_id: Optional[str] = None
    timestamp: datetime
    channel: str
    document_quality_score: float
    status: str
    requester_id: Optional[str] = None
    preparer_id: Optional[str] = None
    processor_id: Optional[str] = None
    fraud_probability: Optional[float] = None
    risk_score: Optional[float] = None
    risk_reasons: Optional[Any] = None
    routing_tier: Optional[str] = None
    required_signatures: int = 0
