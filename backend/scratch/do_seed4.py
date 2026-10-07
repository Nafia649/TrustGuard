import re

with open(r"C:\Users\USER\TrustGuard\backend\scratch\seed_service_dump.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove delete
text = re.sub(r'    db\.query\(LedgerEntry\)\.delete\(\)\n.*?db\.commit\(\)', '    # db.query(LedgerEntry).delete() # disabled for idempotency', text, flags=re.DOTALL)

# 2. Add new vendors inside list
vendors = """        Vendor(
            vendor_id="VEND-013", vendor_name="NewTech Startups", approved=True, bank_account="NEW-BANK-013",
            onboarded_date=now - timedelta(days=2), usual_amount_mean=20000.0, usual_amount_std=1000.0, usual_hour=10.0, usual_weekday=1,
        ),
        Vendor(
            vendor_id="VEND-017", vendor_name="Shady Supplies Ltd", approved=False, bank_account="SHAD-BANK-017",
            onboarded_date=now - timedelta(days=1), usual_amount_mean=45000.0, usual_amount_std=100.0, usual_hour=23.0, usual_weekday=6,
        ),
        Vendor(
            vendor_id="VEND-020", vendor_name="Ghost Entity Corp", approved=False, bank_account="GHST-BANK-999",
            onboarded_date=now - timedelta(days=0), usual_amount_mean=99000.0, usual_amount_std=10.0, usual_hour=2.0, usual_weekday=0,
        ),
    ]
"""
text = text.replace('        ),\n    ]\n    db.add_all(vendors)', '        ),\n' + vendors + '    db.add_all(vendors)')

# 3. Add POs
pos = """        PurchaseOrder(po_id="PO-2026-011", vendor_id="VEND-001", amount=55000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-012", vendor_id="VEND-002", amount=210000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-013", vendor_id="VEND-013", amount=22000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-014", vendor_id="VEND-004", amount=33000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-015", vendor_id="VEND-005", amount=50000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-016", vendor_id="VEND-006", amount=20000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-017", vendor_id="VEND-017", amount=45000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-018", vendor_id="VEND-008", amount=50000.0, status="APPROVED", date=now - timedelta(days=10)),
        PurchaseOrder(po_id="PO-2026-019", vendor_id="VEND-003", amount=49000.0, status="APPROVED", date=now - timedelta(days=10)),
    ]
"""
text = text.replace('        ),\n    ]\n    db.add_all(purchase_orders)', '        ),\n' + pos + '    db.add_all(purchase_orders)')

# 4. Add GRNs
grns = """        GoodsReceipt(grn_id="GRN-2026-011", po_id="PO-2026-011", vendor_id="VEND-001", amount=55000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-012", po_id="PO-2026-012", vendor_id="VEND-002", amount=210000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-013", po_id="PO-2026-013", vendor_id="VEND-013", amount=22000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-014", po_id="PO-2026-014", vendor_id="VEND-004", amount=33000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-015", po_id="PO-2026-015", vendor_id="VEND-005", amount=50000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-016", po_id="PO-2026-016", vendor_id="VEND-006", amount=10000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-017", po_id="PO-2026-017", vendor_id="VEND-017", amount=45000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-018", po_id="PO-2026-018", vendor_id="VEND-008", amount=50000.0, date=now - timedelta(days=5)),
        GoodsReceipt(grn_id="GRN-2026-019", po_id="PO-2026-019", vendor_id="VEND-003", amount=49000.0, date=now - timedelta(days=5)),
"""
text = text.replace('        for i in range(1, 10)\n    ]', '        for i in range(1, 10)\n    ] + [\n' + grns + '    ]')

# 5. Add Payments history
hist = """        *[
            PaymentRequest(
                request_id=f"REQ-HIST-008-{i}", invoice_id=f"INV-HIST-008-{i}", vendor_id="VEND-008",
                amount=50000.0, currency="INR", status="PAID", created_at=now - timedelta(hours=i), risk_score=5, routing_tier="AUTO_APPROVE"
            ) for i in range(1, 10)
        ],
        PaymentRequest(request_id="REQ-HIST-003-1", invoice_id="INV-HIST-003-1", vendor_id="VEND-003", amount=49000.0, currency="INR", status="PAID", created_at=now - timedelta(hours=2), risk_score=5, routing_tier="AUTO_APPROVE"),
    ]
"""
text = text.replace('        ),\n    ]\n    db.add_all(payment_requests)', '        ),\n' + hist + '    db.add_all(payment_requests)')

# 6. Make inserts idempotent
text = text.replace("    db.add(policy_v1)", "    if not db.query(PolicyVersion).filter_by(version=1).first():\n        db.add(policy_v1)")
text = text.replace("    db.add_all(approvers)", "    for item in approvers:\n        if not db.query(Approver).filter_by(approver_id=getattr(item, 'approver_id')).first(): db.add(item)\n    db.flush()")
text = text.replace("    db.add_all(vendors)", "    for item in vendors:\n        if not db.query(Vendor).filter_by(vendor_id=getattr(item, 'vendor_id')).first(): db.add(item)\n    db.flush()")
text = text.replace("    db.add_all(purchase_orders)", "    for item in purchase_orders:\n        if not db.query(PurchaseOrder).filter_by(po_id=getattr(item, 'po_id')).first(): db.add(item)\n    db.flush()")
text = text.replace("    db.add_all(goods_receipts)", "    for item in goods_receipts:\n        if not db.query(GoodsReceipt).filter_by(grn_id=getattr(item, 'grn_id')).first(): db.add(item)\n    db.flush()")
text = text.replace("    db.add_all(payment_requests)", "    for item in payment_requests:\n        if not db.query(PaymentRequest).filter_by(request_id=getattr(item, 'request_id')).first(): db.add(item)\n    db.flush()")

with open(r"C:\Users\USER\TrustGuard\backend\app\services\seed_service.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Restored and updated from dump")
