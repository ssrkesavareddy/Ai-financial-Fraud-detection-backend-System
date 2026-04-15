from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.users import router as user_router
from app.admin import router as admin_router
from app.database import Base, engine
from app.auth import router as auth_router
from app.fraud import router as fraud_router
from app.dashboard import router as dashboard_router  # ✅ FIXED IMPORT

# -------------------------
# CREATE TABLES
# -------------------------
from app.database import Base, engine
Base.metadata.create_all(bind=engine)

# -------------------------
# APP INIT
# -------------------------
app = FastAPI(
    title="Fraud Detection API",
    version="1.0"
)

# -------------------------
# ROUTERS
# -------------------------
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(fraud_router, prefix="/transactions", tags=["Transactions"])
app.include_router(dashboard_router, prefix="/analytics", tags=["Analytics"])
app.include_router(user_router)
app.include_router(admin_router)
# -------------------------
# HEALTH CHECK
# -------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# -------------------------
# CORS CONFIG (IMPORTANT)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)