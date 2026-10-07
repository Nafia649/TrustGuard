import re

path = r"C:\Users\USER\TrustGuard\backend\app\services\seed_service.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove delete
text = re.sub(r'    db\.query\(LedgerEntry\)\.delete\(\)\n.*?db\.commit\(\)', '    # db.query(LedgerEntry).delete() # disabled for idempotency', text, flags=re.DOTALL)

# 2. Add new invoices
vendors = """        Vendor(
            vendor_id="VEND-013",
            vendor_name="NewTech Startups",
            approved=True,
            bank_account="NEW-BANK-013",
            onboarded_date=now - timedelta(days=2),
            usual_amount_mean=20000.0,
            usual_amount_std=1000.0,
            usual_hour=10.0,
            usual_weekday=1,
        ),
        Vendor(
            vendor_id="VEND-017",
            vendor_name="Shady Supplies Ltd",
            approved=False,
            bank_account="SHAD-BANK-017",
            onboarded_date=now - timedelta(days=1),
            usual_amount_mean=45000.0,
            usual_amount_std=100.0,
            usual_hour=23.0,
            usual_weekday=6,
        ),
        Vendor(
            vendor_id="VEND-020",
            vendor_name="Ghost Entity Corp",
            approved=False,
            bank_account="GHST-BANK-999",
            onboarded_date=now - timedelta(days=0),
            usual_amount_mean=99000.0,
            usual_amount_std=10.0,
            usual_hour=2.0,
            usual_weekday=0,
        ),
"""
text = text.replace('    db.add_all(vendors)', vendors + '    db.add_all(vendors)')

pos = """        PurchaseOrder(
            po_id="PO-2026-011",
            vendor_id="VEND-001",
            amount=55000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-012",
            vendor_id="VEND-002",
            amount=210000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-013",
            vendor_id="VEND-013",
            amount=22000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-014",
            vendor_id="VEND-004",
            amount=33000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-015",
            vendor_id="VEND-005",
            amount=50000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-016",
            vendor_id="VEND-006",
            amount=20000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-017",
            vendor_id="VEND-017",
            amount=45000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-018",
            vendor_id="VEND-008",
            amount=50000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-019",
            vendor_id="VEND-003",
            amount=49000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
"""
text = text.replace('    db.add_all(purchase_orders)', pos + '    db.add_all(purchase_orders)')

grns = """        GoodsReceipt(
            grn_id="GRN-2026-011",
            po_id="PO-2026-011",
            vendor_id="VEND-001",
            amount=55000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-012",
            po_id="PO-2026-012",
            vendor_id="VEND-002",
            amount=210000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-013",
            po_id="PO-2026-013",
            vendor_id="VEND-013",
            amount=22000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-014",
            po_id="PO-2026-014",
            vendor_id="VEND-004",
            amount=33000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-015",
            po_id="PO-2026-015",
            vendor_id="VEND-005",
            amount=50000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-016",
            po_id="PO-2026-016",
            vendor_id="VEND-006",
            amount=10000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-017",
            po_id="PO-2026-017",
            vendor_id="VEND-017",
            amount=45000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-018",
            po_id="PO-2026-018",
            vendor_id="VEND-008",
            amount=50000.0,
            date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-019",
            po_id="PO-2026-019",
            vendor_id="VEND-003",
            amount=49000.0,
            date=now - timedelta(days=5),
        ),
"""
text = text.replace('    db.add_all(goods_receipts)', grns + '    db.add_all(goods_receipts)')


hist_payments = """        *[
            PaymentRequest(
                request_id=f"REQ-HIST-008-{i}",
                invoice_id=f"INV-HIST-008-{i}",
                vendor_id="VEND-008",
                amount=50000.0,
                currency="INR",
                status="PAID",
                created_at=now - timedelta(hours=i),
                risk_score=5,
                routing_tier="AUTO_APPROVE"
            )
            for i in range(1, 10)
        ],
        PaymentRequest(
            request_id="REQ-HIST-003-1",
            invoice_id="INV-HIST-003-1",
            vendor_id="VEND-003",
            amount=49000.0,
            currency="INR",
            status="PAID",
            created_at=now - timedelta(hours=2),
            risk_score=5,
            routing_tier="AUTO_APPROVE"
        ),
"""
text = text.replace('    db.add_all(payment_requests)', hist_payments + '    db.add_all(payment_requests)')


# Idempotency replacements
text = text.replace("    db.add(policy_v1)", """    if not db.query(PolicyVersion).filter_by(version=1).first():\n        db.add(policy_v1)""")

def patch_add_all(var_name, cls, key):
    return f"""    for item in {var_name}:
        if not db.query({cls}).filter_by({key}=getattr(item, "{key}")).first():
            db.add(item)
    db.flush()"""

text = text.replace("    db.add_all(approvers)", patch_add_all("approvers", "Approver", "approver_id"))
text = text.replace("    db.add_all(vendors)", patch_add_all("vendors", "Vendor", "vendor_id"))
text = text.replace("    db.add_all(purchase_orders)", patch_add_all("purchase_orders", "PurchaseOrder", "po_id"))
text = text.replace("    db.add_all(goods_receipts)", patch_add_all("goods_receipts", "GoodsReceipt", "grn_id"))
text = text.replace("    db.add_all(payment_requests)", patch_add_all("payment_requests", "PaymentRequest", "request_id"))

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Updated seed_service.py")
