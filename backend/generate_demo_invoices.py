#!/usr/bin/env python3
"""
CLI utility to generate all 10 synthetic TrustGuard demo invoice PDFs in demo-invoices/.
Run with:
    python backend/generate_demo_invoices.py
"""
import sys
import os

# Ensure backend directory is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.services.invoice_generator import generate_all_demo_invoices, DEMO_INVOICES_DIR


def main():
    print(f"Generating 10 synthetic invoice PDF fixtures into: {DEMO_INVOICES_DIR}")
    paths = generate_all_demo_invoices()
    print(f"Successfully generated {len(paths)} demo invoice PDFs:")
    for p in paths:
        rel = os.path.relpath(p, os.path.dirname(BASE_DIR))
        size_kb = os.path.getsize(p) / 1024
        print(f"  - {rel} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
