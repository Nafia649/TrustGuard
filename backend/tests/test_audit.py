import json
import pytest
from app.models.audit_log import AuditLog
from app.services.audit_service import (
    verify_chain,
    log_event,
    calculate_hash,
    GENESIS_HASH,
)


@pytest.fixture(autouse=True)
def clean_audit_table(db_session):
    """Ensure audit table is clean before each test to guarantee test isolation."""
    db_session.query(AuditLog).delete()
    db_session.commit()
    yield


def test_audit_chain_valid(db_session):
    """Verify that a freshly generated series of audit events creates a strictly valid hash chain."""
    entry1 = log_event(db_session, user_id="admin_1", action="INIT", result="SUCCESS", details={"step": 1})
    entry2 = log_event(db_session, user_id="system", action="PROCESS", result="SUCCESS", details={"step": 2})
    entry3 = log_event(db_session, user_id="admin_2", action="FINISH", result="SUCCESS", details={"step": 3})

    assert entry1.previous_hash == GENESIS_HASH
    assert entry2.previous_hash == entry1.current_hash
    assert entry3.previous_hash == entry2.current_hash

    res = verify_chain(db_session)
    assert res["valid"] is True
    assert res["records_checked"] == 3
    assert res["corrupted_id"] is None
    assert res["reason"] is None


def test_audit_chain_broken_previous_hash(db_session):
    """Verify detection when an attacker alters an entry's previous_hash link."""
    entry1 = log_event(db_session, user_id="user1", action="A1", result="SUCCESS")
    entry2 = log_event(db_session, user_id="user2", action="A2", result="SUCCESS")
    entry3 = log_event(db_session, user_id="user3", action="A3", result="SUCCESS")

    # Corrupt previous_hash of entry2
    entry2.previous_hash = "deadbeef" * 8
    db_session.commit()

    res = verify_chain(db_session)
    assert res["valid"] is False
    assert res["corrupted_id"] == entry2.log_id
    assert "broken link" in res["reason"].lower()


def test_audit_chain_modified_current_hash(db_session):
    """Verify detection when an entry's stored current_hash is tampered with."""
    entry1 = log_event(db_session, user_id="user1", action="A1", result="SUCCESS")
    entry2 = log_event(db_session, user_id="user2", action="A2", result="SUCCESS")

    # Corrupt current_hash of entry1 without changing its data
    entry1.current_hash = "badhash" * 9 + "abcd"
    db_session.commit()

    res = verify_chain(db_session)
    assert res["valid"] is False
    assert res["corrupted_id"] == entry1.log_id
    assert "hash mismatch" in res["reason"].lower()


def test_audit_chain_modified_record_data(db_session):
    """Verify detection when an entry's action, details, or result are changed in-place."""
    entry1 = log_event(db_session, user_id="user1", action="GENUINE_ACTION", result="SUCCESS", details={"amount": 1000})
    entry2 = log_event(db_session, user_id="user2", action="A2", result="SUCCESS")

    # Tamper with action
    entry1.action = "TAMPERED_ACTION"
    db_session.commit()

    res = verify_chain(db_session)
    assert res["valid"] is False
    assert res["corrupted_id"] == entry1.log_id
    assert "hash mismatch" in res["reason"].lower()

    # Revert action, tamper with details
    entry1.action = "GENUINE_ACTION"
    entry1.details = json.dumps({"amount": 99999999})
    db_session.commit()

    res2 = verify_chain(db_session)
    assert res2["valid"] is False
    assert res2["corrupted_id"] == entry1.log_id
    assert "hash mismatch" in res2["reason"].lower()

    # Revert details, tamper with result
    entry1.details = json.dumps({"amount": 1000}, sort_keys=True)
    entry1.result = "FAILED_TAMPERED"
    db_session.commit()

    res3 = verify_chain(db_session)
    assert res3["valid"] is False
    assert res3["corrupted_id"] == entry1.log_id


def test_audit_log_endpoint_listing_and_filtering(client):
    """Verify GET /audit-log returns records and supports filtering, sorting, and pagination."""
    client.post("/seed")

    # 1. Fetch all audit logs
    res = client.get("/audit-log")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    first = logs[0]
    assert "log_id" in first
    assert "timestamp" in first
    assert "action" in first
    assert "previous_hash" in first
    assert "current_hash" in first

    # 2. Filter by action
    seed_logs_res = client.get("/audit-log?action=DATABASE_SEEDED")
    assert seed_logs_res.status_code == 200
    seed_logs = seed_logs_res.json()
    assert len(seed_logs) >= 1
    assert all(l["action"] == "DATABASE_SEEDED" for l in seed_logs)

    # 3. Pagination
    paginated_res = client.get("/audit-log?limit=2&offset=0")
    assert paginated_res.status_code == 200
    assert len(paginated_res.json()) <= 2

    # 4. Sorting: asc vs desc
    asc_res = client.get("/audit-log?order=asc")
    desc_res = client.get("/audit-log?order=desc")
    assert asc_res.status_code == 200
    assert desc_res.status_code == 200
    if len(asc_res.json()) >= 2:
        assert asc_res.json()[0]["log_id"] == desc_res.json()[-1]["log_id"]


def test_audit_log_single_entry_endpoint(client):
    """Verify GET /audit-log/{log_id} returns specific record or 404."""
    client.post("/seed")
    logs = client.get("/audit-log").json()
    target_id = logs[0]["log_id"]

    res = client.get(f"/audit-log/{target_id}")
    assert res.status_code == 200
    assert res.json()["log_id"] == target_id

    # 404 test
    res_404 = client.get("/audit-log/LOG-NONEXISTENT-999")
    assert res_404.status_code == 404


def test_audit_log_api_verify_endpoint(client, db_session):
    """Verify GET /audit-log/verify endpoint correctly identifies pristine vs tampered chains."""
    client.post("/seed")

    # 1. Pristine chain verification
    verify_res = client.get("/audit-log/verify")
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["valid"] is True
    assert v_data["records_checked"] > 0
    assert v_data["corrupted_id"] is None

    # Also test verify=true header parameter on list endpoint
    list_res = client.get("/audit-log?verify=true")
    assert list_res.status_code == 200
    assert list_res.headers.get("x-audit-chain-valid") == "true"

    # 2. Tamper with a record in the database
    target_record = db_session.query(AuditLog).first()
    assert target_record is not None
    target_record.action = "TAMPERED_BY_MALICIOUS_ACTOR"
    db_session.commit()

    # 3. Verification must fail
    tampered_verify_res = client.get("/audit-log/verify")
    assert tampered_verify_res.status_code == 200
    t_data = tampered_verify_res.json()
    assert t_data["valid"] is False
    assert t_data["corrupted_id"] == target_record.log_id

    # List endpoint with verify=true reflects invalid state in header
    list_res_tampered = client.get("/audit-log?verify=true")
    assert list_res_tampered.headers.get("x-audit-chain-valid") == "false"
