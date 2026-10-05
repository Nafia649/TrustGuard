from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    grn_id = Column(String, primary_key=True, index=True)
    po_id = Column(String, ForeignKey("purchase_orders.po_id"), nullable=False, index=True)
    received = Column(Boolean, default=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipts")
