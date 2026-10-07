import os
import sys
import json
from fastapi.testclient import TestClient

def test_score_all():
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
        
        print(f"[{inv_id}] Upload status: {resp.status_code}")
        if resp.status_code not in (200, 201, 202):
            print(f"[{inv_id}] Failed to upload: {resp.text}")
            continue
        
        data = resp.json()
        doc_id = data["document_id"]
        extracted = data.get("extracted_data", {})
        vendor_match = data.get("vendor_match", {})
        
        conf = {
            "vendor_id": vendor_match.get("matched_vendor_id"),
            "vendor_name": extracted.get("vendor_name"),
            "invoice_id": extracted.get("invoice_id"),
            "amount": extracted.get("total_amount"),
            "currency": extracted.get("currency", "INR"),
            "bank_account": extracted.get("bank_account"),
            "po_id": extracted.get("po_id")
        }
        
        # 1.b Create Payment Request
        create_resp = client.post(f"/api/v1/invoices/{doc_id}/create-payment-request", json=conf)
        print(f"[{inv_id}] Create PR status: {create_resp.status_code}")
        if create_resp.status_code != 201:
            print(f"[{inv_id}] Failed to create PR: {create_resp.text}")
            continue
            
        create_data = create_resp.json()
        req_id = create_data["payment"]["request_id"]
        print(f"[{inv_id}] REQ ID: {req_id}")
        
        # 2. Score
        score_resp = client.post(f"/api/v1/payments/{req_id}/score")
        print(f"[{inv_id}] Score status: {score_resp.status_code}")
        if score_resp.status_code != 200:
            print(f"[{inv_id}] Failed to score: {score_resp.text}")
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
                if isinstance(reasons, dict):
                    shap_reasons = [(k, v) for k, v in reasons.items()]
                elif isinstance(reasons, list):
                    shap_reasons = reasons[:3]
            except Exception as e:
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

    with open(r"C:\Users\USER\TrustGuard\backend\scratch\score_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n\n=== FINAL REPORT ===")
    for r in results:
        print(f"Invoice: {r['invoice_id']} | Vendor: {r['vendor']} | Amount: {r['amount']}")
        print(f"  Risk Score: {r['risk_score']} (Prob: {r['fraud_probability']:.4f}) -> {r['routing_tier']}")
        print(f"  Status: {r['status']}")
        print(f"  Top 3 SHAP: {r['shap']}")
        print("-" * 50)
