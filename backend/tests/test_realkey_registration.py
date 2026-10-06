"""
Tests for REALKEY Phase 1 — WebAuthn Foundation and Registration.

Verifies:
1. Valid WebAuthn registration
2. Invalid challenge
3. Expired challenge
4. Reused challenge (replay defense)
5. Invalid origin
6. Invalid RP ID
7. Invalid / malformed registration response
8. Duplicate credential registration across approvers
9. Absolute prevention of private key persistence server-side
10. Inactive approver rejection
11. Non-existent approver rejection
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.models.approver import Approver
from app.models.audit_log import AuditLog
from security.realkey import (
    challenge_store,
    VirtualWebAuthnClient,
)


@pytest.fixture(autouse=True)
def clean_challenge_store():
    """Ensure challenge store is clean before each test."""
    challenge_store.clear()
    yield
    challenge_store.clear()


def test_valid_webauthn_registration(client, db_session):
    """1. Test successful, cryptographically valid WebAuthn registration."""
    client.post("/seed")

    # Step 1: Request registration options
    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    assert res_opts.status_code == 200
    data_opts = res_opts.json()
    assert data_opts["approver_id"] == "APP-001"
    assert "challenge_id" in data_opts
    assert "options" in data_opts
    options = data_opts["options"]
    assert options["rp"]["id"] == "localhost"
    assert "challenge" in options

    # Step 2: Virtual WebAuthn client creates genuine WebAuthn credential
    sim_client = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    cred = sim_client.create_credential(options=options)

    # Step 3: Server verifies registration response
    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_verify.status_code == 200
    data_verify = res_verify.json()
    assert data_verify["status"] == "success"
    assert data_verify["approver_id"] == "APP-001"
    assert data_verify["role"] == "senior_administrator"

    # Step 4: Verify Approver state in database
    approver = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    assert approver.credential_id == cred["id"]
    assert "-----BEGIN PUBLIC KEY-----" in approver.public_key
    assert approver.sign_count == 0

    # Step 5: Check profile endpoint
    res_prof = client.get("/auth/webauthn/approvers/APP-001")
    assert res_prof.status_code == 200
    prof = res_prof.json()
    assert prof["credential_registered"] is True
    assert prof["credential_id"] == cred["id"]


def test_invalid_challenge_rejected(client):
    """2. Test registration fails when challenge does not match issued challenge."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Client signs a tampered/different challenge
    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(options=options, override_challenge_b64="TAMPERED_CHALLENGE_BYTES_BASE64")

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_verify.status_code == 400
    assert "verification" in res_verify.json()["detail"].lower()


def test_expired_challenge_rejected(client):
    """3. Test registration fails when challenge has expired."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Force challenge expiration in the challenge store
    chal = challenge_store.get_valid_registration_challenge(approver_id="APP-001")
    chal.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(options=options)

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_verify.status_code == 400
    assert "expired" in res_verify.json()["detail"].lower()


def test_reused_challenge_rejected(client):
    """4. Test that a challenge cannot be used more than once (single-use guarantee)."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(options=options)

    # First attempt succeeds
    res_first = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_first.status_code == 200

    # Replay attempt with same challenge must be rejected
    res_replay = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_replay.status_code == 400
    assert "already been used" in res_replay.json()["detail"].lower()


def test_invalid_origin_rejected(client):
    """5. Test registration fails when client origin does not match configured origin."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Attacker origin
    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(
        options=options,
        override_origin="https://malicious-phishing-site.example.com",
    )

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_verify.status_code == 400
    assert "origin" in res_verify.json()["detail"].lower()


def test_invalid_rp_id_rejected(client):
    """6. Test registration fails when RP ID does not match configured RP ID."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Mismatched RP ID
    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(
        options=options,
        override_rp_id="unauthorized-rpid.com",
    )

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": cred},
    )
    assert res_verify.status_code == 400
    assert "rp id" in res_verify.json()["detail"].lower()


def test_invalid_registration_response_rejected(client):
    """7. Test registration fails on corrupted attestation or malformed payload."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Corrupted CBOR attestation
    sim_client = VirtualWebAuthnClient()
    corrupt_cred = sim_client.create_credential(options=options, corrupt_attestation=True)

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": corrupt_cred},
    )
    assert res_verify.status_code == 400

    # Completely malformed structure
    res_bad = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": "APP-001", "credential": {"arbitrary": "garbage"}},
    )
    assert res_bad.status_code == 400


def test_duplicate_credential_registration_rejected(client):
    """8. Test that duplicate credential cannot be registered to a different approver."""
    client.post("/seed")

    # Step 1: Approver APP-001 registers credential
    res1 = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    opts1 = res1.json()["options"]
    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(options=opts1)
    res_v1 = client.post("/auth/webauthn/register/verify", json={"approver_id": "APP-001", "credential": cred})
    assert res_v1.status_code == 200

    # Step 2: Approver APP-002 attempts to register the EXACT SAME credential
    res2 = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-002"})
    opts2 = res2.json()["options"]
    # Re-use exact credential ID bytes in the attestationObject for APP-002
    from webauthn.helpers import base64url_to_bytes
    cred_duplicate = sim_client.create_credential(
        options=opts2,
        override_credential_id=base64url_to_bytes(cred["id"]),
    )

    res_v2 = client.post("/auth/webauthn/register/verify", json={"approver_id": "APP-002", "credential": cred_duplicate})
    assert res_v2.status_code == 409
    assert "already registered" in res_v2.json()["detail"].lower()


def test_private_key_never_persisted_server_side(client, db_session):
    """9. Test and verify that private key material is NEVER stored server-side."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]
    sim_client = VirtualWebAuthnClient()
    cred = sim_client.create_credential(options=options)

    res_verify = client.post("/auth/webauthn/register/verify", json={"approver_id": "APP-001", "credential": cred})
    assert res_verify.status_code == 200

    # 1. Verify Approver record in DB
    approver = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    pub_key = approver.public_key

    # Must contain standard public key header
    assert "-----BEGIN PUBLIC KEY-----" in pub_key
    assert "-----END PUBLIC KEY-----" in pub_key

    # Must NOT contain private key markers
    assert "PRIVATE KEY" not in pub_key
    assert "PRIVATE" not in pub_key
    assert "private" not in pub_key.lower()

    # 2. Verify all audit logs for this registration contain zero private key material
    logs = db_session.query(AuditLog).filter(AuditLog.user_id == "APP-001").all()
    for log in logs:
        assert "private_key" not in (log.details or "").lower()
        assert "privatekey" not in (log.details or "").lower()


def test_inactive_approver_rejected(client, db_session):
    """10. Test that an inactive approver cannot register credentials."""
    client.post("/seed")

    # Deactivate approver
    approver = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    approver.active = False
    db_session.commit()

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-001"})
    assert res_opts.status_code == 400
    assert "inactive" in res_opts.json()["detail"].lower()


def test_nonexistent_approver_returns_404(client):
    """11. Test requesting options for non-existent approver returns 404."""
    client.post("/seed")

    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-DOES-NOT-EXIST"})
    assert res_opts.status_code == 404
