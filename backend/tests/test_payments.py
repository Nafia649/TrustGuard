import pytest


def test_seed_endpoint(client):
    """Verify that POST /seed creates Acme Ltd demo dataset."""
    response = client.post("/seed")
    assert response.status_code == 200
    data = response.json()
    assert data["company"] == "Acme Ltd"
    assert data["vendors_count"] >= 4
    assert data["purchase_orders_count"] >= 3
    assert data["goods_receipts_count"] >= 3
    assert data["payment_requests_count"] >= 4
    assert len(data["scenarios"]) == 4


def test_list_vendors(client):
    """Verify that seeded vendors can be listed and retrieved."""
    client.post("/seed")
    response = client.get("/vendors")
    assert response.status_code == 200
    vendors = response.json()
    assert len(vendors) >= 4
    vendor_ids = [v["vendor_id"] for v in vendors]
    assert "VEND-001" in vendor_ids

    # Test single vendor fetch
    single_res = client.get("/vendors/VEND-001")
    assert single_res.status_code == 200
    assert single_res.json()["vendor_name"] == "Acme Industrial Supplies"


def test_get_nonexistent_vendor(client):
    """Verify fetching non-existent vendor returns 404."""
    response = client.get("/vendors/NONEXISTENT_VEND")
    assert response.status_code == 404


def test_create_payment_request_success(client):
    """Verify successful creation of a payment request."""
    client.post("/seed")

    payload = {
        "vendor_id": "VEND-001",
        "amount": 25000.0,
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "invoice_id": "INV-NEW-9001",
        "po_id": "PO-2026-001",
        "channel": "portal",
        "document_quality_score": 0.96,
        "requester_id": "emp_sarah_01",
    }
    response = client.post("/payment-requests", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["request_id"].startswith("REQ-")
    assert data["status"] == "PENDING"
    assert data["vendor_id"] == "VEND-001"
    assert data["amount"] == 25000.0
    assert data["bank_account"] == "ACME-BANK-001"
    assert data["invoice_id"] == "INV-NEW-9001"
    assert data["requester_id"] == "emp_sarah_01"


def test_create_payment_request_missing_vendor(client):
    """Verify creating payment for non-existent vendor fails with 404."""
    client.post("/seed")

    payload = {
        "vendor_id": "VEND-DOES-NOT-EXIST",
        "amount": 10000.0,
        "currency": "INR",
        "bank_account": "BANK-000",
        "invoice_id": "INV-FAIL-01",
    }
    response = client.post("/payment-requests", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_payment_request_invalid_po(client):
    """Verify creating payment with invalid PO reference fails with 404."""
    client.post("/seed")

    payload = {
        "vendor_id": "VEND-001",
        "amount": 10000.0,
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "invoice_id": "INV-FAIL-02",
        "po_id": "PO-NONEXISTENT",
    }
    response = client.post("/payment-requests", json=payload)
    assert response.status_code == 404
    assert "purchase order" in response.json()["detail"].lower()


def test_create_payment_request_po_vendor_mismatch(client):
    """Verify creating payment where PO belongs to a different vendor fails with 400."""
    client.post("/seed")

    # PO-2026-001 belongs to VEND-001, not VEND-002
    payload = {
        "vendor_id": "VEND-002",
        "amount": 10000.0,
        "currency": "INR",
        "bank_account": "GLOB-BANK-002",
        "invoice_id": "INV-FAIL-03",
        "po_id": "PO-2026-001",
    }
    response = client.post("/payment-requests", json=payload)
    assert response.status_code == 400
    assert "does not belong to vendor" in response.json()["detail"]


def test_create_payment_request_duplicate_invoice(client):
    """Verify submitting duplicate invoice for same vendor returns 409 Conflict."""
    client.post("/seed")

    # INV-2026-001 is already seeded for VEND-001
    payload = {
        "vendor_id": "VEND-001",
        "amount": 45000.0,
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "invoice_id": "INV-2026-001",
        "po_id": "PO-2026-001",
    }
    response = client.post("/payment-requests", json=payload)
    assert response.status_code == 409
    assert "duplicate invoice" in response.json()["detail"].lower()


def test_list_payments_and_filters(client):
    """Verify listing payments and filtering by status and vendor."""
    client.post("/seed")

    # List all payments
    response = client.get("/payments")
    assert response.status_code == 200
    payments = response.json()
    assert len(payments) >= 4

    # Filter by vendor
    res_vend = client.get("/payments?vendor_id=VEND-001")
    assert res_vend.status_code == 200
    for p in res_vend.json():
        assert p["vendor_id"] == "VEND-001"

    # Filter by status
    res_status = client.get("/payments?status=PENDING")
    assert res_status.status_code == 200
    for p in res_status.json():
        assert p["status"] == "PENDING"


def test_get_payment_by_id(client):
    """Verify fetching single payment by request ID."""
    client.post("/seed")

    response = client.get("/payments/REQ-DEMO-001")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "REQ-DEMO-001"
    assert data["amount"] == 45000.0
    assert data["invoice_id"] == "INV-2026-001"


def test_get_payment_nonexistent(client):
    """Verify 404 for non-existent payment ID."""
    response = client.get("/payments/REQ-UNKNOWN-999")
    assert response.status_code == 404
