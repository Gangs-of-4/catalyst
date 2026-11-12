"""FastAPI app: agent webhook, WhatsApp webhook, staff APIs and the static pages."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import accounts, seed
from .api import (
    admin,
    auth,
    desk,
    errors,
    feedback,
    onboarding,
    orders,
    public,
    setup,
    try_page,
    vapi,
    whatsapp,
)
from .core import db, tenancy
from .core.config import FRONTEND_DIR, env


@asynccontextmanager
async def lifespan(app: FastAPI):
    accounts.ensure_session_secret()
    conn = db.connect()
    seed.ensure(conn)
    tenancy.reindex_whatsapp(conn)
    conn.close()
    conn = db.connect_unchecked()  # startup, before any request: over every business
    try:
        for template, tid in seed.demo_ids(conn).items():  # the demo owners' logins
            accounts.ensure_demo_login(conn, tid, template)
        if env("DEMO_HISTORY").lower() in ("1", "true", "yes"):
            seed.history(conn)  # once: skipped when the demos already have history
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
app.include_router(try_page.router)
app.include_router(orders.router)
app.include_router(feedback.router)
app.include_router(admin.router)
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
