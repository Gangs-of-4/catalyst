"""Orders for one business: create (with catalogue rates), number, list, and move through a fixed
lifecycle. Every function takes a connection scoped to one business (`conn.tid`).

Conflicts never offer another product: out of stock means a callback, and a duplicate points to the
order that already exists (contracts.md §1.11).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from ..core import config, db
from . import catalog

STATUSES = ("new", "confirmed", "dispatched", "delivered", "cancelled")
# The whole lifecycle in one table: the next statuses each status may move to.
TRANSITIONS = {
    "new": ("confirmed", "cancelled"),
    "confirmed": ("dispatched", "cancelled"),
    "dispatched": ("delivered",),
    "delivered": (),
    "cancelled": (),
}
OPEN = ("new", "confirmed", "dispatched")
SOURCES = ("phone", "whatsapp", "walk_in")
DESK_SOURCES = ("walk_in", "whatsapp")  # what the desk may enter; "phone" is the agent's
PAGE_SIZE = 200
MAX_QTY = 9999
MAX_LINES = 30


class OrderError(Exception):
    """`code`: VALIDATION, UNKNOWN_PRODUCT, OUT_OF_STOCK, DUPLICATE_ORDER, INVALID_TRANSITION or
    NOT_FOUND. `matches` are catalogue names for UNKNOWN_PRODUCT; `existing` is the order a
    DUPLICATE_ORDER points to."""

    def __init__(
        self,
        code: str,
        message: str,
        matches: list[dict] | None = None,
        existing: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.matches = matches or []
        self.existing = existing


@dataclass
class Line:
    """One requested line: a product by id (desk) or by spoken name (agent), and a quantity."""

    qty: int
    product_id: int | None = None
    product: str | None = None


def _today_bounds() -> tuple[str, str]:
    today = config.now().date()
    return today.isoformat(), (today + timedelta(days=1)).isoformat()


def _resolve(conn: db.Conn, lines: list[Line]) -> list[dict]:
    """Catalogue rows for each line, quantities merged per product. Raises OrderError."""
    if not lines:
        raise OrderError("VALIDATION", "Add at least one item.")
    if len(lines) > MAX_LINES:
        raise OrderError("VALIDATION", f"One order can have up to {MAX_LINES} items.")
    merged: dict[int, dict] = {}
    for line in lines:
        if not isinstance(line.qty, int) or isinstance(line.qty, bool) or not line.qty >= 1:
            raise OrderError("VALIDATION", "Quantity must be a whole number from 1 to 9999.")
        if line.product_id is not None:
            p = catalog.get(conn, line.product_id)
            if p is None or not p["active"]:
                raise OrderError("UNKNOWN_PRODUCT", "That product isn't in the catalogue.")
        else:
            try:
                p = catalog.find(conn, line.product or "")
            except catalog.CatalogError as e:
                raise OrderError("UNKNOWN_PRODUCT", str(e), e.matches) from e
        if not p["in_stock"]:
            raise OrderError("OUT_OF_STOCK", f"{p['name']} is out of stock right now.", [p])
        if p["id"] in merged:
            merged[p["id"]]["qty"] += line.qty
        else:
            merged[p["id"]] = {"product": p, "qty": line.qty}
        if merged[p["id"]]["qty"] > MAX_QTY:
            raise OrderError("VALIDATION", "Quantity must be a whole number from 1 to 9999.")
    return list(merged.values())


def get(conn: db.Conn, order_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM orders WHERE tenant_id = ? AND id = ?", (conn.tid, order_id)
    ).fetchone()
    return _with_items(conn, [row])[0] if row else None


def _with_items(conn: db.Conn, rows: list[db.Row]) -> list[dict]:
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ", ".join("?" for _ in ids)
    items = conn.execute(
        f"SELECT * FROM order_items WHERE tenant_id = ? AND order_id IN ({marks}) ORDER BY id",
        (conn.tid, *ids),
    ).fetchall()
    by_order: dict[int, list[dict]] = {}
    for it in items:
        by_order.setdefault(it["order_id"], []).append(
            {
                "product_id": it["product_id"],
                "name": it["name"],
                "pack_size": it["pack_size"],
                "qty": it["qty"],
                "rate_paise": it["rate_paise"],
                "rate": catalog.format_inr(it["rate_paise"]),
                "amount": catalog.format_inr(it["qty"] * it["rate_paise"]),
            }
        )
    out = []
    for r in rows:
        lines = by_order.get(r["id"], [])
        total = sum(x["qty"] * x["rate_paise"] for x in lines)
        out.append(
            {
                "id": r["id"],
                "number": r["number"],
                "shop_name": r["shop_name"],
                "contact_name": r["contact_name"],
                "phone": r["phone"],
                "notes": r["notes"],
                "status": r["status"],
                "next": list(TRANSITIONS[r["status"]]),
                "source": r["source"],
                "call_id": r["call_id"],
                "items": lines,
                "total_paise": total,
                "total": catalog.format_inr(total),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        )
    return out


def list_orders(
    conn: db.Conn,
    status: str | None = None,
    day: str | None = None,
    before_id: int | None = None,
    limit: int = PAGE_SIZE,
) -> list[dict]:
    """Newest first, at most `limit`. `day` is YYYY-MM-DD (IST, by creation time). For the next
    page pass the last order's id as `before_id`."""
    sql = "SELECT * FROM orders WHERE tenant_id = ?"
    params: list = [conn.tid]
    if before_id is not None:
        sql += " AND id < ?"
        params.append(before_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if day:
        start = date.fromisoformat(day)
        sql += " AND created_at >= ? AND created_at < ?"
        params += [start.isoformat(), (start + timedelta(days=1)).isoformat()]
    rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", [*params, limit]).fetchall()
    return _with_items(conn, rows)


def _duplicate(conn: db.Conn, phone: str | None, shop: str, wanted: dict[int, int]) -> dict | None:
    """An open order placed today by the same caller (phone, else shop name) with the same items."""
    start, end = _today_bounds()
    if phone:
        rows = conn.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND phone = ? AND created_at >= ?"
            " AND created_at < ? AND status IN (?, ?, ?)",
            (conn.tid, phone, start, end, *OPEN),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND created_at >= ? AND created_at < ?"
            " AND status IN (?, ?, ?)",
            (conn.tid, start, end, *OPEN),
        ).fetchall()
        rows = [r for r in rows if catalog.name_key(r["shop_name"]) == catalog.name_key(shop)]
    for order in _with_items(conn, rows):
        if {x["product_id"]: x["qty"] for x in order["items"]} == wanted:
            return order
    return None


def create(
    conn: db.Conn,
    shop_name: str,
    lines: list[Line],
    source: str,
    contact_name: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
    call_id: str | None = None,
    idempotency_key: str | None = None,
    allow_duplicate: bool = False,
) -> dict:
    """Save an order at the catalogue's current rates. Returns the order.

    The same `idempotency_key` returns the order already saved (a resend after a lost connection).
    Raises OrderError: VALIDATION, UNKNOWN_PRODUCT, OUT_OF_STOCK, or DUPLICATE_ORDER (same caller,
    same items, still open, today) unless `allow_duplicate`."""
    if source not in SOURCES:
        raise OrderError("VALIDATION", f"Unknown source {source}.")
    shop_name = " ".join((shop_name or "").split())
    if not shop_name:
        raise OrderError("VALIDATION", "Shop name is required.")
    if idempotency_key:
        row = conn.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND idempotency_key = ?",
            (conn.tid, idempotency_key),
        ).fetchone()
        if row is not None:
            return _with_items(conn, [row])[0]
    resolved = _resolve(conn, lines)
    if not allow_duplicate:
        wanted = {x["product"]["id"]: x["qty"] for x in resolved}
        existing = _duplicate(conn, phone, shop_name, wanted)
        if existing is not None:
            raise OrderError(
                "DUPLICATE_ORDER",
                f"This looks like order {existing['number']}, placed earlier today.",
                existing=existing,
            )
    for _ in range(3):  # two orders at once can pick the same next number; retry
        ts = db.stamp()
        try:
            with conn:
                number = conn.execute(
                    "SELECT COALESCE(MAX(number), 0) + 1 FROM orders WHERE tenant_id = ?",
                    (conn.tid,),
                ).fetchone()[0]
                row = conn.execute(
                    "INSERT INTO orders (tenant_id, number, shop_name, contact_name, phone, notes,"
                    " status, source, call_id, idempotency_key, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?) RETURNING id",
                    (
                        conn.tid,
                        number,
                        shop_name[:120],
                        (contact_name or "").strip()[:80] or None,
                        phone,
                        (notes or "").strip()[:300] or None,
                        source,
                        call_id,
                        idempotency_key,
                        ts,
                        ts,
                    ),
                ).fetchone()
                for x in resolved:
                    p = x["product"]
                    conn.execute(
                        "INSERT INTO order_items (tenant_id, order_id, product_id, name,"
                        " pack_size, qty, rate_paise) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            conn.tid,
                            row["id"],
                            p["id"],
                            p["name"],
                            p["pack_size"],
                            x["qty"],
                            p["rate_paise"],
                        ),
                    )
            return get(conn, row["id"])
        except db.Conflict:
            conn.rollback()
            if idempotency_key:  # the same request won the race: hand back its order
                again = conn.execute(
                    "SELECT * FROM orders WHERE tenant_id = ? AND idempotency_key = ?",
                    (conn.tid, idempotency_key),
                ).fetchone()
                if again is not None:
                    return _with_items(conn, [again])[0]
    raise OrderError("TRY_AGAIN", "Several orders arrived at once. Please save it again.")


def set_status(conn: db.Conn, order_id: int, status: str) -> dict:
    """Move an order one step along TRANSITIONS. Raises OrderError NOT_FOUND / INVALID_TRANSITION /
    VALIDATION."""
    if status not in STATUSES:
        raise OrderError("VALIDATION", f"Unknown status {status}.")
    order = get(conn, order_id)
    if order is None:
        raise OrderError("NOT_FOUND", "No such order.")
    if status not in TRANSITIONS[order["status"]]:
        raise OrderError(
            "INVALID_TRANSITION",
            f"Order {order['number']} is {order['status']}; it can't become {status}.",
        )
    with conn:
        n = conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE tenant_id = ? AND id = ?"
            " AND status = ?",
            (status, db.stamp(), conn.tid, order_id, order["status"]),
        ).rowcount
    if n != 1:  # someone else moved it at the same moment
        raise OrderError("INVALID_TRANSITION", f"Order {order['number']} just changed. Reload.")
    return get(conn, order_id)


def find_for_caller(conn: db.Conn, number: int | None = None, phone: str | None = None) -> list:
    """Orders for an order-status question, only ever the caller's own: by number *and* the phone
    the order was placed with, else the last 3 for that phone. Without a phone, nothing: order
    numbers count 1, 2, 3, so a number alone would let anyone hear any shop's orders."""
    if not phone:
        return []
    if number is not None:
        rows = conn.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND number = ? AND phone = ?",
            (conn.tid, number, phone),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND phone = ?"
            " ORDER BY created_at DESC, id DESC LIMIT 3",
            (conn.tid, phone),
        ).fetchall()
    return _with_items(conn, rows)
