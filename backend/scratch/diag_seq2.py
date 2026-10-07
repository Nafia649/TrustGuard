import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.audit_log import AuditLog

def diagnose():
    db = SessionLocal()
    
    records = db.query(AuditLog).filter(AuditLog.sequence >= 77).order_by(AuditLog.sequence.asc(), AuditLog.timestamp.asc(), AuditLog.log_id.asc()).all()
    
    print("--- ALL RECORDS FROM SEQUENCE 77 ---")
    for r in records:
        print(f"Seq: {r.sequence}, ID: {r.log_id}, Action: {r.action}, ReqID: {r.request_id}, Time: {r.timestamp}")

if __name__ == "__main__":
    diagnose()
