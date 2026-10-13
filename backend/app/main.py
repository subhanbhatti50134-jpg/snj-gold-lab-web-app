
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.products import router as products_router
from app.api.rates import router as rates_router
from app.db.base import Base
from app.db.session import engine
from app.api.purchases import router as purchases_router
from app.api.sales import router as sales_router
from app.api.inventory import router as inventory_router
from app.api.transactions import router as transactions_router
from app.api.payments import router as payments_router
from app.api.movements import router as movements_router
from app.api.reports import router as reports_router
from app.api.cashflow import router as cashflow_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.parties import router as parties_router
from app.api.audit import router as audit_router
from app.api.settings import router as settings_router
from app.api.backup import router as backup_router
from app.api.dashboard import router as dashboard_router
import app.models  # noqa: F401 - registers all ORM models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Development convenience. Use Alembic migrations for production.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="HisabPro API",
    description="Gold and silver inventory management",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)
app.include_router(rates_router)
app.include_router(cashflow_router)
app.include_router(purchases_router)
app.include_router(sales_router)
app.include_router(inventory_router)
app.include_router(transactions_router)
app.include_router(payments_router)
app.include_router(movements_router)
app.include_router(reports_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(parties_router)
app.include_router(audit_router)
app.include_router(settings_router)
app.include_router(backup_router)
app.include_router(dashboard_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "application": "HisabPro"}
