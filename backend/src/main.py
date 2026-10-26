"""FastAPI app: agent webhook, WhatsApp webhook, staff APIs and the static pages."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import seed
from .api import desk, public, vapi
from .core import db
from .core.config import FRONTEND_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    seed.ensure(conn)
    conn.close()
    yield


app = FastAPI(title="Catalyst clinic demo", lifespan=lifespan)
app.include_router(vapi.router)
app.include_router(public.router)
app.include_router(desk.router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
