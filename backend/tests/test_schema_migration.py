import json
from datetime import datetime
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.services.audit_service import calculate_hash, verify_chain, log_event, GENESIS_HASH
from app.services.migration_service import (
    apply_schema_migrations,
    backfill_audit_log_sequences,
    init_db,
)


def test_fresh_database_schema_contains_sequence():
    """Verify that a database created fresh from scratch contains the 'sequence' column on audit_logs."""
    fresh_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(fresh_engine)

    inspector = inspect(fresh_engine)
    columns = [col["name"] for col in inspector.get_columns("audit_logs")]
    assert "sequence" in columns
    assert "log_id" in columns
    assert "timestamp" in columns
    assert "current_hash" in columns

    # Verify a newly logged event receives sequence=1
    Session = sessionmaker(bind=fresh_engine)
    db = Session()
    try:
        entry = log_event(db, user_id="admin_fresh", action="TEST_FRESH", result="SUCCESS")
        assert entry.sequence == 1
        v = verify_chain(db)
        assert v["valid"] is True
        assert v["records_checked"] == 1
    finally:
        db.close()


def test_existing_database_missing_sequence_can_be_upgraded():
    """Verify that a legacy database created without the 'sequence' column is upgraded properly."""
    legacy_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 1. Manually create the legacy schema where 'sequence' is absent
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE audit_logs (
                    log_id VARCHAR NOT NULL PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    user_id VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    request_id VARCHAR,
                    result VARCHAR NOT NULL,
                    details TEXT,
                    previous_hash VARCHAR NOT NULL,
                    current_hash VARCHAR NOT NULL
                )
                """
            )
        )

    # Verify column is initially missing
    inspector_before = inspect(legacy_engine)
    cols_before = [col["name"] for col in inspector_before.get_columns("audit_logs")]
    assert "sequence" not in cols_before

    # 2. Run migration
    apply_schema_migrations(legacy_engine)

    # Verify column is added and index is created
    inspector_after = inspect(legacy_engine)
    cols_after = [col["name"] for col in inspector_after.get_columns("audit_logs")]
    assert "sequence" in cols_after

    indexes = [idx["name"] for idx in inspector_after.get_indexes("audit_logs")]
    assert "ix_audit_logs_sequence" in indexes


def test_existing_audit_records_receive_valid_sequence_values():
    """Verify that existing unsequenced records are assigned deterministic sequential numbers preserving the chain."""
    legacy_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create legacy table
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE audit_logs (
                    log_id VARCHAR NOT NULL PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    user_id VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    request_id VARCHAR,
                    result VARCHAR NOT NULL,
                    details TEXT,
                    previous_hash VARCHAR NOT NULL,
                    current_hash VARCHAR NOT NULL
                )
                """
            )
        )

    # Insert 3 chained audit records under legacy schema
    Session = sessionmaker(bind=legacy_engine)
    db = Session()
    prev = GENESIS_HASH
    log_ids = []
    for i in range(1, 4):
        lid = f"LOG-LEGACY-{i:03d}"
        log_ids.append(lid)
        ts = datetime.utcnow()
        action = f"LEGACY_ACTION_{i}"
        ch = calculate_hash(lid, ts, "user_old", action, None, "SUCCESS", "", prev)
        db.execute(
            text(
                """
                INSERT INTO audit_logs (log_id, timestamp, user_id, action, request_id, result, details, previous_hash, current_hash)
                VALUES (:lid, :ts, 'user_old', :action, NULL, 'SUCCESS', NULL, :prev, :ch)
                """
            ),
            {"lid": lid, "ts": ts, "action": action, "prev": prev, "ch": ch},
        )
        prev = ch
    db.commit()

    # Apply migration
    apply_schema_migrations(legacy_engine)

    # Check that sequence numbers 1, 2, 3 were assigned
    records = db.query(AuditLog).order_by(AuditLog.sequence.asc()).all()
    assert len(records) == 3
    assert [r.sequence for r in records] == [1, 2, 3]
    assert [r.log_id for r in records] == log_ids

    db.close()


def test_audit_hash_chain_verification_after_upgrade():
    """Verify that hash-chain verification still succeeds on upgraded records and links seamlessly to new records."""
    legacy_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE audit_logs (
                    log_id VARCHAR NOT NULL PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    user_id VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    request_id VARCHAR,
                    result VARCHAR NOT NULL,
                    details TEXT,
                    previous_hash VARCHAR NOT NULL,
                    current_hash VARCHAR NOT NULL
                )
                """
            )
        )

    Session = sessionmaker(bind=legacy_engine)
    db = Session()
    prev = GENESIS_HASH
    for i in range(1, 4):
        lid = f"LOG-CHAIN-{i:03d}"
        ts = datetime.utcnow()
        action = f"ACTION_{i}"
        ch = calculate_hash(lid, ts, "user_chain", action, None, "SUCCESS", "", prev)
        db.execute(
            text(
                """
                INSERT INTO audit_logs (log_id, timestamp, user_id, action, request_id, result, details, previous_hash, current_hash)
                VALUES (:lid, :ts, 'user_chain', :action, NULL, 'SUCCESS', NULL, :prev, :ch)
                """
            ),
            {"lid": lid, "ts": ts, "action": action, "prev": prev, "ch": ch},
        )
        prev = ch
    db.commit()

    # Apply migration
    apply_schema_migrations(legacy_engine)

    # Verify existing upgraded chain
    v1 = verify_chain(db)
    assert v1["valid"] is True
    assert v1["records_checked"] == 3
    assert v1["corrupted_id"] is None

    # Append a new record using current log_event function
    new_entry = log_event(db, user_id="user_new", action="POST_UPGRADE_ACTION", result="SUCCESS")
    assert new_entry.sequence == 4
    assert new_entry.previous_hash == prev

    # Verify chain after new record
    v2 = verify_chain(db)
    assert v2["valid"] is True
    assert v2["records_checked"] == 4
    assert v2["corrupted_id"] is None

    db.close()


def test_seed_and_scoring_works_after_upgrade():
    """Verify that /seed and payment scoring work smoothly after migrating an existing database."""
    legacy_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Initialize all other tables, but simulate audit_logs created with the legacy schema
    Base.metadata.create_all(bind=legacy_engine)
    with legacy_engine.begin() as conn:
        conn.execute(text("DROP TABLE audit_logs"))
        conn.execute(
            text(
                """
                CREATE TABLE audit_logs (
                    log_id VARCHAR NOT NULL PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    user_id VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    request_id VARCHAR,
                    result VARCHAR NOT NULL,
                    details TEXT,
                    previous_hash VARCHAR NOT NULL,
                    current_hash VARCHAR NOT NULL
                )
                """
            )
        )

    # Apply schema migrations
    apply_schema_migrations(legacy_engine)

    TestSession = sessionmaker(bind=legacy_engine)
    test_db = TestSession()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            # 1. Test POST /seed
            seed_res = client.post("/seed")
            assert seed_res.status_code == 200
            assert seed_res.json()["company"] == "Acme Ltd"

            # 2. Test POST /payments/REQ-DEMO-001/score
            score_res = client.post("/payments/REQ-DEMO-001/score")
            assert score_res.status_code == 200
            score_data = score_res.json()
            assert score_data["request_id"] == "REQ-DEMO-001"
            assert score_data["status"] == "AUTHORIZED"
            assert "risk_score" in score_data

            # 3. Verify audit chain verification endpoint
            verify_res = client.get("/audit-log/verify")
            assert verify_res.status_code == 200
            assert verify_res.json()["valid"] is True
            assert verify_res.json()["records_checked"] > 0
    finally:
        app.dependency_overrides.clear()
        test_db.close()
