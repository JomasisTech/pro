from contextlib import asynccontextmanager, suppress
import logging
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.core.database import engine

settings = get_settings()
log = logging.getLogger(__name__)
_worker_stop: threading.Event | None = None
_worker_thread: threading.Thread | None = None
_brand_sync_thread: threading.Thread | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _worker_stop, _worker_thread, _brand_sync_thread
    if settings.demo_mode:
        from app.core.demo import prepare_demo_environment
        prepare_demo_environment()
    if settings.scheduler_worker_enabled:
        from app.modules.posting.worker import run_worker
        _worker_stop = threading.Event()
        _worker_thread = threading.Thread(target=run_worker, args=(_worker_stop,),
                                          name="scheduled-post-worker", daemon=True)
        _worker_thread.start()
        from app.modules.brand_intelligence.worker import run_worker as run_brand_sync_worker
        _brand_sync_thread = threading.Thread(
            target=run_brand_sync_worker, args=(_worker_stop, settings.scheduler_poll_interval_seconds),
            name="brand-intelligence-sync-worker", daemon=True,
        )
        _brand_sync_thread.start()
    try:
        yield
    finally:
        if _worker_stop is not None:
            _worker_stop.set()
        if _worker_thread is not None:
            _worker_thread.join(timeout=10)
        if _brand_sync_thread is not None:
            _brand_sync_thread.join(timeout=10)
        _worker_stop = None
        _worker_thread = None
        _brand_sync_thread = None


app = FastAPI(
    title=settings.app_name,
    version="0.2.7",
    description="BizPilot Pro business automation platform API.",
    lifespan=lifespan,
)

allowed_origins = [origin.strip().rstrip("/") for origin in settings.cors_origins.split(",") if origin.strip()]
if settings.demo_mode:
    # Demo only: no CORS_ORIGINS to configure. Safe here because the API uses bearer tokens, not cookies.
    allowed_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(v1_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Report that the application process is responding; no database required."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def readiness() -> dict[str, str]:
    """Check that the configured database is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Do not expose connection strings or raw database errors in the response.
        raise HTTPException(status_code=503, detail="Database unavailable") from None

    checks = {"database": "ok"}
    if settings.redis_url:
        try:
            from redis import Redis
            client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
        except Exception:
            # Redis backs shared abuse protection; do not expose credentials or provider errors.
            raise HTTPException(status_code=503, detail="Rate-limit store unavailable") from None
        finally:
            if "client" in locals():
                with suppress(Exception):
                    client.close()
        checks["redis"] = "ok"
    return {"status": "ready", **checks}
