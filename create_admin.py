import sys
import os
from datetime import date
import uuid

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def create_admin():
    db = SessionLocal()

    try:
        email = "ssrkesavareddy@gmail.com".lower().strip()
        phone = "+919182292033".strip()

        raw_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")

        existing = db.query(User).filter(User.email == email).first()

        if existing:
            print("❌ Admin already exists")
            return

        admin = User(
            id=uuid.uuid4(),
            public_id=f"USR-{uuid.uuid4().hex[:8].upper()}",
            name="Kesava Reddy",
            email=email,
            password=hash_password(raw_password),
            phone=phone,
            role="ADMIN",
            is_verified=True,
            is_blocked=False,
            account_balance=0,
            dob=date(2002, 8, 25)
        )

        db.add(admin)
        db.commit()

        print("✅ Admin created successfully")
        print(f"Email: {email}")
        print(f"Password: {raw_password}")

    except Exception as e:
        db.rollback()
        print("❌ Error creating admin:", str(e))

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()