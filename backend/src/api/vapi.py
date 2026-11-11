"""POST /vapi/webhook: Vapi tool calls and server messages (contracts.md §1.10)."""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ValidationError

from ..agents import calls, tools
from ..core import db
from ..core import phone as ph
from ..core import settings as cs
from ..core.log import log
from .deps import get_conn, get_webhook_conn, secret_ok

router = APIRouter()


class _Function(BaseModel):
    name: str
    arguments: dict | str | None = None


class _ToolCall(BaseModel):
    id: str
    function: _Function


def _args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw, strict=False)  # LLMs sometimes put raw newlines in strings
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def tool_call_list(message: dict) -> list[_ToolCall]:
    """Accept both `toolCallList[]` and the older `toolWithToolCallList[].toolCall`."""
    raw = message.get("toolCallList")
    if not raw:
        raw = [
            t.get("toolCall")
            for t in message.get("toolWithToolCallList") or []
            if isinstance(t, dict)
        ]
    out = []
    for item in raw or []:
        try:
            out.append(_ToolCall.model_validate(item))
        except ValidationError:
            log.warning("vapi: skipped a malformed tool call")
    return out


@router.post("/vapi/webhook/{public_id}")
async def business_webhook(
    request: Request,
    background: BackgroundTasks,
    conn: db.Conn = Depends(get_webhook_conn),
):
    """One business's assistant: tenant from the path, auth by that business's own secret."""
    return await _handle(request, background, conn)


@router.post("/vapi/webhook")
async def legacy_webhook(
    request: Request,
    background: BackgroundTasks,
    conn: db.Conn = Depends(get_conn),
    x_catalyst_secret: str | None = Header(default=None),
):
    """Transitional single-tenant route for the demo clinic's original assistant (global secret from
    .env). Removed once every assistant is re-synced to its own path (contracts.md §1.10)."""
    if not secret_ok(x_catalyst_secret, "CATALYST_TOOL_SECRET"):
        raise HTTPException(401, "Bad or missing x-catalyst-secret")
    return await _handle(request, background, conn)


async def _handle(request: Request, background: BackgroundTasks, conn: db.Conn):
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Body must be JSON") from None
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, dict):
        raise HTTPException(400, "Missing message")
    kind = message.get("type")
    call = message.get("call") or {}
    call_id = call.get("id")

    if kind == "tool-calls":
        if call_id:
            calls.touch(conn, call_id)
        ctx = tools.Ctx(
            conn=conn,
            settings=cs.load(conn),
            call_id=call_id,
            caller_phone=ph.normalize((call.get("customer") or {}).get("number")),
        )
        results = []
        for tc in tool_call_list(message):
            cached = conn.execute(
                "SELECT result FROM tool_calls WHERE tenant_id = ? AND id = ?", (conn.tid, tc.id)
            ).fetchone()
            if cached:
                result = cached["result"]
            else:
                result = tools.run(ctx, tc.function.name, _args(tc.function.arguments))
                with conn:
                    conn.execute(
                        "INSERT INTO tool_calls (tenant_id, id, result, created_at)"
                        " VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                        (conn.tid, tc.id, result, db.stamp()),
                    )
            log.info("vapi: call %s tool %s", call_id, tc.function.name)
            results.append({"name": tc.function.name, "toolCallId": tc.id, "result": result})
        for job in ctx.defer:
            background.add_task(job)
        return {"results": results}

    if kind == "end-of-call-report":
        outcome = calls.end_of_call(conn, message)
        log.info("vapi: call %s ended, outcome %s", call_id, outcome)
        return {"ok": True}

    return {"ok": True}
