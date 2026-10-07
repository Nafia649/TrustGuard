import json
import os
import sys
sys.path.append('C:/Users/USER/TrustGuard')
sys.path.append('C:/Users/USER/TrustGuard/backend')

from app.database import SessionLocal
from app.models.invoice_document import InvoiceDocument
from app.models.payment_request import PaymentRequest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.services.invoice_generator import DEMO_INVOICE_DEFINITIONS

db = SessionLocal()

print('Invoice | PDF PO | DB Payment PO | PO Exists | PO Approved | GRN Exists | Vendor')
print('-' * 90)

for i in range(11, 21):
    inv_id = f'INV-DEMO-0{i}'
    
    # 1. PDF PO number (from definitions)
    pdf_po = None
    vendor_expected = None
    for item in DEMO_INVOICE_DEFINITIONS:
        if item['invoice_id'] == inv_id:
            pdf_po = item['po_id']
            vendor_expected = item['vendor_id']
            break
            
    # 2. InvoiceDocument extracted po_id
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.extracted_data.like(f'%{inv_id}%')).first()
    extracted_po = None
    if doc and doc.extracted_data:
        try:
            data = json.loads(doc.extracted_data)
            extracted_po = data.get('po_id')
        except:
            pass
            
    # 3. PaymentRequest po_id
    pr = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == inv_id).order_by(PaymentRequest.timestamp.desc()).first()
    db_po = pr.po_id if pr else None
    vendor = pr.vendor_id if pr else vendor_expected
    
    # 4. Database PO record & 5. PO vendor_id & 6. PO Approved
    po_record = None
    if pdf_po:
        po_record = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == pdf_po).first()
        
    po_exists = bool(po_record)
    po_approved = (po_record.status == 'APPROVED') if po_record else False
    
    # 7. GRN record
    grn_record = None
    if pdf_po:
        grn_record = db.query(GoodsReceipt).filter(GoodsReceipt.po_id == pdf_po).first()
        
    grn_exists = bool(grn_record)
    
    print(f'{inv_id:<12} | {str(pdf_po):<10} | {str(db_po):<13} | {str(po_exists):<10} | {str(po_approved):<12} | {str(grn_exists):<11} | {str(vendor):<10}')
    
print('\nInvestigating velocity for possible_split_payment:')
from app.services.feature_builder import build_ml_features

for i in range(11, 21):
    inv_id = f'INV-DEMO-0{i}'
    pr = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == inv_id).order_by(PaymentRequest.timestamp.desc()).first()
    if pr:
        feats = build_ml_features(db, pr)
        print(f'{inv_id}: split={feats.get("possible_split_payment")}, p_24h={feats.get("payments_last_24h")}, a_24h={feats.get("amount_last_24h")}')

