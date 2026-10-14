
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import AUTO_CREATE_TABLES, CORS_ORIGINS
from app.core.logging import configure_logging, get_logger
from app.core import metrics
from app.api.products import router as products_router
from app.api.rates import router as rates_router
from app.db.base import Base
from app.db.session import engine, SessionLocal
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
from app.api.monitoring import router as monitoring_router
import app.models  # noqa: F401 - registers all ORM models

configure_logging()
logger = get_logger("hisabpro")
APP_STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Development convenience only. Production (HISABPRO_AUTO_CREATE_TABLES=false)
    # relies exclusively on Alembic migrations run before startup.
    if AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SNJ Gold Lab API",
    description="Gold and silver inventory management",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Basic hardening headers on every response."""
    response: Response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Browsers ignore this over plain HTTP; it takes effect once HTTPS
    # is terminated in front of the app (Phase 15).
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """One structured line per request + in-process metrics."""
    started = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    path = request.url.path
    metrics.record_request(request.method, path, response.status_code, duration_ms)
    # /health is polled constantly; keep it out of the normal log.
    log = logger.debug if path == "/health" else logger.info
    log(
        "request method=%s path=%s status=%s duration_ms=%.1f auth=%s",
        request.method,
        path,
        response.status_code,
        duration_ms,
        "token" if request.headers.get("authorization") else "-",
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log full tracebacks server-side; never leak internals to clients."""
    logger.exception(
        "unhandled error method=%s path=%s error=%s",
        request.method,
        request.url.path,
        exc.__class__.__name__,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
app.include_router(monitoring_router)


@app.get("/health")
def health_check() -> Response:
    """Liveness + database reachability, used by humans and scripts."""
    uptime = round(time.time() - APP_STARTED_AT, 1)
    db_status = "ok"
    db_latency_ms = 0.0
    status_code = 200
    try:
        db_started = time.perf_counter()
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - db_started) * 1000, 1)
    except Exception:
        logger.exception("health check: database unreachable")
        db_status = "unreachable"
        status_code = 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_status == "ok" else "degraded",
            "application": "SNJ Gold Lab",
            "version": "1.0.0",
            "uptime_seconds": uptime,
            "database": {"status": db_status, "latency_ms": db_latency_ms},
        },
    )
