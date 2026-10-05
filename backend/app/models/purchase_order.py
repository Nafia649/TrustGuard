from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="APPROVED", nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vendor = relationship("Vendor", back_populates="purchase_orders")
    goods_receipts = relationship("GoodsReceipt", back_populates="purchase_order")
    payment_requests = relationship("PaymentRequest", back_populates="purchase_order")
