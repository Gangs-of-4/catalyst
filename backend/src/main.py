"""FastAPI app: agent webhook, WhatsApp webhook, staff APIs and the static pages."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import seed
from .api import desk, public, setup, vapi, whatsapp
from .core import db
from .core.config import FRONTEND_DIR, env


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    seed.ensure(conn)
    conn.close()
    yield


app = FastAPI(title="Catalyst clinic demo", lifespan=lifespan)

# Frontend on Vercel calls the API cross-origin (ADR-0036). Empty = same-origin only.
cors_origins = [o.strip().rstrip("/") for o in env("CORS_ALLOWED_ORIGINS").split(",") if o.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
app.include_router(vapi.router)
app.include_router(public.router)
app.include_router(desk.router)
app.include_router(whatsapp.router)
app.include_router(setup.router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.exception_handler(RequestValidationError)
async def readable_422(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pages show `detail` as-is, so make it one plain sentence."""
    msgs = [str(e.get("msg", "")).removeprefix("Value error, ") for e in exc.errors()]
    return JSONResponse({"detail": " ".join(dict.fromkeys(msgs)) or "Invalid input."}, status_code=422)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
