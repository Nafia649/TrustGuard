from fastapi.testclient import TestClient
from app.main import app
import sys

client = TestClient(app)

# 1. Upload
with open("../demo-invoices/INV-DEMO-021.pdf", "rb") as f:
    upload_res = client.post("/api/v1/invoices/upload", files={"file": ("INV-DEMO-021.pdf", f, "application/pdf")})

doc_id = upload_res.json()["document_id"]

# 2. Extract
ocr_res = client.get(f"/api/v1/invoices/{doc_id}")
ocr_data = ocr_res.json().get("extracted_data")

# 3. Create request
req_res = client.post(f"/api/v1/invoices/{doc_id}/create-payment-request", json={
    "invoice_id": ocr_data.get("invoice_id") or "INV-DEMO-021",
    "amount": ocr_data.get("total_amount") or 42000.0,
    "vendor_id": ocr_data.get("vendor_id"),
    "po_id": ocr_data.get("po_id")
})
print(req_res.json())
req_id = req_res.json().get("payment_request_id")

if req_id:
    # 4. Score
    score_res = client.post(f"/api/v1/payments/{req_id}/score")
    print("Score:", score_res.json().get('risk_score'))
    print("Reasons:", score_res.json().get('reasons'))
