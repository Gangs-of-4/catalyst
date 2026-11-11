"""One business's product catalogue: add, edit, look up by spoken name, and CSV import.

Every function takes a connection scoped to one business (`conn.tid`). Rates are integer paise; the
agent only ever states a rate read from here (contracts.md §1.11).
"""

import csv
import difflib
import io
import re
from dataclasses import dataclass, field

from ..core import db

MAX_NAME = 120
MAX_PACK = 60
MAX_RATE_PAISE = 10_000_000_00  # ₹1 crore: anything above is a typo
MAX_IMPORT_ROWS = 2000
CSV_COLUMNS = ("name", "pack_size", "rate", "in_stock")
YES = {"yes", "y", "true", "1", "haan", "ha", "in stock", ""}
NO = {"no", "n", "false", "0", "nahi", "out", "out of stock"}


class CatalogError(Exception):
    """`code` is VALIDATION, NOT_FOUND or UNKNOWN_PRODUCT; `matches` are close names (spelling help,
    never a substitute)."""

    def __init__(self, code: str, message: str, matches: list[dict] | None = None):
        super().__init__(message)
        self.code = code
        self.matches = matches or []


def name_key(name: str) -> str:
    """The identity of a product name: case, spacing and punctuation don't make a new product."""
    return " ".join(re.sub(r"[^0-9a-zऀ-ॿ]+", " ", name.lower()).split())


def parse_rate(text: str | int | float) -> int:
    """'₹1,234.50', '1234.5' or 1234.5 → paise. Raises ValueError with a plain sentence."""
    raw = str(text).strip().replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", raw.strip()):
        raise ValueError("Rate must be a number of rupees, like 120 or 120.50.")
    rupees, _, paise = raw.strip().partition(".")
    value = int(rupees) * 100 + int((paise + "00")[:2])
    if value <= 0 or value > MAX_RATE_PAISE:
        raise ValueError("Rate must be more than ₹0 and less than ₹1 crore.")
    return value


def format_inr(paise: int) -> str:
    """Indian grouping, paise only when there are any: ₹1,23,456 or ₹99.50."""
    rupees, rest = divmod(paise, 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1] if head else ""
        digits = f"{head},{tail}"
    return f"₹{digits}" + (f".{rest:02d}" if rest else "")


def parse_stock(text) -> bool:
    if isinstance(text, bool):
        return text
    value = str(text).strip().lower()
    if value in YES:
        return True
    if value in NO:
        return False
    raise ValueError("In stock must be yes or no.")


def _clean(name: str, pack_size: str) -> tuple[str, str]:
    name, pack_size = " ".join(str(name).split()), " ".join(str(pack_size or "").split())
    if not name_key(name):
        raise ValueError("Product name is missing.")
    if len(name) > MAX_NAME:
        raise ValueError(f"Product name must be under {MAX_NAME} characters.")
    if len(pack_size) > MAX_PACK:
        raise ValueError(f"Pack size must be under {MAX_PACK} characters.")
    return name, pack_size


def public(row: db.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "pack_size": row["pack_size"],
        "rate_paise": row["rate_paise"],
        "rate": format_inr(row["rate_paise"]),
        "in_stock": bool(row["in_stock"]),
        "active": bool(row["active"]),
    }


def list_products(conn: db.Conn, include_inactive: bool = False) -> list[dict]:
    sql = "SELECT * FROM products WHERE tenant_id = ?"
    if not include_inactive:
        sql += " AND active = 1"
    rows = conn.execute(sql + " ORDER BY name", (conn.tid,)).fetchall()
    return [public(r) for r in rows]


def get(conn: db.Conn, product_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM products WHERE tenant_id = ? AND id = ?", (conn.tid, product_id)
    ).fetchone()
    return public(row) if row else None


def _by_key(conn: db.Conn, key: str) -> db.Row | None:
    return conn.execute(
        "SELECT * FROM products WHERE tenant_id = ? AND name_key = ?", (conn.tid, key)
    ).fetchone()


def add(conn: db.Conn, name: str, pack_size: str, rate_paise: int, in_stock: bool = True) -> dict:
    """Raises CatalogError VALIDATION (bad field, or the name is already in the catalogue)."""
    try:
        name, pack_size = _clean(name, pack_size)
    except ValueError as e:
        raise CatalogError("VALIDATION", str(e)) from e
    try:
        with conn:
            row = conn.execute(
                "INSERT INTO products (tenant_id, name, name_key, pack_size, rate_paise, in_stock,"
                " active, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?) RETURNING id",
                (conn.tid, name, name_key(name), pack_size, rate_paise, int(in_stock), db.stamp()),
            ).fetchone()
    except db.Conflict as e:
        raise CatalogError("VALIDATION", f"{name} is already in the catalogue.") from e
    return get(conn, row["id"])


def update(conn: db.Conn, product_id: int, **changes) -> dict:
    """Change any of name, pack_size, rate_paise, in_stock, active. Raises CatalogError."""
    current = get(conn, product_id)
    if current is None:
        raise CatalogError("NOT_FOUND", "That product isn't in the catalogue.")
    merged = {**current, **{k: v for k, v in changes.items() if v is not None}}
    try:
        name, pack_size = _clean(merged["name"], merged["pack_size"])
    except ValueError as e:
        raise CatalogError("VALIDATION", str(e)) from e
    try:
        with conn:
            conn.execute(
                "UPDATE products SET name = ?, name_key = ?, pack_size = ?, rate_paise = ?,"
                " in_stock = ?, active = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                (
                    name,
                    name_key(name),
                    pack_size,
                    int(merged["rate_paise"]),
                    int(bool(merged["in_stock"])),
                    int(bool(merged["active"])),
                    db.stamp(),
                    conn.tid,
                    product_id,
                ),
            )
    except db.Conflict as e:
        raise CatalogError("VALIDATION", f"{name} is already in the catalogue.") from e
    return get(conn, product_id)


def search(conn: db.Conn, query: str = "", limit: int = 10) -> list[dict]:
    """Active products whose name contains every word of `query` (all of them when empty)."""
    words = name_key(query or "").split()
    found = [p for p in list_products(conn) if all(w in name_key(p["name"]).split() for w in words)]
    if not found and words:  # "paracetamol500" vs "paracetamol 500": compare without spaces
        joined = "".join(words)
        found = [p for p in list_products(conn) if joined in name_key(p["name"]).replace(" ", "")]
    return found[:limit]


def find(conn: db.Conn, spoken: str) -> dict:
    """The one active product a caller or the desk named. Raises CatalogError UNKNOWN_PRODUCT with
    up to 3 `matches`: the products that fit when the name is ambiguous ("which one?"), or close
    spellings of the same name. Never a different product offered instead."""
    key = name_key(spoken or "")
    if not key:
        raise CatalogError("UNKNOWN_PRODUCT", "Which product?")
    exact = _by_key(conn, key)
    if exact is not None and exact["active"]:
        return public(exact)
    fits = search(conn, spoken, limit=4)
    if len(fits) == 1:
        return fits[0]
    if fits:
        raise CatalogError("UNKNOWN_PRODUCT", f"More than one product matches {spoken}.", fits[:3])
    names = {name_key(p["name"]): p for p in list_products(conn)}
    close = difflib.get_close_matches(key, list(names), n=3, cutoff=0.75)
    raise CatalogError(
        "UNKNOWN_PRODUCT", f"{spoken} isn't in the catalogue.", [names[k] for k in close]
    )


@dataclass
class ImportResult:
    added: int = 0
    updated: int = 0
    errors: list[dict] = field(default_factory=list)


def import_csv(conn: db.Conn, text: str) -> ImportResult:
    """Add or update products from CSV (columns name, pack_size, rate, in_stock; header required).

    Good rows are saved; bad rows are reported by their spreadsheet row number (the header is
    row 1) and skipped. A name already in the catalogue is updated, not duplicated."""
    result = ImportResult()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().lower() for h in next(reader, [])]
    missing = [c for c in ("name", "rate") if c not in header]
    if missing:
        result.errors.append(
            {
                "row": 1,
                "message": "The first row must name the columns: name, pack_size, rate, in_stock.",
            }
        )
        return result
    col = {c: header.index(c) for c in CSV_COLUMNS if c in header}
    seen: dict[str, int] = {}
    for number, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue
        if number - 1 > MAX_IMPORT_ROWS:
            result.errors.append(
                {"row": number, "message": f"Only the first {MAX_IMPORT_ROWS} rows are read."}
            )
            break

        row = {c: cells[i].strip() if i < len(cells) else "" for c, i in col.items()}
        try:
            name, pack_size = _clean(row.get("name", ""), row.get("pack_size", ""))
            rate = parse_rate(row.get("rate", ""))
            in_stock = parse_stock(row.get("in_stock", ""))
        except ValueError as e:
            result.errors.append({"row": number, "message": str(e)})
            continue
        key = name_key(name)
        if key in seen:
            result.errors.append(
                {"row": number, "message": f"{name} is already on row {seen[key]} of this file."}
            )
            continue
        seen[key] = number
        existing = _by_key(conn, key)
        if existing is None:
            add(conn, name, pack_size, rate, in_stock)
            result.added += 1
        else:
            update(
                conn,
                existing["id"],
                name=name,
                pack_size=pack_size,
                rate_paise=rate,
                in_stock=in_stock,
                active=True,
            )
            result.updated += 1
    return result
