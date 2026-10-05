from sqlalchemy import Column, String, Boolean, Integer, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Approver(Base):
    __tablename__ = "approvers"

    approver_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # e.g., "senior_administrator", "finance_head", "senior_executive"
    active = Column(Boolean, default=True, nullable=False)
    credential_id = Column(String, nullable=True)
    public_key = Column(Text, nullable=True)
    sign_count = Column(Integer, default=0, nullable=False)

    # Relationships
    signatures = relationship("Signature", back_populates="approver")
