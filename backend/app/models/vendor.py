from datetime import datetime
from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id = Column(String, primary_key=True, index=True)
    vendor_name = Column(String, nullable=False)
    approved = Column(Boolean, default=True, nullable=False)
    bank_account = Column(String, nullable=False)
    onboarded_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    usual_amount_mean = Column(Float, default=0.0, nullable=False)
    usual_amount_std = Column(Float, default=0.0, nullable=False)
    usual_hour = Column(Float, default=12.0, nullable=False)
    usual_weekday = Column(Integer, default=2, nullable=False)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    payment_requests = relationship("PaymentRequest", back_populates="vendor")
