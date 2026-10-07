import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.payment_request import PaymentRequest

def diagnose():
    db = SessionLocal()
    # Find the request ID
    payment = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == "INV-DEMO-005").order_by(PaymentRequest.timestamp.desc()).first()
    if not payment:
        print("Payment not found.")
        return
        
    req_id = payment.request_id
    print(f"Target Request ID: {req_id}")
    
    # 1. Simulate API call to GET /api/v1/payments/{request_id}
    # We will just directly invoke the FastAPI app or make a real HTTP request if it's running. 
    # Since it might not be running on a port, we can just serialize the Pydantic schema 
    # exactly as the endpoint does.
    from app.schemas.payment import PaymentResponse
    
    # Let's see the raw object attributes
    print(f"\n--- DB OBJECT ---")
    print(f"risk_score in DB: {payment.risk_score}")
    print(f"fraud_prob in DB: {payment.fraud_probability}")
    
    # Convert to schema
    response_model = PaymentResponse.model_validate(payment)
    json_response = response_model.model_dump_json(indent=2)
    print("\n--- BACKEND API RESPONSE (PaymentResponse) ---")
    print(json_response)
    
if __name__ == "__main__":
    diagnose()
