"""
TrustGuard OCR & Document Processing Package.
"""
from app.services.ocr.ocr_engine import ocr_engine
from app.services.ocr.parser import parse_invoice_text
from app.services.ocr.vendor_matcher import match_vendor

__all__ = ["ocr_engine", "parse_invoice_text", "match_vendor"]
