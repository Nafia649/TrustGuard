import io
import json
import os
import pytest
import pymupdf as fitz

from app.services.audit_service import verify_chain


def create_sample_pdf(text: str) -> bytes:
    """Helper to generate a clean, in-memory PDF with specified text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


SAMPLE_INVOICE_TEXT = """
Acme Industrial Supplies
100 Industrial Parkway, Sector 4
GSTIN: 29ABCDE1234F1Z5

Invoice Number: INV-2026-8801
Invoice Date: 2026-10-06
Purchase Order: PO-2026-001
Vendor ID: VEND-001

Bill To:
Acme Ltd Corporate Accounts

Description                    Qty    Unit Price    Total Price
Precision Ball Bearings        100    400.00        40000.00
Maintenance Lubricant Kit      1      5000.00       5000.00

Subtotal: 45000.00
Tax: 0.00
Grand Total: ₹ 45,000.00
Bank Account: ACME-BANK-001
"""


@pytest.fixture(autouse=True)
def seed_data(client):
    """Ensure standard seeded state before each test."""
    client.post("/seed")


# 1. Text-based PDF invoice extraction
def test_upload_text_based_pdf_invoice(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    response = client.post(
        "/invoices/upload",
        files={"file": ("acme_invoice.pdf", pdf_bytes, "application/pdf")},
        data={"uploader_id": "test_user"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "EXTRACTED"
    assert data["extracted_data"]["invoice_id"] == "INV-2026-8801"
    assert data["extracted_data"]["total_amount"] == 45000.0
    assert data["extracted_data"]["po_id"] == "PO-2026-001"
    assert data["extracted_data"]["bank_account"] == "ACME-BANK-001"


# 2. Image / scanned invoice OCR handling
def test_upload_image_invoice_handling(client):
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    response = client.post(
        "/invoices/upload",
        files={"file": ("scanned_invoice.png", fake_png, "image/png")},
    )
    # Upload succeeds without crash, either OCR extracted or returns warning if Tesseract not installed
    assert response.status_code == 201
    data = response.json()
    assert data["status"] in ["EXTRACTED", "UPLOADED"]


# 3. Vendor extraction
def test_vendor_extraction(client):
    invoice_text = """
    Supplier: Acme Industrial Supplies
    Invoice #: INV-9901
    Total Amount: 12000.00
    """
    pdf_bytes = create_sample_pdf(invoice_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    extracted = res.json()["extracted_data"]
    assert "Acme Industrial Supplies" in extracted["vendor_name"]


# 4. Invoice number extraction
def test_invoice_number_extraction(client):
    invoice_text = "Bill Number: BILL-2026-777\nTotal: 1000.00"
    pdf_bytes = create_sample_pdf(invoice_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    assert res.json()["extracted_data"]["invoice_id"] == "BILL-2026-777"


# 5. Amount extraction with currency formatting
def test_amount_extraction_with_symbols(client):
    invoice_text = "Invoice No: INV-101\nGrand Total: ₹ 1,25,000.50"
    pdf_bytes = create_sample_pdf(invoice_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    assert res.json()["extracted_data"]["total_amount"] == 125000.50


# 6. Currency extraction
def test_currency_extraction(client):
    invoice_text = "Invoice #: INV-USD-01\nTotal Amount: $ 5,000.00\nUSD Currency"
    pdf_bytes = create_sample_pdf(invoice_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    assert res.json()["extracted_data"]["currency"] == "USD"


# 7. PO extraction
def test_po_extraction(client):
    invoice_text = "Invoice #: INV-102\nPurchase Order: PO-2026-001\nTotal: 2500.00"
    pdf_bytes = create_sample_pdf(invoice_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    assert res.json()["extracted_data"]["po_id"] == "PO-2026-001"


# 8. Bank account extraction
def test_bank_account_extraction(client):
    invoice_text = "Invoice #: INV-103\nBank A/C: ACME-BANK-001\nTotal: 3000.00"
    pdf_bytes = create_sample_pdf(invoice_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    assert res.json()["extracted_data"]["bank_account"] == "ACME-BANK-001"


# 9. Missing field handling (null values, no fabrication)
def test_missing_fields_not_fabricated(client):
    minimal_text = "Invoice Number: INV-MINIMAL-01\nTotal: 500.00"
    pdf_bytes = create_sample_pdf(minimal_text)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    extracted = res.json()["extracted_data"]
    assert extracted["invoice_id"] == "INV-MINIMAL-01"
    assert extracted["total_amount"] == 500.0
    assert extracted["po_id"] is None
    assert extracted["bank_account"] is None
    assert extracted["due_date"] is None


# 10. Invalid file type rejection
def test_invalid_file_type_rejected(client):
    res = client.post(
        "/invoices/upload",
        files={"file": ("malicious_payload.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert res.status_code == 415
    assert "Unsupported file format" in res.json()["detail"]


# 11. Oversized file rejection
def test_oversized_file_rejected(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 100)  # 100 bytes limit
    res = client.post(
        "/invoices/upload",
        files={"file": ("large_doc.pdf", b"x" * 200, "application/pdf")},
    )
    assert res.status_code == 413
    assert "exceeds maximum allowed size" in res.json()["detail"]


# 12. Duplicate invoice detection
def test_duplicate_invoice_blocked(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    # Upload and create payment
    upload_res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = upload_res.json()["document_id"]
    pay_res = client.post(f"/invoices/{doc_id}/create-payment-request")
    assert pay_res.status_code == 201

    # Upload same invoice again
    upload_res2 = client.post(
        "/invoices/upload",
        files={"file": ("invoice_copy.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id2 = upload_res2.json()["document_id"]
    # Attempting to create duplicate payment request must be rejected with 409
    dup_res = client.post(f"/invoices/{doc_id2}/create-payment-request")
    assert dup_res.status_code == 409
    assert "Duplicate invoice detected" in dup_res.json()["detail"]


# 13. Existing registered vendor match
def test_existing_vendor_match(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    v_match = res.json()["vendor_match"]
    assert v_match["matched_vendor_id"] == "VEND-001"
    assert v_match["is_approved"] is True
    assert v_match["bank_account_matches"] is True


# 14. Unknown / new vendor remains unapproved
def test_unknown_vendor_remains_unapproved(client):
    unknown_invoice = """
    Vendor: Unknown Phantom LLC
    Invoice #: INV-PHANTOM-001
    Grand Total: 85000.00
    Bank Account: PHANTOM-BANK-999
    """
    pdf_bytes = create_sample_pdf(unknown_invoice)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    v_match = res.json()["vendor_match"]
    assert v_match["status"] == "NEW_OR_UNREGISTERED"
    assert v_match["is_approved"] is False

    # Create payment request: vendor registered as unapproved
    doc_id = res.json()["document_id"]
    create_res = client.post(f"/invoices/{doc_id}/create-payment-request")
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["is_new_vendor"] is True


# 15. Payment request creation from invoice
def test_payment_request_creation_from_invoice(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = res.json()["document_id"]
    create_res = client.post(f"/invoices/{doc_id}/create-payment-request")
    assert create_res.status_code == 201
    payload = create_res.json()
    assert payload["document_id"] == doc_id
    assert payload["payment"]["amount"] == 45000.0
    assert payload["payment"]["vendor_id"] == "VEND-001"
    assert payload["payment"]["invoice_id"] == "INV-2026-8801"
    assert payload["payment"]["channel"] == "ocr_upload"


# 16. OCR → Three-way match integration
def test_ocr_to_three_way_match_integration(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = res.json()["document_id"]
    create_res = client.post(f"/invoices/{doc_id}/create-payment-request")
    req_id = create_res.json()["payment_request_id"]

    # Run scoring (which performs three-way matching)
    score_res = client.post(f"/payments/{req_id}/score")
    assert score_res.status_code == 200
    b_checks = score_res.json()["business_checks"]
    assert b_checks["po_exists"] == 1
    assert b_checks["po_approved"] == 1
    assert b_checks["grn_exists"] == 1
    assert b_checks["vendor_approved"] == 1
    assert b_checks["amount_match"] is True


# 17. OCR → Scoring & policy routing integration
def test_ocr_to_scoring_and_policy_integration(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = res.json()["document_id"]
    create_res = client.post(
        f"/invoices/{doc_id}/create-payment-request",
        json={
            "invoice_id": "INV-2026-8801",
            "amount": 45000.0,
            "currency": "INR",
            "vendor_id": "VEND-001",
            "bank_account": "ACME-BANK-001",
            "po_id": "PO-2026-001",
            "channel": "portal",
        },
    )
    req_id = create_res.json()["payment_request_id"]

    score_res = client.post(f"/payments/{req_id}/score")
    assert score_res.status_code == 200
    score_data = score_res.json()
    assert score_data["status"] == "AUTHORIZED"
    assert score_data["routing_tier"] == "AUTO_APPROVE"
    assert score_data["required_signatures"] == 0
    assert "features_used" in score_data
    assert score_data["features_used"]["document_quality_score"] > 0


# 18. Audit event creation and cryptographic chain integrity
def test_ocr_audit_events_and_hash_chain(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    res = client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = res.json()["document_id"]
    client.post(f"/invoices/{doc_id}/create-payment-request")

    # Verify audit verification endpoint
    audit_res = client.get("/audit-log/verify")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["valid"] is True
    assert audit_data["records_checked"] >= 3


# 19. Malicious filename / path traversal protection
def test_malicious_filename_sanitized(client):
    pdf_bytes = create_sample_pdf(SAMPLE_INVOICE_TEXT)
    res = client.post(
        "/invoices/upload",
        files={"file": ("../../../../etc/passwd.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    data = res.json()
    # Stored original filename should have stripped directory traversal components
    assert "/" not in data["original_filename"]
    assert "\\" not in data["original_filename"]
    assert data["original_filename"] == "passwd.pdf"
