"""FastAPI app: agent webhook, WhatsApp webhook, staff APIs and the static pages."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import seed
from .api import vapi
from .core import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    seed.ensure(conn)
    conn.close()
    yield


app = FastAPI(title="Catalyst clinic demo", lifespan=lifespan)
app.include_router(vapi.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
