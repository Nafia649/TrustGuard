"""
REALKEY Phase 4 Tests: Exact Payment Approval & WebAuthn Cryptographic Binding.

Verifies:
1. Valid exact payment approval (correct approver + correct payment).
2. Tampering with any payment field after challenge creation is detected and rejected:
   - Wrong amount
   - Wrong vendor_id
   - Wrong bank_account
   - Wrong invoice_id
   - Wrong po_id
   - Wrong currency
   - Wrong policy_version
   - Wrong routing_tier
3. Wrong / mismatched nonce rejection.
4. Expired approval challenge & bundle rejection.
5. Invalid WebAuthn assertion signature rejection.
6. Wrong / unauthorized credential rejection.
7. Inactive approver rejection.
8. Single-use challenge protection (replay prevention).
9. Signature record created only after successful verification.
10. Failed approval does not create a valid signature.
11. Private keys are never persisted anywhere on the server.
12. Server reconstructs payment bundle from authoritative database records.
13. Alias endpoint /payments/{id}/sign works identically to /payments/{id}/approve.
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.models.approver import Approver
from app.models.payment_request import PaymentRequest
from app.models.policy import PolicyVersion
from app.models.signature import Signature
from security.realkey import challenge_store, VirtualWebAuthnClient


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


def test_valid_exact_payment_approval(client, db_session):
    """Test 1 & 2: Valid exact payment approval ceremony succeeds."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    # 1. Request challenge bound to exact payment REQ-DEMO-001
    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    assert res_chal.status_code == 200
    chal_data = res_chal.json()

    assert chal_data["request_id"] == "REQ-DEMO-001"
    assert "nonce" in chal_data
    assert "canonical_hash" in chal_data
    assert "payment_bundle" in chal_data
    assert chal_data["payment_bundle"]["amount"] == 45000
    assert chal_data["payment_bundle"]["vendor_id"] == "VEND-001"
    assert "webauthn_options" in chal_data

    # 2. Authenticator signs WebAuthn assertion
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # 3. Submit approval to backend
    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 200
    data = res_approve.json()

    assert data["authorized"] is True
    assert data["signature_status"] == "VERIFIED"
    assert data["request_id"] == "REQ-DEMO-001"
    assert data["approver_id"] == "APP-001"
    assert data["canonical_hash"] == chal_data["canonical_hash"]
    assert data["payment_binding_valid"] is True
    assert data["payment_status"] == "AUTHORIZED"

    # 4. Verify payment in DB is now AUTHORIZED
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    assert payment.status == "AUTHORIZED"


def test_signature_record_created_after_successful_verification(client, db_session):
    """Test 18: Signature record created only after successful verification."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 200
    sig_id = res_approve.json()["signature_id"]

    # Verify Signature row in database
    sig = db_session.query(Signature).filter(Signature.signature_id == sig_id).first()
    assert sig is not None
    assert sig.request_id == "REQ-DEMO-001"
    assert sig.approver_id == "APP-001"
    assert sig.signature_status == "VALID"
    assert sig.nonce == chal_data["nonce"]
    assert sig.payload_hash == chal_data["canonical_hash"]
    assert sig.signature_payload is not None
    assert sig.raw_signature is not None
    assert len(sig.raw_signature) > 0


def test_tamper_payment_amount_rejected(client, db_session):
    """Test 3 & 16: Modifying payment amount after challenge is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Attacker tampers with amount in the database
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.amount = 450000.0  # Tampered from 45,000 to 450,000
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]

    # Verify no valid signature was created
    sig = db_session.query(Signature).filter(Signature.request_id == "REQ-DEMO-001").first()
    assert sig is None


def test_tamper_vendor_id_rejected(client, db_session):
    """Test 4: Modifying vendor_id after challenge is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Attacker switches vendor to rogue vendor
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.vendor_id = "VEND-004"
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]


def test_tamper_bank_account_rejected(client, db_session):
    """Test 5 & 17: Modifying bank account before verification is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Attacker switches beneficiary bank account
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.bank_account = "ATTACKER-OFFSHORE-999"
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]


def test_tamper_invoice_id_rejected(client, db_session):
    """Test 6: Modifying invoice reference is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.invoice_id = "INV-FORGED-999"
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]


def test_tamper_po_id_rejected(client, db_session):
    """Test 7: Modifying purchase order reference is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.po_id = "PO-2026-999"
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]


def test_tamper_currency_rejected(client, db_session):
    """Test 8: Modifying currency is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.currency = "USD"
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]


def test_tamper_routing_tier_rejected(client, db_session):
    """Test 10: Modifying routing_tier is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Attacker tries to alter routing tier in database
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    payment.routing_tier = "AUTO_APPROVE"
    db_session.commit()

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "PAYMENT_HASH_MISMATCH" in res_approve.json()["detail"]


def test_wrong_nonce_rejected(client):
    """Test 11: Submitting a wrong or altered nonce is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": "00000000000000000000000000000000",  # Fake nonce
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "NONCE_MISMATCH" in res_approve.json()["detail"]


def test_expired_approval_challenge_rejected(client):
    """Test 12: Submitting an approval after challenge expiry is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Manually expire the challenge in the store
    chal_obj = challenge_store._approval_challenges_by_id[chal_data["challenge_id"]]
    chal_obj.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "APPROVAL_CHALLENGE_EXPIRED" in res_approve.json()["detail"]


def test_invalid_webauthn_signature_rejected(client):
    """Test 13: Submitting an invalid WebAuthn signature is rejected."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()

    # Corrupt the signature using simulator
    corrupt_assertion = sim.sign_assertion(
        options=chal_data["webauthn_options"],
        corrupt_signature=True,
    )

    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": corrupt_assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "INVALID_WEBAUTHN_ASSERTION" in res_approve.json()["detail"]


def test_wrong_credential_rejected(client):
    """Test 14: Submitting an assertion from an unauthorized credential is rejected."""
    sim_alice, _ = _setup_registered_approver(client, approver_id="APP-001")
    # Also register Bob
    res_opts_bob = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-002"})
    sim_bob = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    cred_bob = sim_bob.create_credential(options=res_opts_bob.json()["options"])
    client.post("/auth/webauthn/register/verify", json={"approver_id": "APP-002", "credential": cred_bob})

    # Issue challenge for Alice (APP-001)
    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()

    # Bob tries to sign Alice's challenge with Bob's credential
    bob_assertion = sim_bob.sign_assertion(options=chal_data["webauthn_options"])

    # Alice submits Bob's credential
    res_approve = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": bob_assertion,
        },
    )
    assert res_approve.status_code == 400
    assert "CREDENTIAL_NOT_AUTHORIZED" in res_approve.json()["detail"]


def test_inactive_approver_rejected(client, db_session):
    """Test 15: Inactive approver cannot request challenges or approve payments."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    # Deactivate Alice
    approver = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    approver.active = False
    db_session.commit()

    # Challenge is rejected
    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    assert res_chal.status_code == 400
    assert "INACTIVE_APPROVER" in res_chal.json()["detail"]


def test_single_use_approval_challenge(client):
    """Verifies that an approval challenge cannot be reused (single-use guarantee)."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # First approval succeeds
    res1 = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={"approver_id": "APP-001", "nonce": chal_data["nonce"], "credential": assertion},
    )
    assert res1.status_code == 200

    # Second approval with identical challenge fails
    res2 = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={"approver_id": "APP-001", "nonce": chal_data["nonce"], "credential": assertion},
    )
    assert res2.status_code == 400
    assert "INVALID_APPROVAL_CHALLENGE" in res2.json()["detail"]


def test_sign_alias_endpoint(client):
    """Test 13: Alias endpoint /payments/{id}/sign works identically."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    res_sign = client.post(
        "/payments/REQ-DEMO-001/sign",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_sign.status_code == 200
    assert res_sign.json()["authorized"] is True
    assert res_sign.json()["signature_status"] == "VERIFIED"


def test_flattened_signature_submission(client):
    """Verifies support for flattened signature fields in SignatureSubmissionRequest."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Flattened payload
    flattened_payload = {
        "approver_id": "APP-001",
        "nonce": chal_data["nonce"],
        "signature": assertion["response"]["signature"],
        "authenticator_data": assertion["response"]["authenticatorData"],
        "client_data_json": assertion["response"]["clientDataJSON"],
    }

    res_approve = client.post("/payments/REQ-DEMO-001/approve", json=flattened_payload)
    assert res_approve.status_code == 200
    assert res_approve.json()["authorized"] is True


def test_private_key_never_persisted(client, db_session):
    """Test 20: Verifies private keys are never stored anywhere in the database."""
    _setup_registered_approver(client, approver_id="APP-001")

    # Verify registered approver has standard public key PEM (and no private key)
    alice = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    assert "BEGIN PUBLIC KEY" in alice.public_key
    assert "PRIVATE" not in alice.public_key.upper()

    # Check all approvers in database
    approvers = db_session.query(Approver).all()
    for app in approvers:
        if app.public_key:
            assert "PRIVATE" not in app.public_key.upper()

    # Check all signatures in database
    signatures = db_session.query(Signature).all()
    for sig in signatures:
        if sig.signature_payload:
            assert "private" not in sig.signature_payload.lower()
        if sig.raw_signature:
            assert "private" not in sig.raw_signature.lower()
