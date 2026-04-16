import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password
from datetime import date

def create_admin():
    db = SessionLocal()

    email = "ssrkesavareddy@gmail.com"
    raw_password = "kesava12345"
    phone = "+919182292033"

    existing = db.query(User).filter(User.email == email).first()

    if existing:
        print("❌ Admin already exists")
        return

    admin = User(
        email=email,
        password=hash_password(raw_password),
        phone=phone,
        role="admin",
        is_verified=True,
        is_blocked=False,
        account_balance=0,
        dob=date(2002, 8, 25)   # ✅ optional but clean
    )

    db.add(admin)
    db.commit()

    print("✅ Admin created successfully")
    print(f"Email: {email}")
    print(f"Password: {raw_password}")

if __name__ == "__main__":
    create_admin()