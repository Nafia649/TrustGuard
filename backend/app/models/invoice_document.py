from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class InvoiceDocument(Base):
    __tablename__ = "invoice_documents"

    document_id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploader_id = Column(String, nullable=True)
    status = Column(String, default="UPLOADED", nullable=False, index=True)

    # JSON-encoded extraction and vendor matching results
    extracted_data = Column(Text, nullable=True)
    vendor_match = Column(Text, nullable=True)

    # Linked payment request after creation
    payment_request_id = Column(String, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
