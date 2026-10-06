"""
Lightweight Schema Migration Service for TrustGuard.
Ensures existing SQLite databases are smoothly upgraded to the current schema
without losing data, corrupting the hash-chain, or requiring database resets.
"""
import logging
from typing import Optional
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from app.services.audit_service import GENESIS_HASH

logger = logging.getLogger(__name__)


def apply_schema_migrations(engine: Engine) -> None:
    """
    Applies incremental schema updates to existing SQLite tables.
    Safe for both fresh databases and pre-existing legacy databases.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    # 1. AuditLog: Ensure 'sequence' column and index exist
    if "audit_logs" in table_names:
        columns = [col["name"] for col in inspector.get_columns("audit_logs")]
        if "sequence" not in columns:
            logger.info("Migrating audit_logs: adding missing 'sequence' column...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN sequence INTEGER"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_sequence ON audit_logs (sequence)"))

        # 2. Backfill sequence values for any existing unsequenced audit records
        backfill_audit_log_sequences(engine)


def backfill_audit_log_sequences(engine: Engine) -> int:
    """
    Assigns deterministic sequential integers to any unsequenced audit records
    preserving the exact hash-chain and chronological order.
    Returns the number of records updated.
    """
    with engine.begin() as conn:
        # Check if there are any unsequenced records
        unsequenced_count = conn.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE sequence IS NULL")
        ).scalar()
        if not unsequenced_count:
            return 0

        # Find the current max sequence (if any already sequenced)
        max_seq = conn.execute(
            text("SELECT COALESCE(MAX(sequence), 0) FROM audit_logs WHERE sequence IS NOT NULL")
        ).scalar() or 0

        # Retrieve all unsequenced records ordered by timestamp
        rows = conn.execute(
            text(
                "SELECT log_id, timestamp, previous_hash, current_hash "
                "FROM audit_logs WHERE sequence IS NULL ORDER BY timestamp ASC, rowid ASC"
            )
        ).fetchall()

        if not rows:
            return 0

        # Map unsequenced records by their previous_hash to follow the chain
        rows_by_prev = {r[2]: r for r in rows}

        # Determine starting previous_hash:
        # If there are existing sequenced records, start from the last sequenced record's current_hash
        starting_prev = GENESIS_HASH
        if max_seq > 0:
            last_hash = conn.execute(
                text("SELECT current_hash FROM audit_logs WHERE sequence = :seq"),
                {"seq": max_seq},
            ).scalar()
            if last_hash:
                starting_prev = last_hash

        ordered_rows = []
        curr_prev = starting_prev
        while curr_prev in rows_by_prev:
            row = rows_by_prev.pop(curr_prev)
            ordered_rows.append(row)
            curr_prev = row[3]  # current_hash of this record is previous_hash of the next

        # Fallback: append any remaining records ordered by timestamp/rowid
        for r in rows:
            if r not in ordered_rows:
                ordered_rows.append(r)

        current_seq = max_seq
        for row in ordered_rows:
            current_seq += 1
            conn.execute(
                text("UPDATE audit_logs SET sequence = :seq WHERE log_id = :log_id"),
                {"seq": current_seq, "log_id": row[0]},
            )

        logger.info(f"Backfilled sequence values for {len(ordered_rows)} audit records.")
        return len(ordered_rows)


def init_db(engine: Engine) -> None:
    """
    Initializes database tables and applies any required schema updates.
    """
    from app.database import Base
    import app.models  # Ensure all models are registered with Base.metadata

    Base.metadata.create_all(bind=engine)
    apply_schema_migrations(engine)
