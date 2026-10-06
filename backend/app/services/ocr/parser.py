import re
from datetime import datetime
from typing import List, Optional, Tuple
from app.schemas.invoice import InvoiceLineItem, StructuredOCRResult


def clean_number(val_str: str) -> Optional[float]:
    """
    Cleans a numeric string (e.g. '₹ 45,000.00', '150,000', '45.000,00') into a float.
    """
    if not val_str:
        return None
    # Strip currency symbols and whitespace
    cleaned = re.sub(r"[₹$€£\s]", "", val_str)
    # Remove 'Rs.' or 'INR' or 'USD'
    cleaned = re.sub(r"(?i)rs\.?|inr|usd|eur", "", cleaned)
    # Handle European format like 45.000,00 vs standard 45,000.00
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # European format: 45.000,00
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # Standard format: 45,000.00
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Could be 45,000 or 45,00
        parts = cleaned.split(",")
        if len(parts[-1]) == 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    # Match float
    match = re.search(r"[-+]?\d*\.?\d+", cleaned)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def parse_date(date_str: str) -> Optional[str]:
    """
    Normalizes a date string to ISO YYYY-MM-DD format if possible.
    """
    if not date_str:
        return None
    cleaned = date_str.strip()

    # Try standard YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", cleaned)
    if iso_match:
        y, m, d = iso_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Try DD/MM/YYYY or DD-MM-YYYY
    dmy_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", cleaned)
    if dmy_match:
        d, m, y = dmy_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    return cleaned


def parse_invoice_text(
    raw_text: str,
    source_filename: str = "",
    engine_confidence: float = 0.95,
) -> StructuredOCRResult:
    """
    Parses unformatted or semi-structured raw invoice text into StructuredOCRResult.
    Adheres strictly to the Data Integrity Rule: never invents values that cannot be found.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    warnings: List[str] = []

    # 1. Currency Detection
    currency = "INR"
    if "$" in raw_text or re.search(r"\bUSD\b", raw_text, re.IGNORECASE):
        currency = "USD"
    elif "€" in raw_text or re.search(r"\bEUR\b", raw_text, re.IGNORECASE):
        currency = "EUR"
    elif "₹" in raw_text or re.search(r"\bINR\b|\bRs\.?\b", raw_text, re.IGNORECASE):
        currency = "INR"

    # 2. Invoice ID Extraction
    invoice_id: Optional[str] = None
    inv_patterns = [
        r"(?i)(?:invoice\s*(?:number|no\.?|#|id)|bill\s*(?:number|no\.?|#))[:\s]*([A-Z0-9\-_/]+)",
        r"\b(INV[-_]?[A-Z0-9\-_]+)\b",
    ]
    for pattern in inv_patterns:
        match = re.search(pattern, raw_text)
        if match:
            candidate = match.group(1).strip()
            # Exclude false positives like 'DATE' or 'DUE'
            if len(candidate) >= 3 and not re.match(r"(?i)^(date|due|total|amount)$", candidate):
                invoice_id = candidate
                break

    if not invoice_id:
        warnings.append("Could not extract invoice number / ID.")

    # 3. PO ID Extraction
    po_id: Optional[str] = None
    po_patterns = [
        r"(?i)(?:purchase\s*order|po\s*(?:number|no\.?|#|id)?|order\s*(?:number|no\.?|#))[:\s]*([A-Z0-9\-_/]+)",
        r"\b(PO[-_]?[0-9]{4}[-_]?[0-9]+)\b",
    ]
    for pattern in po_patterns:
        match = re.search(pattern, raw_text)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and not re.match(r"(?i)^(date|total|none|n/a)$", candidate):
                po_id = candidate
                break

    # 4. Vendor ID & Vendor Name Extraction
    vendor_id: Optional[str] = None
    vend_id_match = re.search(r"(?i)(?:vendor\s*(?:id|#|number|code))[:\s]*([A-Z0-9\-_]+)", raw_text)
    if vend_id_match:
        vendor_id = vend_id_match.group(1).strip()
    elif re.search(r"\b(VEND[-_][0-9]+)\b", raw_text):
        vendor_id = re.search(r"\b(VEND[-_][0-9]+)\b", raw_text).group(1).strip()

    vendor_name: Optional[str] = None
    # Check explicit label
    vend_name_match = re.search(
        r"(?i)(?:vendor|supplier|seller|billed\s*by|from)[:\s]+([^\n\r,]+)",
        raw_text,
    )
    if vend_name_match:
        cand_name = vend_name_match.group(1).strip()
        # Clean out labels
        cand_name = re.sub(r"(?i)\b(?:name|invoice|gstin|pan|tax|id)\b:?.*", "", cand_name).strip()
        if len(cand_name) > 2:
            vendor_name = cand_name

    # If no labeled vendor, use top header lines (common in invoices where company header is line 1 or 2)
    if not vendor_name and lines:
        for line in lines[:4]:
            if not re.search(r"(?i)invoice|tax|bill\s+to|date|original|gstin|phone|email", line):
                if len(line) > 3 and not line.isupper() or len(line.split()) <= 6:
                    vendor_name = line
                    break

    if not vendor_name and not vendor_id:
        warnings.append("Could not extract vendor name or vendor ID.")

    # 5. Dates
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None

    date_match = re.search(
        r"(?i)(?:invoice\s*date|bill\s*date|dated|date)[:\s]+([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        raw_text,
    )
    if date_match:
        invoice_date = parse_date(date_match.group(1).strip())

    due_match = re.search(
        r"(?i)(?:due\s*date|payment\s*due)[:\s]+([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        raw_text,
    )
    if due_match:
        due_date = parse_date(due_match.group(1).strip())

    # 6. Amounts: Total, Subtotal, Tax
    total_amount: Optional[float] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None

    # Search for Grand Total / Total Amount / Amount Due
    total_patterns = [
        r"(?i)(?:grand\s*total|total\s*amount|amount\s*due|invoice\s*total|net\s*payable|total\s*payable)[:\s]*([^\r\n]+)",
        r"(?i)(?:\btotal\b)[:\s]*([^\r\n]+)",
    ]
    for pattern in total_patterns:
        match = re.search(pattern, raw_text)
        if match:
            captured = match.group(1).strip()
            if captured:
                val = clean_number(captured)
                if val is not None and val > 0:
                    total_amount = val
                    break

    # Subtotal
    subtotal_match = re.search(r"(?i)(?:sub\s*total|subtotal|net\s*amount)[:\s]*([^\r\n]+)", raw_text)
    if subtotal_match:
        cap_sub = subtotal_match.group(1).strip()
        if cap_sub:
            subtotal = clean_number(cap_sub)

    # Tax
    tax_match = re.search(r"(?i)(?:tax|gst|vat|cgst|sgst|igst)[:\s]*([^\r\n]+)", raw_text)
    if tax_match:
        cap_tax = tax_match.group(1).strip()
        if cap_tax:
            tax_amount = clean_number(cap_tax)

    if total_amount is None:
        warnings.append("Could not extract total amount.")

    # 7. Bank Account
    bank_account: Optional[str] = None
    bank_patterns = [
        r"(?i)(?:bank\s*a/?c|account\s*(?:number|no\.?|#)|bank\s*account)[:\s]*([A-Z0-9\-_]{6,25})",
        r"\b([A-Z]{3,5}-BANK-[0-9]{3,4})\b",
    ]
    for pattern in bank_patterns:
        match = re.search(pattern, raw_text)
        if match:
            bank_account = match.group(1).strip()
            break

    # 8. Line Items (optional heuristic)
    line_items: List[InvoiceLineItem] = []
    # Search for lines containing description, qty, unit price, total price
    # e.g., "Industrial Ball Bearings  100  400.00  40000.00"
    for line in lines:
        parts = re.split(r"\s{2,}|\t", line)
        if len(parts) >= 3:
            # Check if last element is a number
            last_val = clean_number(parts[-1])
            if last_val is not None:
                second_last = clean_number(parts[-2])
                desc = parts[0]
                if len(desc) > 3 and not re.search(r"(?i)total|tax|subtotal|balance|due", desc):
                    line_items.append(
                        InvoiceLineItem(
                            description=desc,
                            quantity=clean_number(parts[1]) if len(parts) >= 4 else 1.0,
                            unit_price=second_last,
                            total_price=last_val,
                        )
                    )

    # 9. Compute Overall Extraction Confidence Score
    confidence_weight = 0.0
    if invoice_id:
        confidence_weight += 0.25
    if total_amount is not None:
        confidence_weight += 0.30
    if vendor_name or vendor_id:
        confidence_weight += 0.20
    if po_id:
        confidence_weight += 0.10
    if bank_account:
        confidence_weight += 0.10
    if invoice_date:
        confidence_weight += 0.05

    final_confidence = round(min(1.0, max(0.1, confidence_weight * engine_confidence)), 2)

    return StructuredOCRResult(
        vendor_name=vendor_name,
        vendor_id=vendor_id,
        invoice_id=invoice_id,
        invoice_date=invoice_date,
        due_date=due_date,
        po_id=po_id,
        currency=currency,
        total_amount=total_amount,
        tax_amount=tax_amount,
        subtotal=subtotal,
        bank_account=bank_account,
        line_items=line_items,
        source_filename=source_filename,
        extraction_timestamp=datetime.utcnow(),
        confidence=final_confidence,
        raw_text=raw_text,
        validation_warnings=warnings,
    )
