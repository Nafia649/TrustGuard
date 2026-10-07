import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.audit_log import AuditLog

def diagnose():
    db = SessionLocal()
    
    # 1. Call verification logic directly
    from app.services.audit_service import verify_chain
    
    print("--- 1. VERIFICATION API RESPONSE ---")
    verification_result = verify_chain(db)
    print(json.dumps(verification_result, indent=2))
    
    corrupted_id = verification_result.get("corrupted_record_id")
    if not corrupted_id:
        print("No corrupted ID found in verification result?!")
        # Fallback to the one the user specified
        corrupted_id = "LOG-2811B91C10D0"
        
    print(f"\n--- 2. CORRUPTED RECORD: {corrupted_id} ---")
    corrupted_record = db.query(AuditLog).filter(AuditLog.log_id == corrupted_id).first()
    if not corrupted_record:
        print(f"Record {corrupted_id} not found!")
    else:
        print(f"Sequence: {corrupted_record.sequence}")
        print(f"Timestamp: {corrupted_record.timestamp}")
        print(f"Action: {corrupted_record.action}")
        print(f"User ID: {corrupted_record.user_id}")
        print(f"Request ID: {corrupted_record.request_id}")
        print(f"Previous Hash: {corrupted_record.previous_hash}")
        print(f"Current Hash: {corrupted_record.current_hash}")
        print(f"Details: {corrupted_record.details}")
        
        print(f"\n--- 3. PREVIOUS RECORD ---")
        prev_sequence = corrupted_record.sequence - 1
        prev_record = db.query(AuditLog).filter(AuditLog.sequence == prev_sequence).first()
        if not prev_record:
            print("No previous record found!")
        else:
            print(f"Previous Sequence: {prev_record.sequence}")
            print(f"Previous ID: {prev_record.log_id}")
            print(f"Previous Current Hash: {prev_record.current_hash}")
            
            print("\n--- COMPARISON ---")
            if corrupted_record.previous_hash == prev_record.current_hash:
                print("PREVIOUS HASH LINK: MATCH")
            else:
                print("PREVIOUS HASH LINK: MISMATCH")
                print(f"Stored previous_hash: {corrupted_record.previous_hash}")
                print(f"Actual previous current_hash: {prev_record.current_hash}")
                
        print("\n--- 4. HASH RECALCULATION ---")
        from app.services.audit_service import calculate_hash
        
        recalc_hash = calculate_hash(
            timestamp=corrupted_record.timestamp,
            user_id=corrupted_record.user_id,
            action=corrupted_record.action,
            request_id=corrupted_record.request_id,
            result=corrupted_record.result,
            details=corrupted_record.details,
            previous_hash=corrupted_record.previous_hash
        )
        print(f"Stored current_hash: {corrupted_record.current_hash}")
        print(f"Expected current_hash (recalculated): {recalc_hash}")
        if corrupted_record.current_hash == recalc_hash:
            print("CURRENT HASH: MATCH")
        else:
            print("CURRENT HASH: MISMATCH")

if __name__ == "__main__":
    diagnose()
