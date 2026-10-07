import re

seed_service_path = r"C:\Users\USER\TrustGuard\backend\app\services\seed_service.py"
with open(seed_service_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove the clear block
delete_block = """    # Clear existing data in foreign-key dependency order
    db.query(LedgerEntry).delete()
    db.query(Signature).delete()
    db.query(AuditLog).delete()
    db.query(PaymentRequest).delete()
    db.query(GoodsReceipt).delete()
    db.query(PurchaseOrder).delete()
    db.query(Approver).delete()
    db.query(Vendor).delete()
    db.query(PolicyVersion).delete()
    db.commit()"""
content = content.replace(delete_block, "    # Removed destructive clear for idempotency")

# 2. Replace add_all with idempotent adds
def replace_add_all(model_name, var_name, match_field):
    old_str = f"    db.add_all({var_name})"
    new_str = f'''    for item in {var_name}:
        if not db.query({model_name}).filter_by({match_field}=getattr(item, "{match_field}")).first():
            db.add(item)
    db.flush()'''
    return old_str, new_str

replacements = [
    ("Approver", "approvers", "approver_id"),
    ("Vendor", "vendors", "vendor_id"),
    ("PurchaseOrder", "purchase_orders", "po_id"),
    ("GoodsReceipt", "goods_receipts", "grn_id"),
    ("PaymentRequest", "payment_requests", "request_id"),
]

for model, var, field in replacements:
    old_s, new_s = replace_add_all(model, var, field)
    content = content.replace(old_s, new_s)

# Also handle policy version
content = content.replace("    db.add(policy_v1)", """    if not db.query(PolicyVersion).filter_by(version=1).first():
        db.add(policy_v1)""")

with open(seed_service_path, "w", encoding="utf-8") as f:
    f.write(content)

print("seed_service.py patched for idempotency.")
