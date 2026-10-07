import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend\app")
from app.main import app

client = TestClient(app)

demo_dir = r"C:\Users\USER\TrustGuard\demo-invoices"
new_invs = [f"INV-DEMO-0{i}" for i in range(11, 21)]

results = []

for inv_id in new_invs:
    pdf_path = os.path.join(demo_dir, f"{inv_id}.pdf")
    if not os.path.exists(pdf_path):
        print(f"Missing {pdf_path}")
        continue
    
    # 1. Upload and OCR
    with open(pdf_path, "rb") as f:
        resp = client.post("/api/v1/invoices/upload", files={"file": (f"{inv_id}.pdf", f, "application/pdf")})
    
    if resp.status_code != 200:
        print(f"Failed to upload {inv_id}: {resp.text}")
        continue
    
    data = resp.json()
    req_id = data["payment_request"]["request_id"]
    print(f"Uploaded {inv_id} -> {req_id}")
    
    # 2. Score
    score_resp = client.post(f"/api/v1/payments/{req_id}/score")
    if score_resp.status_code != 200:
        print(f"Failed to score {req_id}: {score_resp.text}")
        continue
        
    s_data = score_resp.json()
    
    # 3. Get Payment details
    pay_resp = client.get(f"/api/v1/payments/{req_id}")
    p_data = pay_resp.json()
    
    # SHAP details
    shap_reasons = []
    if p_data.get("risk_reasons"):
        try:
            reasons = json.loads(p_data["risk_reasons"])
            shap_reasons = [(k, v) for k, v in reasons.items()]
        except:
            pass

    results.append({
        "invoice_id": inv_id,
        "vendor": p_data["vendor_id"],
        "amount": p_data["amount"],
        "fraud_probability": p_data["fraud_probability"],
        "risk_score": p_data["risk_score"],
        "routing_tier": p_data["routing_tier"],
        "status": p_data["status"],
        "shap": shap_reasons[:3]
    })

print("\n--- RESULTS ---")
for r in results:
    print(f"\nInvoice: {r['invoice_id']}")
    print(f"Vendor: {r['vendor']}")
    print(f"Amount: {r['amount']}")
    print(f"Fraud Prob: {r['fraud_probability']}")
    print(f"Risk Score: {r['risk_score']}")
    print(f"Routing Tier: {r['routing_tier']}")
    print(f"Payment Status: {r['status']}")
    print(f"Top 3 SHAP: {r['shap']}")
