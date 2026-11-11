"""FastAPI app: agent webhook, WhatsApp webhook, staff APIs and the static pages."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import accounts, seed
from .api import auth, desk, errors, onboarding, public, setup, vapi, whatsapp
from .core import db
from .core.config import FRONTEND_DIR, env


@asynccontextmanager
async def lifespan(app: FastAPI):
    accounts.ensure_session_secret()
    conn = db.connect()
    demo = seed.ensure(conn)
    conn.close()
    conn = db.connect_unchecked()  # startup, before any request: the demo owner's login
    try:
        accounts.ensure_demo_login(conn, demo)
    finally:
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
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        allow_credentials=True,
    )
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(vapi.router)
app.include_router(public.router)
app.include_router(desk.pages)
app.include_router(desk.router)
app.include_router(whatsapp.router)
app.include_router(setup.pages)
app.include_router(setup.router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


errors.install(app)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
