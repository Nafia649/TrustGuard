import re

# 1. Update invoice_generator.py
generator_path = r"C:\Users\USER\TrustGuard\backend\app\services\invoice_generator.py"
with open(generator_path, "r", encoding="utf-8") as f:
    content = f.read()

new_invoices = """    {
        "invoice_id": "INV-DEMO-011",
        "vendor_id": "VEND-001",
        "vendor_name": "Acme Industrial Supplies",
        "address": "100 Industrial Parkway, Sector 4, Bangalore",
        "gstin": "29ABCDE1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-011",
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "scenario": "Clean Legitimate",
        "template": "corporate",
        "line_items": [
            ("Industrial Widgets Type A", 50, 1000.0, 50000.0)
        ],
        "subtotal": 50000.0,
        "tax": 5000.0,
        "total": 55000.0,
    },
    {
        "invoice_id": "INV-DEMO-012",
        "vendor_id": "VEND-002",
        "vendor_name": "Global Logistics Corp",
        "address": "200 Trade Center, Mumbai",
        "gstin": "27XYZDE1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-012",
        "currency": "INR",
        "bank_account": "GLOB-BANK-002",
        "scenario": "Clean Legitimate High Value",
        "template": "digital",
        "line_items": [
            ("Global Freight Services Q3", 1, 200000.0, 200000.0)
        ],
        "subtotal": 200000.0,
        "tax": 10000.0,
        "total": 210000.0,
    },
    {
        "invoice_id": "INV-DEMO-013",
        "vendor_id": "VEND-013",
        "vendor_name": "NewTech Startups",
        "address": "300 Tech Park, Pune",
        "gstin": "27NEWTE1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-013",
        "currency": "INR",
        "bank_account": "NEW-BANK-013",
        "scenario": "New Vendor",
        "template": "minimal",
        "line_items": [
            ("Software Licenses", 10, 2000.0, 20000.0)
        ],
        "subtotal": 20000.0,
        "tax": 2000.0,
        "total": 22000.0,
    },
    {
        "invoice_id": "INV-DEMO-014",
        "vendor_id": "VEND-004",
        "vendor_name": "Meridian Office Systems",
        "address": "400 Office Block, Delhi",
        "gstin": "07MERID1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-014",
        "currency": "INR",
        "bank_account": "FRAUD-BANK-999",
        "scenario": "Bank Account Change",
        "template": "corporate",
        "line_items": [
            ("Office Chairs", 10, 3000.0, 30000.0)
        ],
        "subtotal": 30000.0,
        "tax": 3000.0,
        "total": 33000.0,
    },
    {
        "invoice_id": "INV-DEMO-015",
        "vendor_id": "VEND-005",
        "vendor_name": "Nova Industrial Parts",
        "address": "500 Nova Hub, Chennai",
        "gstin": "33NOVAX1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-015",
        "currency": "INR",
        "bank_account": "NOVA-BANK-005",
        "scenario": "PO Mismatch",
        "template": "digital",
        "line_items": [
            ("Industrial Part X", 20, 4000.0, 80000.0)
        ],
        "subtotal": 80000.0,
        "tax": 5000.0,
        "total": 85000.0,
    },
    {
        "invoice_id": "INV-DEMO-016",
        "vendor_id": "VEND-006",
        "vendor_name": "BluePeak Logistics",
        "address": "600 Peak Road, Hyderabad",
        "gstin": "36BLUEP1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-016",
        "currency": "INR",
        "bank_account": "BLUE-BANK-006",
        "scenario": "GRN Mismatch",
        "template": "minimal",
        "line_items": [
            ("Logistics Delivery Run", 5, 4000.0, 20000.0)
        ],
        "subtotal": 20000.0,
        "tax": 0.0,
        "total": 20000.0,
    },
    {
        "invoice_id": "INV-DEMO-017",
        "vendor_id": "VEND-017",
        "vendor_name": "Shady Supplies Ltd",
        "address": "700 Back Alley, Nowhere",
        "gstin": "99SHADY1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-017",
        "currency": "INR",
        "bank_account": "SHAD-BANK-017",
        "scenario": "Unapproved Vendor",
        "template": "corporate",
        "line_items": [
            ("Consulting Fees", 1, 45000.0, 45000.0)
        ],
        "subtotal": 45000.0,
        "tax": 0.0,
        "total": 45000.0,
    },
    {
        "invoice_id": "INV-DEMO-018",
        "vendor_id": "VEND-008",
        "vendor_name": "GreenField Packaging",
        "address": "800 Green Park, Noida",
        "gstin": "09GREEN1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-018",
        "currency": "INR",
        "bank_account": "GREN-BANK-008",
        "scenario": "Velocity Alert",
        "template": "digital",
        "line_items": [
            ("Packaging Materials", 100, 500.0, 50000.0)
        ],
        "subtotal": 50000.0,
        "tax": 0.0,
        "total": 50000.0,
    },
    {
        "invoice_id": "INV-DEMO-019",
        "vendor_id": "VEND-003",
        "vendor_name": "Apex Cloud Services",
        "address": "300 Cloud Way, Bangalore",
        "gstin": "29APEXX1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-019",
        "currency": "INR",
        "bank_account": "APEX-BANK-003",
        "scenario": "Split Payment Pattern",
        "template": "minimal",
        "line_items": [
            ("Cloud Subscription Part 1", 1, 49000.0, 49000.0)
        ],
        "subtotal": 49000.0,
        "tax": 0.0,
        "total": 49000.0,
    },
    {
        "invoice_id": "INV-DEMO-020",
        "vendor_id": "VEND-020",
        "vendor_name": "Ghost Entity Corp",
        "address": "999 Unknown Street, Void",
        "gstin": "99GHOST1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "",
        "currency": "INR",
        "bank_account": "GHST-BANK-999",
        "scenario": "High Risk Fraud",
        "template": "corporate",
        "line_items": [
            ("Marketing Strategy", 1, 99000.0, 99000.0)
        ],
        "subtotal": 99000.0,
        "tax": 0.0,
        "total": 99000.0,
    },
]
"""
if "INV-DEMO-011" not in content:
    content = re.sub(r'(\s*\}\,\n)(\])(\n\s*\"\"\")', r'\1' + new_invoices + r'\3', content)
    with open(generator_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Invoices added to generator.")

# 2. Update seed_service.py
seed_path = r"C:\Users\USER\TrustGuard\backend\app\services\seed_service.py"
with open(seed_path, "r", encoding="utf-8") as f:
    seed_content = f.read()

new_vendors = """        Vendor(
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
"""
if "VEND-013" not in seed_content:
    seed_content = seed_content.replace('    for item in vendors:', new_vendors + '    for item in vendors:')
    print("Vendors added.")

new_pos = """        PurchaseOrder(
            po_id="PO-2026-011", vendor_id="VEND-001", amount=55000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-012", vendor_id="VEND-002", amount=210000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-013", vendor_id="VEND-013", amount=22000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-014", vendor_id="VEND-004", amount=33000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        # PO Mismatch scenario (PO is 50k, Invoice is 85k)
        PurchaseOrder(
            po_id="PO-2026-015", vendor_id="VEND-005", amount=50000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-016", vendor_id="VEND-006", amount=20000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-017", vendor_id="VEND-017", amount=45000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-018", vendor_id="VEND-008", amount=50000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-019", vendor_id="VEND-003", amount=49000.0, status="APPROVED", date=now - timedelta(days=10),
        ),
"""
if "PO-2026-011" not in seed_content:
    seed_content = seed_content.replace('    for item in purchase_orders:', new_pos + '    for item in purchase_orders:')
    print("POs added.")

new_grns = """        GoodsReceipt(
            grn_id="GRN-2026-011", po_id="PO-2026-011", vendor_id="VEND-001", amount=55000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-012", po_id="PO-2026-012", vendor_id="VEND-002", amount=210000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-013", po_id="PO-2026-013", vendor_id="VEND-013", amount=22000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-014", po_id="PO-2026-014", vendor_id="VEND-004", amount=33000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-015", po_id="PO-2026-015", vendor_id="VEND-005", amount=50000.0, date=now - timedelta(days=5),
        ),
        # GRN Mismatch scenario (GRN is 10k, Invoice is 20k)
        GoodsReceipt(
            grn_id="GRN-2026-016", po_id="PO-2026-016", vendor_id="VEND-006", amount=10000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-017", po_id="PO-2026-017", vendor_id="VEND-017", amount=45000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-018", po_id="PO-2026-018", vendor_id="VEND-008", amount=50000.0, date=now - timedelta(days=5),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-019", po_id="PO-2026-019", vendor_id="VEND-003", amount=49000.0, date=now - timedelta(days=5),
        ),
"""
if "GRN-2026-011" not in seed_content:
    seed_content = seed_content.replace('    for item in goods_receipts:', new_grns + '    for item in goods_receipts:')
    print("GRNs added.")

# Add historical velocity for VEND-008 to create a natural velocity flag without overwriting other records.
new_payment_requests = """        # Generate realistic history for Velocity Alert (VEND-008)
        *[
            PaymentRequest(
                request_id=f"REQ-HIST-008-{i}", invoice_id=f"INV-HIST-008-{i}", vendor_id="VEND-008",
                amount=50000.0, currency="INR", status="PAID",
                created_at=now - timedelta(hours=i), risk_score=5, routing_tier="AUTO_APPROVE"
            )
            for i in range(1, 10)
        ],
        # Generate realistic history for Split Payment (VEND-003)
        PaymentRequest(
            request_id="REQ-HIST-003-1", invoice_id="INV-HIST-003-1", vendor_id="VEND-003",
            amount=49000.0, currency="INR", status="PAID",
            created_at=now - timedelta(hours=2), risk_score=5, routing_tier="AUTO_APPROVE"
        ),
"""
if "REQ-HIST-008-1" not in seed_content:
    seed_content = seed_content.replace('    for item in payment_requests:', new_payment_requests + '    for item in payment_requests:')
    print("Payment history added.")


with open(seed_path, "w", encoding="utf-8") as f:
    f.write(seed_content)

print("seed_service.py successfully updated with new fixtures.")
