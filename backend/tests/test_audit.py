from app.services.audit_service import verify_chain, log_event


def test_audit_hash_chain_validity(client, db_session):
    """Verify that audit records created during seeding and payment requests maintain cryptographic chain validity."""
    client.post("/seed")
    verification = verify_chain(db_session)
    assert verification["valid"] is True
    assert verification["records_checked"] > 0
    assert verification["corrupted_id"] is None


def test_audit_chain_tamper_detection(db_session):
    """Verify that any modification of an audit record is immediately detected by verify_chain."""
    # Create two chained records
    entry1 = log_event(db_session, user_id="user1", action="ACTION_1", result="SUCCESS")
    entry2 = log_event(db_session, user_id="user2", action="ACTION_2", result="SUCCESS")

    # Verify initial chain is valid
    assert verify_chain(db_session)["valid"] is True

    # Tamper with the first record's action
    entry1.action = "TAMPERED_ACTION"
    db_session.commit()

    # Chain verification must fail
    tamper_result = verify_chain(db_session)
    assert tamper_result["valid"] is False
    assert tamper_result["corrupted_id"] == entry1.log_id
