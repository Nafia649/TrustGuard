import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.services.invoice_generator import generate_single_invoice_pdf, DEMO_INVOICES_DIR

final_invoices = [
    {
        "invoice_id": "INV-DEMO-021",
        "vendor_id": "VEND-009",
        "vendor_name": "Orion Manufacturing",
        "address": "Industrial Foundry Sector 8, Faridabad 121001",
        "gstin": "06ORINMAN7788X9Z2",
        "date": "2026-10-07",
        "due_date": "2026-11-20",
        "po_id": "PO-2026-009",
        "currency": "INR",
        "bank_account": "ORIN-BANK-009",
        "scenario": "Low Risk E2E Validation",
        "template": "corporate",
        "line_items": [
            ("Custom CNC Machined Steel Mounts", 7, 6000.0, 42000.0),
        ],
        "subtotal": 42000.0,
        "tax": 0.0,
        "total": 42000.0,
    },
    {
        "invoice_id": "INV-DEMO-022",
        "vendor_id": "VEND-002",
        "vendor_name": "Global Logistics Corp",
        "address": "450 Freight Ave, Mumbai",
        "gstin": "27GLOBL1234F1Z5",
        "date": "2026-10-07",
        "due_date": "2026-11-06",
        "po_id": "PO-2026-012",
        "currency": "INR",
        "bank_account": "GLOB-BANK-002",
        "scenario": "Medium Risk E2E Validation",
        "template": "minimal",
        "line_items": [
            ("Overweight Transport Route", 1, 150000.0, 150000.0),
            ("Expedited Surcharge", 1, 60000.0, 60000.0)
        ],
        "subtotal": 210000.0,
        "tax": 0.0,
        "total": 210000.0,
    },
    {
        "invoice_id": "INV-DEMO-023",
        "vendor_id": "VEND-020",
        "vendor_name": "Ghost Entity Corp",
        "address": "PO Box 9999, Unknown Location",
        "gstin": "99GHOST9999Z9Z9",
        "date": "2026-10-07",
        "due_date": "2026-10-08",
        "po_id": None,
        "currency": "INR",
        "bank_account": "GHST-BANK-999",
        "scenario": "High Risk E2E Validation",
        "template": "digital",
        "line_items": [
            ("Consulting Services Retainer", 1, 200000.0, 200000.0)
        ],
        "subtotal": 200000.0,
        "tax": 0.0,
        "total": 200000.0,
    }
]

def main():
    print(f"Generating 3 final synthetic invoice PDFs into: {DEMO_INVOICES_DIR}")
    for inv in final_invoices:
        filename = f"{inv['invoice_id']}.pdf"
        file_path = os.path.join(DEMO_INVOICES_DIR, filename)
        generate_single_invoice_pdf(inv, file_path)
        print(f"Generated {filename}")

if __name__ == "__main__":
    main()
