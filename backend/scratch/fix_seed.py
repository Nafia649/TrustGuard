import re

with open(r"C:\Users\USER\TrustGuard\backend\app\services\seed_service.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix created_at -> timestamp
text = text.replace("created_at=now", "timestamp=now")

# Fix missing bank_account
text = text.replace('vendor_id="VEND-008",\n                amount=50000.0,', 'vendor_id="VEND-008",\n                amount=50000.0, bank_account="GREN-BANK-008",')
text = text.replace('vendor_id="VEND-003", amount=49000.0,', 'vendor_id="VEND-003", amount=49000.0, bank_account="APEX-BANK-003",')

with open(r"C:\Users\USER\TrustGuard\backend\app\services\seed_service.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed seed_service.py fields")
