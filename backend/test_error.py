import sys; sys.path.append('C:/Users/USER/TrustGuard'); sys.path.append('C:/Users/USER/TrustGuard/backend')
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
doc = client.get('/api/v1/invoices').json()[0]
doc_id = doc['document_id']
res = client.post(f'/api/v1/invoices/{doc_id}/create-payment-request', json={'invoice_id':'test', 'amount':100})
print(res.status_code, res.text)
