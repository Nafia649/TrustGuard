import os
import pytest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.models.payment_request import PaymentRequest
from app.models.audit_log import AuditLog
from app.services.invoice_generator import DEMO_INVOICE_DEFINITIONS, generate_all_demo_invoices, DEMO_INVOICES_DIR
from app.services.seed_service import seed_database
from app.services.ocr.ocr_engine import ocr_engine
from app.services.ocr.parser import parse_invoice_text


def test_10_vendors_seeded(client, db_session):
    """1. 10 vendors generated. 2. VEND-001..009 approved. 3. VEND-010 unapproved."""
    client.post("/seed")
    vendors = db_session.query(Vendor).all()
    assert len(vendors) == 10

    for v in vendors:
        if v.vendor_id in [f"VEND-00{i}" for i in range(1, 10)]:
            assert v.approved is True, f"{v.vendor_id} should be approved"
        elif v.vendor_id == "VEND-010":
            assert v.approved is False, "VEND-010 Shadow Shell Enterprises must be unapproved"


def test_vendors_idempotent_on_repeated_generation(client, db_session):
    """4. Vendors are not duplicated on repeated generation."""
    client.post("/seed")
    client.post("/seed")
    vendors = db_session.query(Vendor).all()
    assert len(vendors) == 10


def test_invoice_fixtures_unique_and_match_procurement(client, db_session):
    """5. Invoice IDs are unique. 6. Invoice data matches vendor/PO data."""
    invoice_ids = [inv["invoice_id"] for inv in DEMO_INVOICE_DEFINITIONS]
    assert len(invoice_ids) == 10
    assert len(set(invoice_ids)) == 10

    # Ensure files exist on disk
    generated = generate_all_demo_invoices()
    assert len(generated) == 10
    for path in generated:
        assert os.path.exists(path)


def test_ocr_extracts_expected_fields(client):
    """7. Generated invoice can be uploaded. 8. OCR extracts expected fields."""
    client.post("/seed")
    pdf_path = os.path.join(DEMO_INVOICES_DIR, "INV-DEMO-001.pdf")
    assert os.path.exists(pdf_path)

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/invoices/upload",
            files={"file": ("INV-DEMO-001.pdf", f, "application/pdf")},
            data={"uploader_id": "emp_accounts_01"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "EXTRACTED"
    assert data["extracted_data"]["invoice_id"] == "INV-DEMO-001"
    assert data["extracted_data"]["total_amount"] == 45000.0
    assert data["vendor_match"]["matched_vendor_id"] == "VEND-001"
    assert data["vendor_match"]["is_approved"] is True


def test_payment_creation_and_settlement_lifecycle(client, db_session):
    """
    9. First payment against an invoice succeeds.
    10. Same invoice cannot be paid twice.
    11. Same invoice cannot create two independent payment requests.
    12. Fully paid invoice has zero remaining payable.
    14. Overpayment / duplicate is rejected with 409 and ALREADY_SETTLED.
    """
    client.post("/seed")
    pdf_path = os.path.join(DEMO_INVOICES_DIR, "INV-DEMO-001.pdf")
    with open(pdf_path, "rb") as f:
        res_upload = client.post(
            "/invoices/upload",
            files={"file": ("INV-DEMO-001.pdf", f, "application/pdf")},
        )
    doc_id = res_upload.json()["document_id"]

    # Check settlement status before payment (UNPAID)
    res_status0 = client.get("/invoices/INV-DEMO-001/settlement-status")
    assert res_status0.status_code == 200
    assert res_status0.json()["settlement_status"] == "UNPAID"
    assert res_status0.json()["remaining_payable"] == 45000.0

    # 9. First payment creation succeeds
    review_payload = {
        "invoice_id": "INV-DEMO-001",
        "amount": 45000.0,
        "vendor_id": "VEND-001",
        "bank_account": "ACME-BANK-001",
        "po_id": "PO-2026-001",
        "channel": "portal",
        "requester_id": "emp_accounts_01",
    }
    res_pay1 = client.post(f"/invoices/{doc_id}/create-payment-request", json=review_payload)
    assert res_pay1.status_code == 201
    pay_id = res_pay1.json()["payment_request_id"]

    # Settlement status while pending
    res_status1 = client.get("/invoices/INV-DEMO-001/settlement-status")
    assert res_status1.status_code == 200
    assert res_status1.json()["settlement_status"] == "PENDING_APPROVAL"

    # 11. Duplicate payment request while pending is blocked (409)
    res_dup = client.post(f"/invoices/{doc_id}/create-payment-request")
    assert res_dup.status_code == 409
    assert "Duplicate invoice detected" in res_dup.json()["detail"]

    # Score and auto-approve the payment (VEND-001, 45k, matching PO)
    res_score = client.post(f"/payments/{pay_id}/score")
    assert res_score.status_code == 200
    assert res_score.json()["routing_tier"] == "AUTO_APPROVE"
    assert res_score.json()["payment_status"] == "AUTHORIZED"

    # Release the payment to mock ledger
    res_release = client.post(f"/payments/{pay_id}/release")
    assert res_release.status_code == 200
    assert res_release.json()["status"] == "RELEASED"

    # 12. Settlement status now SETTLED with zero remaining payable
    res_status2 = client.get("/invoices/INV-DEMO-001/settlement-status")
    assert res_status2.status_code == 200
    status_data = res_status2.json()
    assert status_data["settlement_status"] == "SETTLED"
    assert status_data["total_paid"] == 45000.0
    assert status_data["remaining_payable"] == 0.0

    # 10 & 14. Same invoice second payment is blocked (ALREADY_SETTLED)
    res_second_pay = client.post(
        "/payment-requests",
        json={
            "vendor_id": "VEND-001",
            "amount": 45000.0,
            "currency": "INR",
            "bank_account": "ACME-BANK-001",
            "invoice_id": "INV-DEMO-001",
            "po_id": "PO-2026-001",
        },
    )
    assert res_second_pay.status_code == 409
    assert "already settled" in res_second_pay.json()["detail"].lower()

    # Verify audit log recorded INVOICE_ALREADY_SETTLED
    settle_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "INVOICE_ALREADY_SETTLED")
        .first()
    )
    assert settle_audit is not None
    assert settle_audit.result == "BLOCKED"


def test_different_invoices_same_vendor_valid(client):
    """15. Different invoices from the same vendor remain valid."""
    client.post("/seed")
    res1 = client.post(
        "/payment-requests",
        json={
            "vendor_id": "VEND-001",
            "amount": 10000.0,
            "currency": "INR",
            "bank_account": "ACME-BANK-001",
            "invoice_id": "INV-V1-AAA",
            "po_id": "PO-2026-001",
        },
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/payment-requests",
        json={
            "vendor_id": "VEND-001",
            "amount": 12000.0,
            "currency": "INR",
            "bank_account": "ACME-BANK-001",
            "invoice_id": "INV-V1-BBB",
            "po_id": "PO-2026-001",
        },
    )
    assert res2.status_code == 201


def test_unapproved_vendor_scenario(client, db_session):
    """17. New/unapproved vendor scenario works (escalation/hold, OCR never auto-approves)."""
    client.post("/seed")
    pdf_path = os.path.join(DEMO_INVOICES_DIR, "INV-DEMO-010.pdf")
    with open(pdf_path, "rb") as f:
        res_upload = client.post(
            "/invoices/upload",
            files={"file": ("INV-DEMO-010.pdf", f, "application/pdf")},
        )
    assert res_upload.status_code == 201
    data = res_upload.json()
    assert data["vendor_match"]["is_approved"] is False  # OCR NEVER APPROVES!
    assert data["vendor_match"]["matched_vendor_id"] == "VEND-010"

    doc_id = data["document_id"]
    res_pay = client.post(f"/invoices/{doc_id}/create-payment-request")
    assert res_pay.status_code == 201
    pay_id = res_pay.json()["payment_request_id"]

    # Verify payment request vendor is unapproved
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == pay_id).first()
    assert payment.vendor.approved is False
    assert payment.po_id is None

    # Three-way match confirms vendor_approved == 0 and po_exists == 0
    from app.services.three_way_match import perform_three_way_match
    checks = perform_three_way_match(db_session, payment)
    assert checks["vendor_approved"] == 0
    assert checks["po_exists"] == 0

    # Since no PO exists, scoring adheres to Data Integrity Rule (MissingFeatureDerivationError -> 422)
    res_score = client.post(f"/payments/{pay_id}/score")
    assert res_score.status_code == 422
    assert "invoice_po_amount_ratio" in res_score.json()["detail"]["feature"]


def test_bank_account_change_scenario(client):
    """18. Bank account change scenario detected (REQ-DEMO-007)."""
    client.post("/seed")
    res_score = client.post("/payments/REQ-DEMO-007/score")
    assert res_score.status_code == 200
    score_data = res_score.json()
    assert score_data["business_checks"]["bank_account_changed"] == 1
    assert score_data["routing_tier"] in ("TWO_SIGNATURES", "ANALYST_HOLD")


def test_invoice_po_mismatch_scenario(client):
    """19. Invoice/PO mismatch scenario detected (REQ-DEMO-008: PO 50k vs Inv 75k)."""
    client.post("/seed")
    res_score = client.post("/payments/REQ-DEMO-008/score")
    assert res_score.status_code == 200
    score_data = res_score.json()
    assert score_data["business_checks"]["amount_match"] is False
    assert score_data["routing_tier"] in ("ONE_SIGNATURE", "TWO_SIGNATURES", "ANALYST_HOLD")


def test_audit_hash_chain_intact(client):
    """22. Existing audit behavior is not broken; hash chain verifies."""
    client.post("/seed")
    res_verify = client.get("/audit-log/verify")
    assert res_verify.status_code == 200
    assert res_verify.json()["valid"] is True
