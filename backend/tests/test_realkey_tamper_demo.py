"""
REALKEY Phase 5 Tests: Tamper Detection Demonstration.

Verifies:
1. Tampering with any of the 11 security-critical fields breaks the SHA-256 canonical hash:
   - amount
   - vendor_id
   - bank_account
   - invoice_id
   - po_id
   - currency
   - routing_tier
   - policy_version
   - nonce
   - expiry
   - timestamp
2. In-memory simulation preserves bundle immutability (zero side-effects on original).
3. Structurally invalid tampered values trigger bundle validation rejection.
4. Tamper demo API endpoint POST /payments/{id}/tamper-demo functions correctly.
5. Critical Security Invariant: The original payment and signature records in the database
   remain completely unchanged after running the tamper demo.
6. Audit logging: TAMPER_DETECTED event with result SECURITY_ALERT is recorded in the
   hash-chained audit log, and chain integrity remains unbroken.
7. Identical value submission detects no tampering and does not raise an alert.
8. Invalid field names return HTTP 400.
9. Unsigned payments return HTTP 400.
10. Non-existent payments return HTTP 404.
11. Real WebAuthn assertion verification rejects the tampered payment hash with
    PaymentHashMismatchError.
"""

from datetime import datetime, timezone
import pytest

from app.models.payment_request import PaymentRequest
from app.models.signature import Signature
from app.models.audit_log import AuditLog
from app.services.audit_service import verify_chain
from security.realkey import (
    REQUIRED_PAYMENT_BUNDLE_FIELDS,
    VirtualWebAuthnClient,
    challenge_store,
    create_payment_bundle,
    demonstrate_tamper_detection,
    hash_payment_bundle,
    simulate_payment_tampering,
    verify_payment_approval,
    PaymentHashMismatchError,
)


@pytest.fixture(autouse=True)
def clean_challenge_store():
    """Ensure challenge store is clean before and after each test."""
    challenge_store.clear()
    yield
    challenge_store.clear()


def _setup_registered_approver(client, approver_id="APP-001"):
    """Seeds the DB and registers a real WebAuthn passkey for the approver."""
    client.post("/seed")
    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": approver_id})
    assert res_opts.status_code == 200
    options = res_opts.json()["options"]

    sim = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    cred = sim.create_credential(options=options)

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": approver_id, "credential": cred},
    )
    assert res_verify.status_code == 200
    return sim, cred


def _setup_approved_payment(client, request_id="REQ-DEMO-001", approver_id="APP-001"):
    """Seeds DB, registers passkey, and executes valid payment approval."""
    sim, _ = _setup_registered_approver(client, approver_id=approver_id)

    res_chal = client.post(f"/payments/{request_id}/challenge", json={"approver_id": approver_id})
    assert res_chal.status_code == 200
    chal_data = res_chal.json()

    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    res_approve = client.post(
        f"/payments/{request_id}/approve",
        json={
            "approver_id": approver_id,
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 200
    return sim, chal_data, res_approve.json()


# ==============================================================================
# 1. STANDALONE CRYPTOGRAPHIC TAMPER DETECTION TESTS
# ==============================================================================

def test_tamper_detection_standalone_amount():
    """Modifying amount from 50000 to 500000 changes hash and invalidates approval."""
    original_bundle = create_payment_bundle(
        vendor_id="VEND-001",
        amount=50000,
        currency="INR",
        bank_account="ACCT-1234",
        invoice_id="INV-001",
        po_id="PO-001",
        timestamp="2026-03-31T10:00:00Z",
        nonce="test_nonce_12345678",
        expiry="2026-03-31T10:05:00Z",
        policy_version=1,
        routing_tier="TIER_1",
    )

    result = demonstrate_tamper_detection(
        original_bundle=original_bundle,
        field="amount",
        tampered_value=500000,
    )

    assert result.tamper_detected is True
    assert result.hash_match is False
    assert result.approval_valid is False
    assert result.field_modified == "amount"
    assert result.original_value == 50000
    assert result.tampered_value == 500000
    assert result.original_hash != result.tampered_hash
    assert result.reason == "PAYMENT_HASH_MISMATCH"
    assert "Payment hash mismatch detected" in result.message


def test_tamper_detection_all_11_fields_individually():
    """Modifying any single one of the 11 security-critical fields breaks the SHA-256 hash."""
    base_bundle = create_payment_bundle(
        vendor_id="VEND-001",
        amount=50000,
        currency="INR",
        bank_account="ACCT-1234",
        invoice_id="INV-001",
        po_id="PO-001",
        timestamp="2026-03-31T10:00:00Z",
        nonce="test_nonce_12345678",
        expiry="2026-03-31T10:05:00Z",
        policy_version=1,
        routing_tier="TIER_1",
    )

    tampered_values = {
        "amount": 99999,
        "vendor_id": "VEND-ATTACKER",
        "bank_account": "ACCT-EVIL-9999",
        "invoice_id": "INV-EVIL-002",
        "po_id": "PO-EVIL-999",
        "currency": "USD",
        "routing_tier": "TIER_3",
        "policy_version": 2,
        "nonce": "tampered_nonce_8888",
        "expiry": "2026-04-01T12:00:00Z",
        "timestamp": "2026-03-31T11:00:00Z",
    }

    assert set(tampered_values.keys()) == REQUIRED_PAYMENT_BUNDLE_FIELDS

    for field, new_val in tampered_values.items():
        res = demonstrate_tamper_detection(base_bundle, field, new_val)
        assert res.tamper_detected is True, f"Field '{field}' failed to trigger tamper detection!"
        assert res.hash_match is False
        assert res.approval_valid is False
        assert res.original_hash != res.tampered_hash
        assert res.field_modified == field


def test_simulate_payment_tampering_immutability():
    """simulate_payment_tampering must not alter the original bundle dictionary."""
    orig = {
        "amount": 50000,
        "vendor_id": "VEND-001",
        "currency": "INR",
        "bank_account": "ACCT-1234",
        "invoice_id": "INV-001",
        "po_id": "PO-001",
        "timestamp": "2026-03-31T10:00:00Z",
        "nonce": "test_nonce_12345678",
        "expiry": "2026-03-31T10:05:00Z",
        "policy_version": 1,
        "routing_tier": "TIER_1",
    }
    copy_orig = dict(orig)

    mutated = simulate_payment_tampering(orig, "amount", 100000)
    assert mutated["amount"] == 100000
    assert orig["amount"] == 50000
    assert orig == copy_orig


def test_simulate_payment_tampering_invalid_field():
    """Attempting to tamper with an invalid field name raises ValueError."""
    orig = {"vendor_id": "VEND-001"}
    with pytest.raises(ValueError, match="Invalid field"):
        simulate_payment_tampering(orig, "non_existent_field", "value")


def test_tamper_detection_identical_value():
    """Submitting the exact same value reports no tampering."""
    bundle = create_payment_bundle(
        vendor_id="VEND-001",
        amount=50000,
        currency="INR",
        bank_account="ACCT-1234",
        invoice_id="INV-001",
        po_id="PO-001",
        timestamp="2026-03-31T10:00:00Z",
        nonce="test_nonce_12345678",
        expiry="2026-03-31T10:05:00Z",
        policy_version=1,
        routing_tier="TIER_1",
    )
    res = demonstrate_tamper_detection(bundle, "amount", 50000)
    assert res.tamper_detected is False
    assert res.hash_match is True
    assert res.approval_valid is True
    assert res.reason == "IDENTICAL_PAYMENT"


def test_tamper_detection_invalid_datatype():
    """Attacker submitting an invalid type (e.g. non-numeric amount) fails bundle validation."""
    bundle = create_payment_bundle(
        vendor_id="VEND-001",
        amount=50000,
        currency="INR",
        bank_account="ACCT-1234",
        invoice_id="INV-001",
        po_id="PO-001",
        timestamp="2026-03-31T10:00:00Z",
        nonce="test_nonce_12345678",
        expiry="2026-03-31T10:05:00Z",
        policy_version=1,
        routing_tier="TIER_1",
    )
    res = demonstrate_tamper_detection(bundle, "amount", "NOT_A_NUMBER")
    assert res.tamper_detected is True
    assert res.approval_valid is False
    assert res.reason == "PAYMENT_BUNDLE_VALIDATION_FAILED"


# ==============================================================================
# 2. END-TO-END TAMPER DEMO API INTEGRATION TESTS
# ==============================================================================

def test_tamper_demo_api_amount_modification(client, db_session):
    """POST /payments/{id}/tamper-demo successfully demonstrates tamper detection on amount."""
    sim, chal_data, approve_data = _setup_approved_payment(client, request_id="REQ-DEMO-001")

    res = client.post(
        "/payments/REQ-DEMO-001/tamper-demo",
        json={"field": "amount", "tampered_value": 450000},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["tamper_detected"] is True
    assert data["field_modified"] == "amount"
    assert data["original_value"] == 45000
    assert data["tampered_value"] == 450000
    assert data["hash_match"] is False
    assert data["approval_valid"] is False
    assert data["original_hash"] == chal_data["canonical_hash"]
    assert data["original_hash"] != data["tampered_hash"]
    assert data["reason"] == "PAYMENT_HASH_MISMATCH"
    assert data["audit_logged"] is True


def test_tamper_demo_preserves_database_records(client, db_session):
    """CRITICAL SECURITY INVARIANT: Tamper demo must NEVER modify database payment or signature records."""
    _setup_approved_payment(client, request_id="REQ-DEMO-001")

    # Capture original database state
    orig_payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    orig_amount = orig_payment.amount
    orig_status = orig_payment.status
    orig_vendor = orig_payment.vendor_id

    orig_sig = db_session.query(Signature).filter(Signature.request_id == "REQ-DEMO-001").first()
    orig_sig_hash = orig_sig.payload_hash
    orig_sig_status = orig_sig.signature_status

    # Run tamper demo
    res = client.post(
        "/payments/REQ-DEMO-001/tamper-demo",
        json={"field": "amount", "tampered_value": 999999},
    )
    assert res.status_code == 200

    # Refresh and verify DB records remain unchanged
    db_session.refresh(orig_payment)
    db_session.refresh(orig_sig)

    assert orig_payment.amount == orig_amount == 45000
    assert orig_payment.status == orig_status == "AUTHORIZED"
    assert orig_payment.vendor_id == orig_vendor == "VEND-001"
    assert orig_sig.payload_hash == orig_sig_hash
    assert orig_sig.signature_status == orig_sig_status == "VALID"


def test_tamper_demo_creates_hash_chained_audit_log(client, db_session):
    """Tamper demo creates a TAMPER_DETECTED event in the hash-chained audit log with chain intact."""
    _setup_approved_payment(client, request_id="REQ-DEMO-001")

    res = client.post(
        "/payments/REQ-DEMO-001/tamper-demo",
        json={"field": "bank_account", "tampered_value": "ATTACKER-IBAN-666"},
    )
    assert res.status_code == 200

    # Query audit log
    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.request_id == "REQ-DEMO-001", AuditLog.action == "TAMPER_DETECTED")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.result == "SECURITY_ALERT"
    assert "ATTACKER-IBAN-666" in audit_entry.details
    assert "bank_account" in audit_entry.details
    assert audit_entry.current_hash is not None

    # Verify audit chain integrity across all records
    chain_status = verify_chain(db_session)
    assert chain_status["valid"] is True
    assert chain_status["corrupted_id"] is None


def test_tamper_demo_all_11_fields_via_api(client, db_session):
    """Every one of the 11 security-critical fields can be tested via the API endpoint."""
    _setup_approved_payment(client, request_id="REQ-DEMO-001")

    test_fields = [
        ("amount", 88000),
        ("vendor_id", "VEND-ATTACKER"),
        ("bank_account", "ACCT-HACKED-99"),
        ("invoice_id", "INV-MALICIOUS-01"),
        ("po_id", "PO-MALICIOUS-01"),
        ("currency", "EUR"),
        ("routing_tier", "TIER_3"),
        ("policy_version", 2),
        ("nonce", "evil_nonce_999999"),
        ("expiry", "2026-12-31T23:59:59Z"),
        ("timestamp", "2026-01-01T00:00:00Z"),
    ]

    for field, tampered_val in test_fields:
        res = client.post(
            "/payments/REQ-DEMO-001/tamper-demo",
            json={"field": field, "tampered_value": tampered_val},
        )
        assert res.status_code == 200, f"API failed for field {field}: {res.text}"
        data = res.json()
        assert data["tamper_detected"] is True, f"Field '{field}' was not detected as tampered!"
        assert data["hash_match"] is False
        assert data["approval_valid"] is False
        assert data["field_modified"] == field
        assert data["original_hash"] != data["tampered_hash"]


def test_tamper_demo_identical_value_via_api(client, db_session):
    """Submitting the identical value via API reports no tampering and does not log alert."""
    _setup_approved_payment(client, request_id="REQ-DEMO-001")

    initial_audit_count = db_session.query(AuditLog).filter(AuditLog.action == "TAMPER_DETECTED").count()

    res = client.post(
        "/payments/REQ-DEMO-001/tamper-demo",
        json={"field": "amount", "tampered_value": 45000},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["tamper_detected"] is False
    assert data["hash_match"] is True
    assert data["approval_valid"] is True
    assert data["audit_logged"] is False

    new_audit_count = db_session.query(AuditLog).filter(AuditLog.action == "TAMPER_DETECTED").count()
    assert new_audit_count == initial_audit_count


def test_tamper_demo_invalid_field_returns_400(client, db_session):
    """Attempting to tamper with an invalid field returns HTTP 400."""
    _setup_approved_payment(client, request_id="REQ-DEMO-001")

    res = client.post(
        "/payments/REQ-DEMO-001/tamper-demo",
        json={"field": "attacker_injected_field", "tampered_value": "payload"},
    )
    assert res.status_code == 400
    assert "INVALID_FIELD" in res.json()["detail"]


def test_tamper_demo_unsigned_payment_returns_400(client, db_session):
    """Calling tamper-demo on an unapproved payment returns HTTP 400."""
    client.post("/seed")

    # REQ-DEMO-002 has not been approved
    res = client.post(
        "/payments/REQ-DEMO-002/tamper-demo",
        json={"field": "amount", "tampered_value": 90000},
    )
    assert res.status_code == 400
    assert "PAYMENT_NOT_SIGNED" in res.json()["detail"]


def test_tamper_demo_nonexistent_payment_returns_404(client, db_session):
    """Calling tamper-demo on a non-existent payment returns HTTP 404."""
    client.post("/seed")

    res = client.post(
        "/payments/NON_EXISTENT_REQ/tamper-demo",
        json={"field": "amount", "tampered_value": 1000},
    )
    assert res.status_code == 404
    assert "PAYMENT_NOT_FOUND" in res.json()["detail"]


def test_tampered_bundle_fails_real_webauthn_verification():
    """Real WebAuthn assertion verification strictly fails with PaymentHashMismatchError when hash is tampered."""
    sim = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    reg_opts = {
        "challenge": "dGVzdF9jaGFsbGVuZ2VfcmVn",
        "rp": {"name": "TrustGuard", "id": "localhost"},
        "user": {"id": "VVNFUi0wMDE=", "name": "approver@trustguard.internal", "displayName": "Approver"},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
    }
    cred = sim.create_credential(options=reg_opts)

    # 1. Authoritative original bundle and hash
    original_bundle = create_payment_bundle(
        vendor_id="VEND-001",
        amount=50000,
        currency="INR",
        bank_account="ACCT-1234",
        invoice_id="INV-001",
        po_id="PO-001",
        timestamp="2026-03-31T10:00:00Z",
        nonce="test_nonce_12345678",
        expiry="2026-03-31T10:05:00Z",
        policy_version=1,
        routing_tier="TIER_1",
    )
    original_hash = hash_payment_bundle(original_bundle)

    # 2. Tampered bundle and hash
    tampered_bundle = simulate_payment_tampering(original_bundle, "amount", 500000)
    tampered_hash = hash_payment_bundle(tampered_bundle)
    assert original_hash != tampered_hash

    # 3. WebAuthn challenge issued with original hash
    import os
    challenge_bytes = os.urandom(32)
    import base64
    chal_b64 = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")

    assertion = sim.sign_assertion(options={
        "challenge": chal_b64,
        "rpId": "localhost",
        "allowCredentials": [{"type": "public-key", "id": cred["id"]}],
    })

    # 4. Verification with original hash succeeds
    res_valid = verify_payment_approval(
        credential_payload=assertion,
        expected_challenge=challenge_bytes,
        expected_rp_id="localhost",
        expected_origin="http://localhost:5173",
        public_key_pem=sim.public_key_pem,
        current_sign_count=0,
        authoritative_payment_hash=original_hash,
        challenge_payment_hash=original_hash,
        request_id="REQ-001",
        approver_id="APP-001",
    )
    assert res_valid.authorized is True
    assert res_valid.signature_status == "VERIFIED"

    # 5. Verification with tampered authoritative hash fails with PaymentHashMismatchError
    with pytest.raises(PaymentHashMismatchError, match="Payment hash mismatch"):
        verify_payment_approval(
            credential_payload=assertion,
            expected_challenge=challenge_bytes,
            expected_rp_id="localhost",
            expected_origin="http://localhost:5173",
            public_key_pem=sim.public_key_pem,
            current_sign_count=0,
            authoritative_payment_hash=tampered_hash,
            challenge_payment_hash=original_hash,
            request_id="REQ-001",
            approver_id="APP-001",
        )
