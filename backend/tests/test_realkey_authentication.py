"""
Tests for REALKEY Phase 2 — WebAuthn Authentication / Assertion Verification.

Verifies:
1. Valid authentication (with and without approver_id)
2. Unknown credential rejection
3. Unknown approver rejection
4. Inactive approver rejection
5. Invalid challenge rejection
6. Expired challenge rejection
7. Reused challenge rejection (single-use guarantee)
8. Invalid origin rejection
9. Invalid RP ID rejection
10. Invalid cryptographic signature rejection
11. Sign-counter / replay violation rejection
12. Malformed assertion payload rejection
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


def _register_approver(client, approver_id="APP-001"):
    """Helper to register a genuine WebAuthn credential for an approver."""
    client.post("/seed")
    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": approver_id})
    assert res_opts.status_code == 200
    options = res_opts.json()["options"]

    sim_client = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    cred = sim_client.create_credential(options=options)
    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": approver_id, "credential": cred},
    )
    assert res_verify.status_code == 200
    return sim_client, cred


def test_valid_webauthn_authentication(client, db_session):
    """1. Test successful, cryptographically valid WebAuthn authentication assertion."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    # Part A: Authentication with explicit approver_id
    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    assert res_opts.status_code == 200
    data_opts = res_opts.json()
    assert "challenge_id" in data_opts
    assert data_opts["options"]["rpId"] == "localhost"

    assertion = sim_client.sign_assertion(options=data_opts["options"], sign_count=1)

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_verify.status_code == 200
    data_verify = res_verify.json()
    assert data_verify["status"] == "authenticated"
    assert data_verify["approver_id"] == "APP-001"
    assert data_verify["name"] == "Alice Smith"
    assert data_verify["role"] == "senior_administrator"
    assert data_verify["sign_count"] == 1

    # Verify sign count updated in DB
    app = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    assert app.sign_count == 1

    # Part B: Discoverable authentication (approver_id omitted in verify request)
    res_opts2 = client.post("/auth/webauthn/authenticate/options", json={})
    assert res_opts2.status_code == 200
    assertion2 = sim_client.sign_assertion(options=res_opts2.json()["options"], sign_count=2)

    res_verify2 = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"credential": assertion2},
    )
    assert res_verify2.status_code == 200
    data_verify2 = res_verify2.json()
    assert data_verify2["approver_id"] == "APP-001"
    assert data_verify2["sign_count"] == 2


def test_unknown_credential_rejected(client):
    """2. Test assertion with an unregistered credential ID is rejected with 404."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={})
    # Client asserts with an unknown credential ID
    assertion = sim_client.sign_assertion(
        options=res_opts.json()["options"],
        override_credential_id=b"unregistered_123",
        sign_count=1,
    )

    res_verify = client.post("/auth/webauthn/authenticate/verify", json={"credential": assertion})
    assert res_verify.status_code == 404
    assert "unknown credential" in res_verify.json()["detail"].lower()


def test_unknown_approver_rejected(client):
    """3. Test authentication for non-existent approver returns 404."""
    client.post("/seed")

    # Options request for unknown approver
    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-DOES-NOT-EXIST"})
    assert res_opts.status_code == 404

    # Verify request for unknown approver
    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-DOES-NOT-EXIST", "credential": {"id": "dummy", "response": {}}},
    )
    assert res_verify.status_code == 404


def test_inactive_approver_rejected(client, db_session):
    """4. Test that deactivated approver cannot authenticate."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    # Deactivate approver
    app = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    app.active = False
    db_session.commit()

    # Options request fails
    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    assert res_opts.status_code == 400
    assert "inactive" in res_opts.json()["detail"].lower()


def test_invalid_challenge_rejected(client):
    """5. Test assertion signed with an invalid/altered challenge fails."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Sign tampered challenge
    assertion = sim_client.sign_assertion(
        options=options,
        override_challenge_b64="TAMPERED_CHALLENGE_BYTES_INCORRECT",
        sign_count=1,
    )

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_verify.status_code in (400, 404)


def test_expired_challenge_rejected(client):
    """6. Test assertion with an expired challenge is rejected."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Force expiration in challenge store
    chal = challenge_store.get_valid_authentication_challenge(approver_id="APP-001")
    chal.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    assertion = sim_client.sign_assertion(options=options, sign_count=1)

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_verify.status_code == 400
    assert "expired" in res_verify.json()["detail"].lower()


def test_reused_challenge_rejected(client):
    """7. Test that an authentication challenge cannot be replayed/reused."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]
    assertion = sim_client.sign_assertion(options=options, sign_count=1)

    # First attempt succeeds
    res1 = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res1.status_code == 200

    # Replay attempt fails
    res_replay = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_replay.status_code == 400
    assert "already been used" in res_replay.json()["detail"].lower()


def test_invalid_origin_rejected(client):
    """8. Test assertion created under an unlisted/phishing origin fails."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    assertion = sim_client.sign_assertion(
        options=options,
        override_origin="https://phishing-attacker.com",
        sign_count=1,
    )

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_verify.status_code == 400
    assert "origin" in res_verify.json()["detail"].lower()


def test_invalid_rp_id_rejected(client):
    """9. Test assertion where RP ID hash does not match configured RP ID fails."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    assertion = sim_client.sign_assertion(
        options=options,
        override_rp_id="rogue-rpid.com",
        sign_count=1,
    )

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_verify.status_code == 400
    assert "rp id" in res_verify.json()["detail"].lower()


def test_invalid_signature_rejected(client):
    """10. Test assertion with an invalid/corrupted cryptographic signature fails."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Sign with a completely different rogue keypair
    rogue_client = VirtualWebAuthnClient()
    rogue_client.create_credential(options=options)
    rogue_assertion = rogue_client.sign_assertion(
        options=options,
        override_credential_id=sim_client._credential_id,
        sign_count=1,
    )

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": rogue_assertion},
    )
    assert res_verify.status_code == 400
    assert "signature" in res_verify.json()["detail"].lower()


def test_sign_counter_replay_violation_rejected(client, db_session):
    """11. Test that counter rollback or equal count is rejected (replay/cloning defense)."""
    sim_client, _ = _register_approver(client, approver_id="APP-001")

    # Set approver sign_count in DB to 10
    app = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    app.sign_count = 10
    db_session.commit()

    res_opts = client.post("/auth/webauthn/authenticate/options", json={"approver_id": "APP-001"})
    options = res_opts.json()["options"]

    # Authenticator returns sign_count=5 (less than 10)
    assertion = sim_client.sign_assertion(options=options, sign_count=5)

    res_verify = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"approver_id": "APP-001", "credential": assertion},
    )
    assert res_verify.status_code == 400
    assert "sign count" in res_verify.json()["detail"].lower()


def test_malformed_assertion_payload_rejected(client):
    """12. Test malformed payload structures are rejected."""
    _, cred = _register_approver(client, approver_id="APP-001")

    # Payload with missing ID
    res1 = client.post("/auth/webauthn/authenticate/verify", json={"credential": {}})
    assert res1.status_code == 400

    # Payload with invalid response dictionary
    res2 = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"credential": {"id": cred["id"], "response": "not_a_dict"}},
    )
    assert res2.status_code == 400

    # Payload with missing clientDataJSON
    res3 = client.post(
        "/auth/webauthn/authenticate/verify",
        json={"credential": {"id": cred["id"], "response": {}}},
    )
    assert res3.status_code == 400
