from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Signature(Base):
    __tablename__ = "signatures"

    signature_id = Column(String, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("payment_requests.request_id"), nullable=False, index=True)
    approver_id = Column(String, ForeignKey("approvers.approver_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    signature_status = Column(String, default="VALID", nullable=False)  # "VALID", "INVALID", "REVOKED"
    nonce = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    payload_hash = Column(String, nullable=True)
    signature_payload = Column(Text, nullable=True)  # Canonical JSON string of the exact signed bundle
    raw_signature = Column(Text, nullable=True)

    # Relationships
    payment_request = relationship("PaymentRequest", back_populates="signatures")
    approver = relationship("Approver", back_populates="signatures")
