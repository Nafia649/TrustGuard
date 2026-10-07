import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.payment_request import PaymentRequest
from app.models.policy import PolicyVersion
from app.services.policy_engine import evaluate_routing

db = SessionLocal()
payment = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == "INV-DEMO-005").order_by(PaymentRequest.timestamp.desc()).first()

print(f"Risk Score: 99")
print(f"Amount: {payment.amount}")

routing = evaluate_routing(db, payment.amount, 99.0)
print(f"Routing Tier: {routing.tier}")

policy_row = db.query(PolicyVersion).filter(PolicyVersion.active == True).first()
pol = json.loads(policy_row.policy_json)
print(f"Auto-approve cap amount: {pol.get('auto_approve_cap_amount')}")

