from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
try:
    from app.api.routes import auth, signals, market, backtest, admin
except Exception as _import_err:
    import traceback, sys
    traceback.print_exc()
    sys.exit(f"FATAL: failed to import routes — {_import_err}")

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.db.database import engine, Base
        import app.models.user
        import app.models.signal
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Add new columns to existing databases (idempotent)
        from sqlalchemy import text
        migration_stmts = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token_expires TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_analyses INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_reset_date DATE",
            "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS magic_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS magic_token_expires TIMESTAMPTZ",
        ]
        async with engine.begin() as conn:
            for stmt in migration_stmts:
                try:
                    await conn.execute(text(stmt))
                except Exception:
                    pass  # SQLite doesn't support IF NOT EXISTS — ignore

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
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0", "modules": 12}


@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    log.error("unhandled", path=request.url.path, error=str(exc), traceback=tb)
    return JSONResponse(status_code=500, content={"detail": str(exc), "type": type(exc).__name__})
