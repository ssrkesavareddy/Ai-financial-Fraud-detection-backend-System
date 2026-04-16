from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fraud Detection API", version="1.0")

ALLOWED_ORIGINS = [
   "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import auth_router, transactions_router, analytics_router, users_router, admin_router
from app.api.admin import router as admin_router

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(analytics_router)
app.include_router(users_router)
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}