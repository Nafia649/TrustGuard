from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, String, Boolean
from app.database import Base


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    version = Column(Integer, primary_key=True, index=True)
    policy_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String, default="system", nullable=False)
    active = Column(Boolean, default=True, nullable=False)
