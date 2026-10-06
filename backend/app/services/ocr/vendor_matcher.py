import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models.vendor import Vendor
from app.schemas.invoice import StructuredOCRResult, VendorMatchResult


def normalize_vendor_name(name: str) -> str:
    """
    Normalizes a business name by stripping common corporate suffixes,
    punctuation, and excess whitespace for conservative fuzzy matching.
    """
    if not name:
        return ""
    cleaned = name.lower()
    # Remove common company legal suffixes
    cleaned = re.sub(
        r"\b(ltd|limited|corp|corporation|inc|incorporated|pvt|private|llc|enterprises|supplies|services|group|co)\b",
        "",
        cleaned,
    )
    # Remove punctuation
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    # Collapse whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def match_vendor(db: Session, extracted: StructuredOCRResult) -> VendorMatchResult:
    """
    Matches extracted invoice information against registered vendors.
    Hierarchy:
    1. Explicit vendor ID if present and matches a registered vendor
    2. Exact vendor name (case-insensitive)
    3. Normalized name matching

    CRITICAL RULE:
    OCR is an EXTRACTION layer.
    OCR must NEVER automatically create or mark a vendor as approved.
    If no match exists, status must be NEW_OR_UNREGISTERED with is_approved=False.
    """
    # 1. Match by Explicit Vendor ID
    if extracted.vendor_id:
        vendor_by_id = (
            db.query(Vendor)
            .filter(Vendor.vendor_id == extracted.vendor_id.strip().upper())
            .first()
        )
        if vendor_by_id:
            bank_match = None
            if extracted.bank_account:
                bank_match = bool(
                    vendor_by_id.bank_account.strip().upper() == extracted.bank_account.strip().upper()
                )
            return VendorMatchResult(
                status="EXACT_ID",
                matched_vendor_id=vendor_by_id.vendor_id,
                matched_vendor_name=vendor_by_id.vendor_name,
                is_approved=vendor_by_id.approved,
                bank_account_matches=bank_match,
                message=f"Matched vendor by explicit ID '{vendor_by_id.vendor_id}' ({vendor_by_id.vendor_name}).",
            )

    # 2. Match by Exact Vendor Name
    if extracted.vendor_name:
        clean_extracted_name = extracted.vendor_name.strip()
        exact_vendor = (
            db.query(Vendor)
            .filter(Vendor.vendor_name.ilike(clean_extracted_name))
            .first()
        )
        if exact_vendor:
            bank_match = None
            if extracted.bank_account:
                bank_match = bool(
                    exact_vendor.bank_account.strip().upper() == extracted.bank_account.strip().upper()
                )
            return VendorMatchResult(
                status="EXACT_NAME",
                matched_vendor_id=exact_vendor.vendor_id,
                matched_vendor_name=exact_vendor.vendor_name,
                is_approved=exact_vendor.approved,
                bank_account_matches=bank_match,
                message=f"Matched vendor by exact name '{exact_vendor.vendor_name}' ({exact_vendor.vendor_id}).",
            )

        # 3. Match by Normalized Name
        norm_extracted = normalize_vendor_name(clean_extracted_name)
        if norm_extracted and len(norm_extracted) >= 3:
            all_vendors = db.query(Vendor).all()
            for v in all_vendors:
                norm_master = normalize_vendor_name(v.vendor_name)
                if norm_master and (norm_extracted == norm_master or norm_extracted in norm_master or norm_master in norm_extracted):
                    bank_match = None
                    if extracted.bank_account:
                        bank_match = bool(
                            v.bank_account.strip().upper() == extracted.bank_account.strip().upper()
                        )
                    return VendorMatchResult(
                        status="NORMALIZED_NAME",
                        matched_vendor_id=v.vendor_id,
                        matched_vendor_name=v.vendor_name,
                        is_approved=v.approved,
                        bank_account_matches=bank_match,
                        message=f"Matched vendor by normalized name '{v.vendor_name}' ({v.vendor_id}).",
                    )

    # 4. No Match Found
    return VendorMatchResult(
        status="NEW_OR_UNREGISTERED",
        matched_vendor_id=None,
        matched_vendor_name=extracted.vendor_name,
        is_approved=False,
        bank_account_matches=None,
        message=(
            f"Vendor '{extracted.vendor_name or extracted.vendor_id or 'Unknown'}' is not in the registered "
            "vendor master. Marked as unapproved/new vendor."
        ),
    )
