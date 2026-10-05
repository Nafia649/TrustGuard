from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class LedgerEntry(Base):
    """Mock ledger entry representing simulated financial settlement."""
    __tablename__ = "ledger_entries"

    ledger_id = Column(String, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("payment_requests.request_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    status = Column(String, default="PENDING", nullable=False, index=True)  # PENDING, AUTHORIZED, RELEASED
    authorized_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)

    # Relationships
    payment_request = relationship("PaymentRequest", back_populates="ledger_entries")
