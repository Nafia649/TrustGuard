import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.audit_log import AuditLog

def diagnose():
    db = SessionLocal()
    
    records = db.query(AuditLog).order_by(AuditLog.sequence.asc(), AuditLog.timestamp.asc(), AuditLog.log_id.asc()).all()
    
    print("--- ALL RECORDS AROUND SEQUENCE 77 ---")
    for r in records[-10:]:
        print(f"Seq: {r.sequence}, ID: {r.log_id}, PrevHash: {r.previous_hash[:10]}..., CurrHash: {r.current_hash[:10]}...")

if __name__ == "__main__":
    diagnose()
