import re

path = r"C:\Users\USER\TrustGuard\backend\app\services\invoice_generator.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

new_invoices = """
    {
        "invoice_id": "INV-DEMO-011",
        "vendor_id": "VEND-001",
        "vendor_name": "Acme Industrial Supplies",
        "address": "100 Industrial Parkway, Sector 4, Bangalore 560001",
        "gstin": "29ACMEI1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-011",
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "scenario": "Clean Invoice",
        "template": "corporate",
        "line_items": [
            ("Industrial Bearings", 100, 500.0, 50000.0),
            ("Shipping", 1, 5000.0, 5000.0)
        ],
        "subtotal": 55000.0,
        "tax": 0.0,
        "total": 55000.0,
    },
    {
        "invoice_id": "INV-DEMO-012",
        "vendor_id": "VEND-002",
        "vendor_name": "Global Logistics Corp",
        "address": "450 Freight Ave, Mumbai",
        "gstin": "27GLOBL1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-012",
        "currency": "INR",
        "bank_account": "GLOB-BANK-002",
        "scenario": "Two Signatures Needed",
        "template": "minimal",
        "line_items": [
            ("Freight Forwarding Q3", 1, 210000.0, 210000.0)
        ],
        "subtotal": 210000.0,
        "tax": 0.0,
        "total": 210000.0,
    },
    {
        "invoice_id": "INV-DEMO-013",
        "vendor_id": "VEND-013",
        "vendor_name": "NewTech Startups",
        "address": "12 Tech Hub, Pune",
        "gstin": "27NEWTE1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-013",
        "currency": "INR",
        "bank_account": "NEW-BANK-013",
        "scenario": "New Vendor Alert",
        "template": "digital",
        "line_items": [
            ("Software License", 1, 22000.0, 22000.0)
        ],
        "subtotal": 22000.0,
        "tax": 0.0,
        "total": 22000.0,
    },
    {
        "invoice_id": "INV-DEMO-014",
        "vendor_id": "VEND-004",
        "vendor_name": "Rapid Print Solutions",
        "address": "12 Print Street, Delhi",
        "gstin": "07RAPID1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-014",
        "currency": "INR",
        "bank_account": "ALT-BANK-999",
        "scenario": "Bank Account Changed",
        "template": "corporate",
        "line_items": [
            ("Marketing Brochures", 1000, 33.0, 33000.0)
        ],
        "subtotal": 33000.0,
        "tax": 0.0,
        "total": 33000.0,
    },
    {
        "invoice_id": "INV-DEMO-015",
        "vendor_id": "VEND-005",
        "vendor_name": "Office Supplies Direct",
        "address": "55 Desk Ave, Hyderabad",
        "gstin": "36OFFIC1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-015",
        "currency": "INR",
        "bank_account": "OFFI-BANK-005",
        "scenario": "PO Mismatch",
        "template": "minimal",
        "line_items": [
            ("Ergonomic Chairs", 10, 8500.0, 85000.0)
        ],
        "subtotal": 85000.0,
        "tax": 0.0,
        "total": 85000.0,
    },
    {
        "invoice_id": "INV-DEMO-016",
        "vendor_id": "VEND-006",
        "vendor_name": "CleanSpace Co.",
        "address": "90 Hygiene Rd, Chennai",
        "gstin": "33CLEAN1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-016",
        "currency": "INR",
        "bank_account": "CLEN-BANK-006",
        "scenario": "GRN Mismatch",
        "template": "digital",
        "line_items": [
            ("Cleaning Services Q3", 1, 20000.0, 20000.0)
        ],
        "subtotal": 20000.0,
        "tax": 0.0,
        "total": 20000.0,
    },
    {
        "invoice_id": "INV-DEMO-017",
        "vendor_id": "VEND-017",
        "vendor_name": "Shady Supplies Ltd",
        "address": "Unknown PO Box, Kolkata",
        "gstin": "19SHADY1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-017",
        "currency": "INR",
        "bank_account": "SHAD-BANK-017",
        "scenario": "Unapproved Vendor",
        "template": "corporate",
        "line_items": [
            ("Consulting Services", 1, 45000.0, 45000.0)
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
    }
]
"""

if "INV-DEMO-011" not in text:
    text = re.sub(r'(\s*\}\,\n)(\])', r'\1' + new_invoices[1:], text, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("Patched invoice_generator.py")
