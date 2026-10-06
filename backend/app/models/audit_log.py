from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(String, primary_key=True, index=True)
    sequence = Column(Integer, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    request_id = Column(String, ForeignKey("payment_requests.request_id"), nullable=True, index=True)
    result = Column(String, nullable=False)
    details = Column(Text, nullable=True)  # JSON-encoded extra details
    previous_hash = Column(String, nullable=False)
    current_hash = Column(String, nullable=False)

    # Relationships
    payment_request = relationship("PaymentRequest", back_populates="audit_logs")
