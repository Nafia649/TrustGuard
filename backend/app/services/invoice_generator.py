import os
from typing import List, Dict, Any, Optional
import pymupdf as fitz

# Default destination directory for demo PDF fixtures at repository root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEMO_INVOICES_DIR = os.path.join(REPO_ROOT, "demo-invoices")

# Definition of the 10 synthetic demo invoices
DEMO_INVOICE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "invoice_id": "INV-DEMO-001",
        "vendor_id": "VEND-001",
        "vendor_name": "Acme Industrial Supplies",
        "address": "100 Industrial Parkway, Sector 4, Bangalore 560001",
        "gstin": "29ACMEIND1234F1Z5",
        "date": "2026-10-06",
        "due_date": "2026-11-05",
        "po_id": "PO-2026-001",
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "template": "corporate",
        "scenario": "Scenario A: Normal / Low Risk (Auto-Approve Target)",
        "line_items": [
            ("Precision Ball Bearings (Grade A)", 100, 400.0, 40000.0),
            ("High-Temp Industrial Lubricant Kit", 1, 5000.0, 5000.0),
        ],
        "subtotal": 45000.0,
        "tax": 0.0,
        "total": 45000.0,
    },
    {
        "invoice_id": "INV-DEMO-002",
        "vendor_id": "VEND-002",
        "vendor_name": "Global Logistics Corp",
        "address": "Terminal 3 Freight Wing, Cargo Complex, Mumbai 400099",
        "gstin": "27GLOBLOG5678E2Z1",
        "date": "2026-10-06",
        "due_date": "2026-10-20",
        "po_id": "PO-2026-002",
        "currency": "INR",
        "bank_account": "GLOB-BANK-002",
        "template": "minimal",
        "scenario": "Scenario B: Medium Risk (Single Signature Escalation > ₹50,000 cap)",
        "line_items": [
            ("Heavy Machinery Freight & Transit Escort", 1, 150000.0, 150000.0),
        ],
        "subtotal": 150000.0,
        "tax": 0.0,
        "total": 150000.0,
    },
    {
        "invoice_id": "INV-DEMO-003",
        "vendor_id": "VEND-003",
        "vendor_name": "Apex Cloud Services",
        "address": "Cyber Heights Tower B, Level 14, Hyderabad 500081",
        "gstin": "36APEXCLD9012D3Z9",
        "date": "2026-10-06",
        "due_date": "2026-11-06",
        "po_id": "PO-2026-003",
        "currency": "INR",
        "bank_account": "APEX-BANK-003",
        "template": "digital",
        "scenario": "Scenario A: Tamper Demo Baseline / Low Risk",
        "line_items": [
            ("Dedicated Kubernetes Enterprise Nodes", 5, 8000.0, 40000.0),
            ("Managed Cloud Storage Bucket Tier-1", 1, 10000.0, 10000.0),
        ],
        "subtotal": 50000.0,
        "tax": 0.0,
        "total": 50000.0,
    },
    {
        "invoice_id": "INV-DEMO-004",
        "vendor_id": "VEND-004",
        "vendor_name": "Meridian Office Systems",
        "address": "45 Park Avenue Business Park, Chennai 600028",
        "gstin": "33MERIOFF3456C4Z7",
        "date": "2026-10-06",
        "due_date": "2026-10-25",
        "po_id": "PO-2026-004",
        "currency": "INR",
        "bank_account": "MERI-BANK-004",
        "template": "corporate",
        "scenario": "Scenario A: Approved Vendor Office Equipment",
        "line_items": [
            ("Ergonomic Mesh Task Chairs", 4, 5000.0, 20000.0),
            ("Height Adjustable Workstation Converters", 3, 4000.0, 12000.0),
        ],
        "subtotal": 32000.0,
        "tax": 0.0,
        "total": 32000.0,
    },
    {
        "invoice_id": "INV-DEMO-005",
        "vendor_id": "VEND-005",
        "vendor_name": "Nova Industrial Parts",
        "address": "Phase II MIDC Industrial Area, Pune 411018",
        "gstin": "27NOVAPRT7890B5Z3",
        "date": "2026-10-06",
        "due_date": "2026-11-15",
        "po_id": "PO-2026-005",
        "currency": "INR",
        "bank_account": "NOVA-BANK-005",
        "template": "minimal",
        "scenario": "Scenario B: Medium Risk Heavy Spares (> ₹50,000 threshold)",
        "line_items": [
            ("Heavy-Duty Flange Assemblies", 20, 2400.0, 48000.0),
            ("Hydraulic Valve Seal Sets", 10, 2000.0, 20000.0),
        ],
        "subtotal": 68000.0,
        "tax": 0.0,
        "total": 68000.0,
    },
    {
        "invoice_id": "INV-DEMO-006",
        "vendor_id": "VEND-006",
        "vendor_name": "BluePeak Logistics",
        "address": "Ring Road Logistics Hub, Plot 12, Ahmedabad 382443",
        "gstin": "24BLUELOG1122A6Z1",
        "date": "2026-10-06",
        "due_date": "2026-10-21",
        "po_id": "PO-2026-006",
        "currency": "INR",
        "bank_account": "BLUE-BANK-006",
        "template": "digital",
        "scenario": "Scenario A: Routine Inter-State Dispatch",
        "line_items": [
            ("Regional Express Pallet Shipment", 6, 3000.0, 18000.0),
        ],
        "subtotal": 18000.0,
        "tax": 0.0,
        "total": 18000.0,
    },
    {
        "invoice_id": "INV-DEMO-007",
        "vendor_id": "VEND-007",
        "vendor_name": "Vertex IT Solutions",
        "address": "Electronic City Tech Zone, Gate 3, Gurgaon 122002",
        "gstin": "06VERTITS3344Z7Z8",
        "date": "2026-10-06",
        "due_date": "2026-11-10",
        "po_id": "PO-2026-007",
        "currency": "INR",
        "bank_account": "DIFF-BANK-VERT-999",  # Deliberate mismatch with VERT-BANK-007
        "template": "corporate",
        "scenario": "Scenario D: Bank Account Change (Flagged: bank_account_changed = 1)",
        "line_items": [
            ("Enterprise Infrastructure Security Audit", 1, 75000.0, 75000.0),
            ("Network Firewall Hardening Support", 1, 20000.0, 20000.0),
        ],
        "subtotal": 95000.0,
        "tax": 0.0,
        "total": 95000.0,
    },
    {
        "invoice_id": "INV-DEMO-008",
        "vendor_id": "VEND-008",
        "vendor_name": "GreenField Packaging",
        "address": "Eco Green Industrial Corridor, Surat 395006",
        "gstin": "24GRENPAK5566Y8Z5",
        "date": "2026-10-06",
        "due_date": "2026-10-31",
        "po_id": "PO-2026-008",  # Linked PO is 50,000; invoice is 75,000 (50% mismatch)
        "currency": "INR",
        "bank_account": "GREN-BANK-008",
        "template": "minimal",
        "scenario": "Scenario E: Invoice Amount vs PO Mismatch (PO ₹50,000 vs Invoice ₹75,000)",
        "line_items": [
            ("Biodegradable Heavy Packaging Enclosures", 2500, 30.0, 75000.0),
        ],
        "subtotal": 75000.0,
        "tax": 0.0,
        "total": 75000.0,
    },
    {
        "invoice_id": "INV-DEMO-009",
        "vendor_id": "VEND-009",
        "vendor_name": "Orion Manufacturing",
        "address": "Industrial Foundry Sector 8, Faridabad 121001",
        "gstin": "06ORINMAN7788X9Z2",
        "date": "2026-10-06",
        "due_date": "2026-11-20",
        "po_id": "PO-2026-009",
        "currency": "INR",
        "bank_account": "ORIN-BANK-009",
        "template": "digital",
        "scenario": "Scenario A: Low Risk Custom Machine Components",
        "line_items": [
            ("Custom CNC Machined Steel Mounts", 7, 6000.0, 42000.0),
        ],
        "subtotal": 42000.0,
        "tax": 0.0,
        "total": 42000.0,
    },
    {
        "invoice_id": "INV-DEMO-010",
        "vendor_id": "VEND-010",
        "vendor_name": "Shadow Shell Enterprises",
        "address": "Offshore Virtual Business Suite 99, Port Vila",
        "gstin": "99SHADOW9999Z0Z0",
        "date": "2026-10-06",
        "due_date": "2026-10-07",
        "po_id": None,  # No PO
        "currency": "INR",
        "bank_account": "SHAD-BANK-010",
        "template": "corporate",
        "scenario": "Scenario C: Unapproved Shadow Vendor (approved = False, No PO, ₹500,000 Hold)",
        "line_items": [
            ("Urgent Strategic Advisory Fee (Unspecified Scope)", 1, 500000.0, 500000.0),
        ],
        "subtotal": 500000.0,
        "tax": 0.0,
        "total": 500000.0,
    },
]


def render_corporate_template(doc: fitz.Document, inv: Dict[str, Any]) -> None:
    """Renders Template 1: Corporate Clean with top branding header and structured grid."""
    page = doc.new_page()

    # Header Bar
    page.draw_rect(fitz.Rect(36, 36, 576, 95), color=(0.08, 0.22, 0.38), fill=(0.08, 0.22, 0.38))
    page.insert_text((50, 65), inv["vendor_name"], fontsize=15, color=(1, 1, 1))
    page.insert_text((50, 82), f"Vendor ID: {inv['vendor_id']}  |  GSTIN: {inv['gstin']}", fontsize=9, color=(0.85, 0.9, 0.95))

    # Meta Section: Left Vendor Address, Right Invoice Facts
    page.insert_text((50, 115), "ISSUED BY:", fontsize=9, color=(0.4, 0.4, 0.4))
    page.insert_text((50, 128), inv["vendor_name"], fontsize=10, color=(0.1, 0.1, 0.1))
    page.insert_text((50, 140), inv["address"], fontsize=8, color=(0.3, 0.3, 0.3))

    page.insert_text((350, 115), "INVOICE DETAILS:", fontsize=9, color=(0.4, 0.4, 0.4))
    page.insert_text((350, 128), f"Invoice Number: {inv['invoice_id']}", fontsize=10, color=(0.1, 0.1, 0.1))
    page.insert_text((350, 141), f"Invoice Date: {inv['date']}", fontsize=9, color=(0.2, 0.2, 0.2))
    page.insert_text((350, 154), f"Due Date: {inv['due_date']}", fontsize=9, color=(0.2, 0.2, 0.2))
    po_str = f"Purchase Order: {inv['po_id']}" if inv["po_id"] else "Purchase Order: None (N/A)"
    page.insert_text((350, 167), po_str, fontsize=9, color=(0.2, 0.2, 0.2))

    # Bill To Box
    page.draw_rect(fitz.Rect(36, 185, 576, 218), color=(0.92, 0.94, 0.96), fill=(0.92, 0.94, 0.96))
    page.insert_text((50, 204), "Bill To: Acme Ltd Accounts Department, Corporate HQ", fontsize=9, color=(0.2, 0.2, 0.2))

    # Line Items Table Header
    y_start = 240
    page.draw_rect(fitz.Rect(36, y_start, 576, y_start + 20), color=(0.08, 0.22, 0.38), fill=(0.08, 0.22, 0.38))
    page.insert_text((45, y_start + 14), "Description", fontsize=9, color=(1, 1, 1))
    page.insert_text((320, y_start + 14), "Qty", fontsize=9, color=(1, 1, 1))
    page.insert_text((390, y_start + 14), "Unit Price", fontsize=9, color=(1, 1, 1))
    page.insert_text((480, y_start + 14), "Total Price", fontsize=9, color=(1, 1, 1))

    y = y_start + 35
    for desc, qty, rate, amount in inv["line_items"]:
        # Line text formatted so parser captures desc, qty, rate, amount cleanly
        line_str = f"{desc}  {qty}  {rate:.2f}  {amount:.2f}"
        page.insert_text((45, y), line_str, fontsize=9, color=(0.1, 0.1, 0.1))
        page.draw_line((36, y + 6), (576, y + 6), color=(0.85, 0.85, 0.85), width=0.5)
        y += 24

    # Summary Section
    y_sum = max(y + 20, 380)
    page.draw_rect(fitz.Rect(320, y_sum, 576, y_sum + 75), color=(0.95, 0.97, 0.99), fill=(0.95, 0.97, 0.99))
    page.insert_text((335, y_sum + 20), f"Subtotal: {inv['currency']} {inv['subtotal']:,.2f}", fontsize=9, color=(0.3, 0.3, 0.3))
    page.insert_text((335, y_sum + 36), f"Tax: {inv['currency']} {inv['tax']:,.2f}", fontsize=9, color=(0.3, 0.3, 0.3))
    page.insert_text((335, y_sum + 58), f"Grand Total: ₹ {inv['total']:,.2f}", fontsize=11, color=(0.05, 0.2, 0.4))

    # Remittance / Bank Account Details
    y_bank = y_sum + 95
    page.draw_rect(fitz.Rect(36, y_bank, 576, y_bank + 45), color=(0.9, 0.9, 0.9), width=0.5)
    page.insert_text((50, y_bank + 18), "PAYMENT REMITTANCE INSTRUCTIONS:", fontsize=8, color=(0.4, 0.4, 0.4))
    page.insert_text((50, y_bank + 33), f"Bank Account: {inv['bank_account']}    Currency: {inv['currency']}", fontsize=9, color=(0.1, 0.1, 0.1))

    # Footer Notice
    page.insert_text((50, 780), f"Demo Fixture: {inv['scenario']} (Synthetic Data Only)", fontsize=7, color=(0.6, 0.6, 0.6))


def render_minimal_template(doc: fitz.Document, inv: Dict[str, Any]) -> None:
    """Renders Template 2: Minimalist Professional with classical rule dividers."""
    page = doc.new_page()

    # Vendor Header on Left, INVOICE on Right
    page.insert_text((45, 60), inv["vendor_name"].upper(), fontsize=14, color=(0.1, 0.1, 0.1))
    page.insert_text((45, 75), f"Vendor ID: {inv['vendor_id']}", fontsize=9, color=(0.4, 0.4, 0.4))
    page.insert_text((45, 87), inv["address"], fontsize=8, color=(0.5, 0.5, 0.5))

    page.insert_text((440, 60), "TAX INVOICE", fontsize=16, color=(0.2, 0.2, 0.2))
    page.insert_text((440, 76), f"Invoice #: {inv['invoice_id']}", fontsize=10, color=(0.1, 0.1, 0.1))
    page.insert_text((440, 90), f"Date: {inv['date']}", fontsize=9, color=(0.3, 0.3, 0.3))

    page.draw_line((45, 105), (565, 105), color=(0.2, 0.2, 0.2), width=1.5)

    # Reference row
    po_str = f"Purchase Order: {inv['po_id']}" if inv["po_id"] else "PO: N/A"
    page.insert_text((45, 125), f"Billed To: Acme Ltd  |  {po_str}  |  GSTIN: {inv['gstin']}", fontsize=9, color=(0.2, 0.2, 0.2))
    page.draw_line((45, 135), (565, 135), color=(0.8, 0.8, 0.8), width=0.5)

    # Items Header
    y = 160
    page.insert_text((45, y), "Item & Specification", fontsize=9, color=(0.4, 0.4, 0.4))
    page.insert_text((320, y), "Quantity", fontsize=9, color=(0.4, 0.4, 0.4))
    page.insert_text((400, y), "Rate", fontsize=9, color=(0.4, 0.4, 0.4))
    page.insert_text((490, y), "Amount", fontsize=9, color=(0.4, 0.4, 0.4))
    page.draw_line((45, y + 6), (565, y + 6), color=(0.3, 0.3, 0.3), width=0.75)

    y += 26
    for desc, qty, rate, amount in inv["line_items"]:
        line_str = f"{desc}  {qty}  {rate:.2f}  {amount:.2f}"
        page.insert_text((45, y), line_str, fontsize=9, color=(0.1, 0.1, 0.1))
        page.draw_line((45, y + 6), (565, y + 6), color=(0.9, 0.9, 0.9), width=0.5)
        y += 24

    # Total Box
    y_tot = max(y + 30, 360)
    page.draw_line((350, y_tot), (565, y_tot), color=(0.4, 0.4, 0.4), width=1.0)
    page.insert_text((360, y_tot + 18), f"Subtotal: {inv['subtotal']:,.2f}", fontsize=9, color=(0.3, 0.3, 0.3))
    page.insert_text((360, y_tot + 32), f"Tax: {inv['tax']:,.2f}", fontsize=9, color=(0.3, 0.3, 0.3))
    page.draw_line((350, y_tot + 38), (565, y_tot + 38), color=(0.4, 0.4, 0.4), width=1.0)
    page.insert_text((360, y_tot + 55), f"Grand Total: ₹ {inv['total']:,.2f}", fontsize=11, color=(0.0, 0.0, 0.0))
    page.draw_line((350, y_tot + 62), (565, y_tot + 62), color=(0.4, 0.4, 0.4), width=1.0)

    # Bank Info
    y_b = y_tot + 85
    page.insert_text((45, y_b), "DIRECT DEPOSIT INFORMATION:", fontsize=8, color=(0.4, 0.4, 0.4))
    page.insert_text((45, y_b + 14), f"Bank Account: {inv['bank_account']}", fontsize=9, color=(0.1, 0.1, 0.1))
    page.insert_text((45, y_b + 28), f"Currency: {inv['currency']}  |  Due Date: {inv['due_date']}", fontsize=8, color=(0.3, 0.3, 0.3))

    page.insert_text((45, 780), f"Demo Fixture: {inv['scenario']} (Synthetic Data Only)", fontsize=7, color=(0.6, 0.6, 0.6))


def render_digital_template(doc: fitz.Document, inv: Dict[str, Any]) -> None:
    """Renders Template 3: Modern Tech / Digital layout with dark accents and structured metadata."""
    page = doc.new_page()

    # Dark Upper Header
    page.draw_rect(fitz.Rect(30, 30, 582, 85), color=(0.12, 0.15, 0.22), fill=(0.12, 0.15, 0.22))
    page.insert_text((45, 58), inv["vendor_name"], fontsize=15, color=(0.95, 0.96, 0.98))
    page.insert_text((45, 74), f"Cloud & IT Services  |  Vendor ID: {inv['vendor_id']}", fontsize=8, color=(0.7, 0.75, 0.85))

    page.insert_text((440, 58), "INVOICE", fontsize=15, color=(0.3, 0.75, 0.95))
    page.insert_text((440, 74), inv["invoice_id"], fontsize=9, color=(0.85, 0.9, 0.95))

    # Meta Grid Box
    page.draw_rect(fitz.Rect(30, 95, 582, 165), color=(0.95, 0.96, 0.98), fill=(0.95, 0.96, 0.98))
    page.insert_text((45, 115), f"Invoice Number: {inv['invoice_id']}", fontsize=9, color=(0.15, 0.2, 0.25))
    page.insert_text((45, 130), f"Invoice Date: {inv['date']}", fontsize=9, color=(0.25, 0.3, 0.35))
    page.insert_text((45, 145), f"Due Date: {inv['due_date']}", fontsize=9, color=(0.25, 0.3, 0.35))

    po_str = f"Purchase Order: {inv['po_id']}" if inv["po_id"] else "PO: N/A"
    page.insert_text((320, 115), po_str, fontsize=9, color=(0.15, 0.2, 0.25))
    page.insert_text((320, 130), f"Vendor ID: {inv['vendor_id']}", fontsize=9, color=(0.25, 0.3, 0.35))
    page.insert_text((320, 145), f"Bank Account: {inv['bank_account']}", fontsize=9, color=(0.15, 0.2, 0.25))

    # Service Table Header
    y = 190
    page.draw_rect(fitz.Rect(30, y, 582, y + 20), color=(0.22, 0.26, 0.35), fill=(0.22, 0.26, 0.35))
    page.insert_text((45, y + 14), "Service Description", fontsize=9, color=(1, 1, 1))
    page.insert_text((320, y + 14), "Qty", fontsize=9, color=(1, 1, 1))
    page.insert_text((400, y + 14), "Unit Rate", fontsize=9, color=(1, 1, 1))
    page.insert_text((490, y + 14), "Total Price", fontsize=9, color=(1, 1, 1))

    y += 34
    for desc, qty, rate, amount in inv["line_items"]:
        line_str = f"{desc}  {qty}  {rate:.2f}  {amount:.2f}"
        page.insert_text((45, y), line_str, fontsize=9, color=(0.15, 0.2, 0.25))
        page.draw_line((30, y + 6), (582, y + 6), color=(0.88, 0.9, 0.92), width=0.5)
        y += 24

    # Bottom Payment & Total Cards
    y_bot = max(y + 20, 370)
    page.draw_rect(fitz.Rect(30, y_bot, 280, y_bot + 70), color=(0.95, 0.96, 0.98), fill=(0.95, 0.96, 0.98))
    page.insert_text((45, y_bot + 20), "REMITTANCE ACCOUNT:", fontsize=8, color=(0.4, 0.45, 0.5))
    page.insert_text((45, y_bot + 36), f"Bank Account: {inv['bank_account']}", fontsize=9, color=(0.15, 0.2, 0.25))
    page.insert_text((45, y_bot + 52), f"Currency: {inv['currency']} (Electronic Transfer)", fontsize=8, color=(0.3, 0.35, 0.4))

    page.draw_rect(fitz.Rect(320, y_bot, 582, y_bot + 70), color=(0.12, 0.15, 0.22), fill=(0.12, 0.15, 0.22))
    page.insert_text((340, y_bot + 22), f"Subtotal: {inv['subtotal']:,.2f}", fontsize=9, color=(0.7, 0.75, 0.85))
    page.insert_text((340, y_bot + 38), f"Tax: {inv['tax']:,.2f}", fontsize=9, color=(0.7, 0.75, 0.85))
    page.insert_text((340, y_bot + 58), f"Grand Total: ₹ {inv['total']:,.2f}", fontsize=11, color=(1, 1, 1))

    page.insert_text((45, 780), f"Demo Fixture: {inv['scenario']} (Synthetic Data Only)", fontsize=7, color=(0.6, 0.6, 0.6))


def generate_single_invoice_pdf(inv: Dict[str, Any], output_path: str) -> str:
    """Generates a single synthetic invoice PDF according to its template."""
    doc = fitz.open()

    tpl = inv.get("template", "corporate")
    if tpl == "minimal":
        render_minimal_template(doc, inv)
    elif tpl == "digital":
        render_digital_template(doc, inv)
    else:
        render_corporate_template(doc, inv)

    doc.save(output_path)
    doc.close()
    return output_path


def generate_all_demo_invoices(target_dir: Optional[str] = None) -> List[str]:
    """
    Generates all 10 synthetic invoice PDF fixtures into target_dir (defaults to demo-invoices/).
    Returns list of generated file paths. Idempotent and safe to run repeatedly.
    """
    output_dir = target_dir or DEMO_INVOICES_DIR
    os.makedirs(output_dir, exist_ok=True)

    generated_paths: List[str] = []
    for inv in DEMO_INVOICE_DEFINITIONS:
        filename = f"{inv['invoice_id']}.pdf"
        file_path = os.path.join(output_dir, filename)
        generate_single_invoice_pdf(inv, file_path)
        generated_paths.append(file_path)

    return generated_paths
