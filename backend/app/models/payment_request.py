from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    request_id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    bank_account = Column(String, nullable=False)
    invoice_id = Column(String, nullable=False, index=True)
    po_id = Column(String, ForeignKey("purchase_orders.po_id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    channel = Column(String, default="portal", nullable=False)
    document_quality_score = Column(Float, default=1.0, nullable=False)
    status = Column(String, default="PENDING", nullable=False, index=True)

    # Separation of duties tracking
    requester_id = Column(String, nullable=True)
    processor_id = Column(String, nullable=True)

    @property
    def preparer_id(self) -> Optional[str]:
        """Authoritative identity of the preparer/creator of the payment request."""
        return self.requester_id

    @preparer_id.setter
    def preparer_id(self, value: Optional[str]) -> None:
        self.requester_id = value

    # ML scoring & explanation results
    fraud_probability = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_reasons = Column(Text, nullable=True)  # JSON-encoded reasons from SHAP/ML

    # Policy routing results
    routing_tier = Column(String, nullable=True)
    required_signatures = Column(Integer, default=0, nullable=False)

    # Relationships
    vendor = relationship("Vendor", back_populates="payment_requests")
    purchase_order = relationship("PurchaseOrder", back_populates="payment_requests")
    signatures = relationship("Signature", back_populates="payment_request")
    ledger_entries = relationship("LedgerEntry", back_populates="payment_request")
    audit_logs = relationship("AuditLog", back_populates="payment_request")
