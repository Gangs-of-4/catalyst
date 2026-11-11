"""Catalogue and order board for the logged-in owner's business (contracts.md §6.1). Only for
templates with the `orders` module; others get 404."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ..core import db
from ..core import phone as ph
from ..orders import catalog
from ..orders import service as orders
from .deps import require_csrf_header, require_orders
from .errors import ApiError

router = APIRouter(dependencies=[Depends(require_csrf_header)])
MAX_CSV_BYTES = 1_000_000

STATUS_CODES = {
    "NOT_FOUND": 404,
    "DUPLICATE_ORDER": 409,
    "INVALID_TRANSITION": 409,
    "OUT_OF_STOCK": 409,
}


def _catalog_error(e: catalog.CatalogError) -> ApiError:
    return ApiError(404 if e.code == "NOT_FOUND" else 422, e.code, str(e), alternatives=e.matches)


def _order_error(e: orders.OrderError) -> ApiError:
    """Never another product as an alternative: a duplicate gets the existing order; an unknown name
    gets catalogue spellings of what was asked for."""
    alternatives = [e.existing] if e.existing else e.matches if e.code == "UNKNOWN_PRODUCT" else []
    return ApiError(STATUS_CODES.get(e.code, 422), e.code, str(e), alternatives=alternatives)


# Catalogue


@router.get("/api/catalog")
def get_catalog(
    all_: bool = Query(False, alias="all"), conn: db.Conn = Depends(require_orders)
) -> dict:
    return {"products": catalog.list_products(conn, include_inactive=all_)}


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=catalog.MAX_NAME)
    pack_size: str = Field(default="", max_length=catalog.MAX_PACK)
    rate: str | float = Field(description="Rupees, e.g. 120 or '120.50'")
    in_stock: bool = True


class ProductChange(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=catalog.MAX_NAME)
    pack_size: str | None = Field(default=None, max_length=catalog.MAX_PACK)
    rate: str | float | None = None
    in_stock: bool | None = None
    active: bool | None = None


def _paise(rate) -> int:
    try:
        return catalog.parse_rate(rate)
    except ValueError as e:
        raise ApiError(422, "VALIDATION", str(e), fields={"rate": str(e)}) from e


@router.post("/api/catalog")
def add_product(body: ProductIn, conn: db.Conn = Depends(require_orders)) -> dict:
    try:
        return catalog.add(conn, body.name, body.pack_size, _paise(body.rate), body.in_stock)
    except catalog.CatalogError as e:
        raise _catalog_error(e) from e


@router.put("/api/catalog/{product_id}")
def change_product(
    product_id: int, body: ProductChange, conn: db.Conn = Depends(require_orders)
) -> dict:
    changes = body.model_dump(exclude={"rate"}, exclude_none=True)
    if body.rate is not None:
        changes["rate_paise"] = _paise(body.rate)
    try:
        return catalog.update(conn, product_id, **changes)
    except catalog.CatalogError as e:
        raise _catalog_error(e) from e


@router.post("/api/catalog/import")
async def import_catalog(request: Request, conn: db.Conn = Depends(require_orders)) -> dict:
    """The CSV file as the raw request body (Content-Type: text/csv), at most 1 MB."""
    raw = await request.body()
    if len(raw) > MAX_CSV_BYTES:
        raise ApiError(422, "VALIDATION", "That file is too big. Keep it under 1 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(
            422, "VALIDATION", "Save the file as CSV (UTF-8) from Excel or Google Sheets."
        ) from None
    if not text.strip():
        raise ApiError(422, "VALIDATION", "The file is empty.")
    r = catalog.import_csv(conn, text)
    return {"added": r.added, "updated": r.updated, "errors": r.errors}


# Orders


class LineIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=orders.MAX_QTY)


class OrderIn(BaseModel):
    shop_name: str = Field(min_length=1, max_length=120)
    contact_name: str = Field(default="", max_length=80)
    phone: str = ""
    notes: str = Field(default="", max_length=300)
    items: list[LineIn] = Field(min_length=1, max_length=orders.MAX_LINES)
    source: str = "walk_in"
    idempotency_key: str | None = Field(default=None, max_length=80)
    allow_duplicate: bool = False


@router.get("/api/orders")
def list_orders(
    status: str | None = None,
    date_: str | None = Query(None, alias="date"),
    conn: db.Conn = Depends(require_orders),
) -> dict:
    if status and status not in orders.STATUSES:
        raise ApiError(422, "VALIDATION", f"Status must be one of: {', '.join(orders.STATUSES)}.")
    if date_:
        try:
            date.fromisoformat(date_)
        except ValueError:
            raise ApiError(422, "VALIDATION", "Date must look like 2026-11-15.") from None
    return {"orders": orders.list_orders(conn, status, date_)}


@router.post("/api/orders")
def add_order(body: OrderIn, conn: db.Conn = Depends(require_orders)) -> dict:
    phone = ph.normalize(body.phone) if body.phone.strip() else None
    if body.phone.strip() and not phone:
        message = "Phone must be a 10-digit Indian mobile number."
        raise ApiError(422, "VALIDATION", message, fields={"phone": message})
    if body.source not in ("walk_in", "whatsapp"):
        raise ApiError(422, "VALIDATION", "Source must be walk_in or whatsapp.")
    try:
        return orders.create(
            conn,
            body.shop_name,
            [orders.Line(qty=x.qty, product_id=x.product_id) for x in body.items],
            body.source,
            contact_name=body.contact_name,
            phone=phone,
            notes=body.notes,
            idempotency_key=body.idempotency_key,
            allow_duplicate=body.allow_duplicate,
        )
    except orders.OrderError as e:
        raise _order_error(e) from e


class StatusIn(BaseModel):
    status: str


@router.post("/api/orders/{order_id}/status")
def set_order_status(
    order_id: int, body: StatusIn, conn: db.Conn = Depends(require_orders)
) -> dict:
    try:
        return orders.set_status(conn, order_id, body.status)
    except orders.OrderError as e:
        raise _order_error(e) from e
