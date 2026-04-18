from app.core.database import SessionLocal
from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog

db = SessionLocal()

db.query(Transaction).delete()
db.query(FraudLog).delete()

db.commit()
db.close()

print("All transactions cleared")