import sys
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.payment_request import PaymentRequest
import json

def diagnose():
    db = SessionLocal()
    payment = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == "INV-DEMO-005").order_by(PaymentRequest.timestamp.desc()).first()
    if not payment:
        print("Payment with INV-DEMO-005 not found in DB.")
        sys.exit(1)

    print(f"Request ID: {payment.request_id}")
    print(f"Vendor: {payment.vendor_id}")
    print(f"Amount: {payment.amount}")
    print(f"Status: {payment.status}")
    print(f"Risk Score: {payment.risk_score}")
    print(f"Routing Tier: {payment.routing_tier}")
    print(f"Fraud Prob: {payment.fraud_probability}")
    print(f"Risk Reasons: {payment.risk_reasons}")

if __name__ == "__main__":
    diagnose()
