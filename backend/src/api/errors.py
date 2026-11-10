"""The browser API's one error shape (contracts.md §6): {detail, code, fields?, alternatives?}.

`detail` is one plain sentence the page shows as-is. Never a stack trace.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..core.log import log


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        fields: dict[str, str] | None = None,
        alternatives: list | None = None,
    ):
        self.status, self.code, self.detail = status, code, detail
        self.fields, self.alternatives = fields, alternatives


def body(code: str, detail: str, fields=None, alternatives=None) -> dict:
    out: dict = {"detail": detail, "code": code}
    if fields:
        out["fields"] = fields
    if alternatives:
        out["alternatives"] = alternatives
    return out


def _label(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query") and not isinstance(p, int)]
    return (parts[-1] if parts else "this field").replace("_", " ")


def _plain(err: dict) -> str:
    """One plain sentence per pydantic error, with no library wording."""
    label = _label(tuple(err.get("loc", ())))
    kind = err.get("type", "")
    msg = str(err.get("msg", ""))
    if kind == "missing":
        return f"Please fill in {label}."
    if kind in ("string_too_short", "too_short"):
        return f"Please fill in {label}."
    if kind in ("string_too_long", "too_long"):
        return f"{label.capitalize()} is too long."
    if kind == "value_error":
        return msg.removeprefix("Value error, ")
    if kind.startswith("json") or kind == "model_attributes_type":
        return "That request wasn't readable. Reload the page and try again."
    return f"Please check {label}."


def plain_fields(errors: list[dict], prefix: str = "") -> dict[str, str]:
    """{field path: plain sentence} from pydantic errors, for forms to mark inputs."""
    fields: dict[str, str] = {}
    for e in errors:
        key = ".".join(str(p) for p in e.get("loc", ()) if p != "body")
        fields.setdefault(
            f"{prefix}.{key}" if prefix and key else prefix or key or "body", _plain(e)
        )
    return fields


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            body(exc.code, exc.detail, exc.fields, exc.alternatives), status_code=exc.status
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Pages show `detail` as-is, so make it plain sentences; `fields` lets forms mark inputs."""
        fields = plain_fields(exc.errors())
        detail = " ".join(dict.fromkeys(fields.values())) or "Invalid input."
        return JSONResponse(body("VALIDATION", detail, fields), status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Exception type and path only: messages and request bodies can hold names and phones.
        log.error("unhandled %s on %s", type(exc).__name__, request.url.path)
        return JSONResponse(
            body("INTERNAL", "Something went wrong on our side. Please try again."),
            status_code=500,
        )
