import json
import os
import sys
sys.path.append('C:/Users/USER/TrustGuard')
sys.path.append('C:/Users/USER/TrustGuard/backend')

from app.database import SessionLocal
from app.models.invoice_document import InvoiceDocument
from app.models.payment_request import PaymentRequest
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt

db = SessionLocal()

print('Invoice      | OCR PO     | Payment PO   | PO Exists  | PO Approved | GRN Exists | Match Result')
print('-' * 95)

for i in range(11, 21):
    inv_id = f'INV-DEMO-0{i}'
    
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.extracted_data.like(f'%{inv_id}%')).first()
    ocr_po = None
    if doc and doc.extracted_data:
        try:
            data = json.loads(doc.extracted_data)
            ocr_po = data.get('po_id')
        except:
            pass
            
    pr = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == inv_id).order_by(PaymentRequest.timestamp.desc()).first()
    db_po = pr.po_id if pr else None
    
    po_record = None
    if db_po:
        po_record = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == db_po).first()
        
    po_exists = bool(po_record)
    po_approved = (po_record.status == 'APPROVED') if po_record else False
    
    grn_record = None
    if db_po:
        grn_record = db.query(GoodsReceipt).filter(GoodsReceipt.po_id == db_po).first()
        
    grn_exists = bool(grn_record)
    match_result = 'PASS' if (po_exists and grn_exists) else 'FAIL'
    
    print(f'{inv_id:<12} | {str(ocr_po):<10} | {str(db_po):<12} | {str(po_exists):<10} | {str(po_approved):<11} | {str(grn_exists):<10} | {match_result}')
    
