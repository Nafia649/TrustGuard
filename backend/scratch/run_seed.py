import sys
import os
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.services.seed_service import seed_database
from app.services.audit_service import verify_chain
import json

db = SessionLocal()
print("Seeding database...")
res = seed_database(db)
print("Seed finished.")

print("\nVerifying audit chain...")
v = verify_chain(db)
print(json.dumps(v, indent=2))
