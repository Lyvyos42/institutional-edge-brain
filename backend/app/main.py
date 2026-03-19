from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api.routes import auth, signals, market, backtest

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.db.database import engine, Base
        import app.models.user
        import app.models.signal
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("db_ready")
    except Exception as e:
        log.error("db_init_failed", error=str(e))
    yield
    log.info("shutdown")


app = FastAPI(title="Institutional Edge Brain API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(signals.router)
app.include_router(market.router)
app.include_router(backtest.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0", "modules": 12}


@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    log.error("unhandled", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
