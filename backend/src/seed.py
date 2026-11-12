"""Demo data (Phase 2 M9): the schema, the two public demo businesses (a clinic and a wholesale
distributor), today's fictional data so screens aren't empty, and an optional 4-week history so
the desk, the order board and the admin page show real-looking usage.

Everything here is fictional: names from `verticals/*/demo-tenant.yaml`, phones in the
+91 9000x xxxxx test range. The history is deterministic for a given day and always relative to
today, so `reset_demo` (scripts/seed_demo.py) keeps the demos fresh until the program ends.
"""

import random
from datetime import date, datetime, time, timedelta

from .booking import service
from .core import config, db, tenancy
from .core.log import log
from .orders import catalog
from .orders import service as orders
from .verticals import loader

HISTORY_DAYS = 28
# What reset_demo clears before seeding again. Settings and logins are kept.
DEMO_DATA_TABLES = (
    "order_items",
    "orders",
    "products",
    "bookings",
    "blocks",
    "inbox",
    "calls",
    "tool_calls",
    "pending_actions",
    "events",
)


def ensure(conn: db.Conn, with_demo_data: bool = True) -> str:
    """Create the schema and both demo businesses if missing. Returns the demo clinic's id."""
    db.init(conn)
    clinic = tenancy.demo_id(conn, "clinic")
    if clinic is None:
        # Keep what an old single-clinic demo had set up on /setup, if its database was just moved.
        s = {**loader.default_settings(), **(db.take_carried_settings() or {})}
        clinic = tenancy.create(
            conn,
            "clinic",
            s,
            public_id=tenancy.DEMO_PUBLIC_ID.format(template="clinic"),
            is_demo=True,
        )
        if with_demo_data:
            _clinic_today(conn.for_tenant(clinic), s)
    if tenancy.demo_id(conn, "wholesale") is None:
        try:
            shop = tenancy.create(
                conn,
                "wholesale",
                wholesale_settings(),
                public_id=tenancy.DEMO_PUBLIC_ID.format(template="wholesale"),
                is_demo=True,
            )
        except db.Conflict:  # another worker starting at the same moment made it first
            conn.rollback()
            shop = None
        if shop and with_demo_data:
            _wholesale_today(conn.for_tenant(shop))
    return clinic


def demo_ids(conn: db.Conn) -> dict[str, str]:
    """{template: tenant id} for the demo businesses that exist."""
    out = {}
    for template in ("clinic", "wholesale"):
        tid = tenancy.demo_id(conn, template)
        if tid:
            out[template] = tid
    return out


def wholesale_settings() -> dict:
    t = loader.template_defaults("wholesale")
    demo = loader.load_yaml("demo-tenant.yaml", loader.template_dir("wholesale"))
    return {
        "name": demo["name"],
        "city": demo.get("city", ""),
        "address": demo["address"],
        "landmark": demo.get("landmark", ""),
        "sessions": demo["sessions"],
        "closed_weekdays": demo.get("closed_weekdays", []),
        "faqs": demo.get("faqs", []),
        "whatsapp_numbers": demo.get("whatsapp_numbers", []),
        "voice": demo.get("voice", "female"),
        "labels": t["labels"],
        "confirm_words": t["confirm_words"],
        "reject_words": t["reject_words"],
        "preview_expiry_min": t["preview_expiry_min"],
        "min_order": demo.get("min_order", ""),
        "delivery_area": demo.get("delivery_area", ""),
    }


# ---------- today ----------


def _clinic_today(conn: db.Conn, s: dict) -> None:
    seed = loader.load_yaml("demo-tenant.yaml").get("seed", {})
    today = config.now().date()
    open_days = [today]
    d = today
    while len(open_days) < 2:
        d += timedelta(days=1)
        if not service.is_closed(s, d):
            open_days.append(d)
    ts = db.stamp()
    with conn:
        for b in seed.get("bookings", []):
            # Direct insert: seed rows may sit in the past today, which `book` rightly refuses.
            conn.execute(
                "INSERT INTO bookings (tenant_id, resource_id, date, time, status, source, name,"
                " phone, reason, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'booked', ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (
                    conn.tid,
                    b["doctor"],
                    open_days[b["day"]].isoformat(),
                    b["time"],
                    b.get("source", "phone"),
                    b["name"],
                    b["phone"],
                    b.get("reason"),
                    ts,
                    ts,
                ),
            )
        for c in seed.get("callbacks", []):
            conn.execute(
                "INSERT INTO inbox (tenant_id, kind, urgent, name, phone, reason, note, created_at)"
                " VALUES (?, 'callback', 0, ?, ?, ?, ?, ?)",
                (conn.tid, c["name"], c["phone"], c["reason"], c.get("note"), ts),
            )


def _wholesale_today(conn: db.Conn) -> None:
    base = loader.template_dir("wholesale")
    catalog.import_csv(conn, (base / "sample-catalog.csv").read_text(encoding="utf-8"))
    demo = loader.load_yaml("demo-tenant.yaml", base)
    steps = {"new": [], "confirmed": ["confirmed"], "dispatched": ["confirmed", "dispatched"]}
    for o in demo.get("seed", {}).get("orders", []):
        made = orders.create(
            conn,
            o["shop"],
            [orders.Line(qty=qty, product=name) for name, qty in o["items"]],
            o.get("source", "phone"),
            contact_name=o.get("contact"),
            phone=o.get("phone"),
            allow_duplicate=True,
        )
        for status in steps[o.get("status", "new")]:
            orders.set_status(conn, made["id"], status)


# ---------- the 4-week history ----------


def _at(d: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(d, time(hour, minute), tzinfo=config.IST).isoformat(timespec="seconds")


def _phone(rng: random.Random) -> str:
    return f"+919000{rng.randint(100000, 999999)}"  # the fictional test range


def _event(conn: db.Conn, type_: str, at: str) -> None:
    conn.execute(
        "INSERT INTO events (tenant_id, user_id, type, created_at) VALUES (?, NULL, ?, ?)",
        (conn.tid, type_, at),
    )


def _call(conn: db.Conn, rng: random.Random, d: date, n: int, outcomes: list[str]) -> None:
    hour, minute = rng.randint(10, 18), rng.randint(0, 59)
    outcome = rng.choice(outcomes)
    started, ended = _at(d, hour, minute), _at(d, hour, min(minute + rng.randint(1, 4), 59))
    flags = {k: int(outcome == k) for k in ("booked", "escalated", "callback")}
    written = conn.execute(
        "INSERT INTO calls (tenant_id, id, started_at, ended_at, booked, escalated, callback,"
        " outcome, ended_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'customer-ended-call')"
        " ON CONFLICT DO NOTHING",
        (conn.tid, f"demo-{d.isoformat()}-{n}", started, ended, *flags.values(), outcome),
    ).rowcount
    if written == 1:  # the evidence counts only rows that exist
        _event(conn, "call_ended", ended)


def _owner_activity(conn: db.Conn, rng: random.Random, d: date) -> None:
    if rng.random() < 0.8:
        _event(conn, "login", _at(d, 9, rng.randint(0, 59)))
    for _ in range(rng.randint(0, 2)):
        _event(conn, "wa_command", _at(d, rng.randint(8, 21), rng.randint(0, 59)))


def _clinic_day(conn: db.Conn, s: dict, d: date, names: list[str]) -> None:
    rng = random.Random(f"clinic:{d.isoformat()}")
    slots = [(doc["id"], t) for doc in s["doctors"] for t in service.session_times(s)]
    for i, (doctor, t) in enumerate(rng.sample(slots, min(len(slots), rng.randint(3, 6)))):
        status = rng.choice(["done"] * 6 + ["no_show", "cancelled"])
        source = rng.choice(["phone", "phone", "phone", "walk_in", "whatsapp"])
        made = _at(d - timedelta(days=rng.randint(0, 3)), 10, i)
        written = conn.execute(
            "INSERT INTO bookings (tenant_id, resource_id, date, time, status, source, name,"
            " phone, reason, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT DO NOTHING",
            (
                conn.tid,
                doctor,
                d.isoformat(),
                t,
                status,
                source,
                rng.choice(names),
                _phone(rng),
                rng.choice(["checkup", "cleaning", "filling", "daant dard", None]),
                made,
                made,
            ),
        ).rowcount
        if written == 1:
            _event(conn, "booking_created", made)
            _event(conn, "booking_status", _at(d, 20, i))
    for n in range(rng.randint(2, 5)):
        _call(
            conn, rng, d, n, ["booked", "booked", "answered", "answered", "callback", "escalated"]
        )
    if rng.random() < 0.4:
        at = _at(d, 13, rng.randint(0, 59))
        conn.execute(
            "INSERT INTO inbox (tenant_id, kind, urgent, name, phone, reason, note, created_at,"
            " done_at) VALUES (?, 'callback', 0, ?, ?, 'unanswered_question', ?, ?, ?)",
            (conn.tid, rng.choice(names), _phone(rng), "Fees ke baare mein poocha", at, _at(d, 17)),
        )
        _event(conn, "callback_created", at)
    _owner_activity(conn, rng, d)


def _wholesale_day(conn: db.Conn, d: date, products: list[dict], shops: list[str]) -> None:
    rng = random.Random(f"wholesale:{d.isoformat()}")
    plan = sorted(  # by time, so order numbers follow the clock within the day too
        (
            rng.randint(9, 17),
            rng.randint(0, 59),
            rng.choice(["delivered"] * 5 + ["dispatched", "cancelled"]),
        )
        for _ in range(rng.randint(2, 5))
    )
    for i, (hour, minute, status) in enumerate(plan):
        made = _at(d, hour, minute)
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM orders WHERE tenant_id = ?", (conn.tid,)
        ).fetchone()[0]
        row = conn.execute(
            "INSERT INTO orders (tenant_id, number, shop_name, contact_name, phone, status,"
            " source, created_at, updated_at) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?) RETURNING id",
            (
                conn.tid,
                number,
                rng.choice(shops),
                _phone(rng),
                status,
                rng.choice(["phone", "phone", "whatsapp", "walk_in"]),
                made,
                made,
            ),
        ).fetchone()
        for p in rng.sample(products, rng.randint(1, min(3, len(products)))):
            conn.execute(
                "INSERT INTO order_items (tenant_id, order_id, product_id, name, pack_size, qty,"
                " rate_paise) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    conn.tid,
                    row["id"],
                    p["id"],
                    p["name"],
                    p["pack_size"],
                    rng.randint(2, 40),
                    p["rate_paise"],
                ),
            )
        _event(conn, "order_created", made)
        for step in range({"delivered": 3, "dispatched": 2, "cancelled": 1}[status]):
            _event(conn, "order_status", _at(d, 18, i * 3 + step))
    for n in range(rng.randint(1, 4)):
        _call(conn, rng, d, n, ["booked", "booked", "answered", "callback"])
    _owner_activity(conn, rng, d)


def has_history(conn: db.Conn) -> bool:
    """Seeded history is marked by its calls (ids "demo-<date>-<n>"), not by "any old event": a
    demo used before DEMO_HISTORY was set still gets its history."""
    return (
        conn.execute(
            "SELECT 1 FROM calls WHERE tenant_id = ? AND id LIKE 'demo-%' LIMIT 1", (conn.tid,)
        ).fetchone()
        is not None
    )


ORDER_COPY = (
    "shop_name",
    "contact_name",
    "phone",
    "notes",
    "status",
    "source",
    "call_id",
    "idempotency_key",
    "created_at",
    "updated_at",
)
ITEM_COPY = ("product_id", "name", "pack_size", "qty", "rate_paise")


def _take_out_orders(conn: db.Conn, since: date) -> list[tuple[dict, list[dict]]]:
    """Remove the orders created on or after `since`, inside the caller's transaction, and return
    them with their lines (exactly as stored) to be put back later."""
    rows = conn.execute(
        "SELECT * FROM orders WHERE tenant_id = ? AND created_at >= ? ORDER BY created_at, id",
        (conn.tid, since.isoformat()),
    ).fetchall()
    taken = []
    for r in rows:
        items = conn.execute(
            "SELECT * FROM order_items WHERE tenant_id = ? AND order_id = ? ORDER BY id",
            (conn.tid, r["id"]),
        ).fetchall()
        taken.append(({k: r[k] for k in ORDER_COPY}, [{k: i[k] for k in ITEM_COPY} for i in items]))
        conn.execute(
            "DELETE FROM order_items WHERE tenant_id = ? AND order_id = ?", (conn.tid, r["id"])
        )
        conn.execute("DELETE FROM orders WHERE tenant_id = ? AND id = ?", (conn.tid, r["id"]))
    return taken


def _put_back_orders(conn: db.Conn, taken: list[tuple[dict, list[dict]]]) -> None:
    """Insert orders taken out by _take_out_orders again, after everything else: new ids and
    numbers, every other field as it was."""
    for order, items in taken:
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM orders WHERE tenant_id = ?", (conn.tid,)
        ).fetchone()[0]
        row = conn.execute(
            "INSERT INTO orders (tenant_id, number, "
            + ", ".join(ORDER_COPY)
            + ") VALUES (?, ?, "
            + ", ".join("?" for _ in ORDER_COPY)
            + ") RETURNING id",
            (conn.tid, number, *(order[k] for k in ORDER_COPY)),
        ).fetchone()
        for it in items:
            conn.execute(
                "INSERT INTO order_items (tenant_id, order_id, " + ", ".join(ITEM_COPY) + ")"
                " VALUES (?, ?, " + ", ".join("?" for _ in ITEM_COPY) + ")",
                (conn.tid, row["id"], *(it[k] for k in ITEM_COPY)),
            )


def history(conn: db.Conn, days: int = HISTORY_DAYS) -> None:
    """Add the last `days` days (not today) of fictional usage to both demo businesses, in one
    transaction each. Safe to run twice, or from two workers at once: a business that already
    has seeded history is skipped, and a clash with another worker is rolled back."""
    today = config.now().date()
    past = [today - timedelta(days=i) for i in range(days, 0, -1)]
    for template, tid in demo_ids(conn).items():
        scoped = conn.for_tenant(tid)
        if has_history(scoped):
            continue
        s = tenancy.load_settings(scoped)
        demo = loader.load_yaml("demo-tenant.yaml", loader.template_dir(template))
        names = demo.get("history", {})
        products = catalog.list_products(scoped) if template == "wholesale" else []
        try:
            with scoped:
                # Today's orders (seeded, or placed on the demo already) are taken out and put
                # back after the history, so ids and numbers both follow the dates and the order
                # board's newest-first page starts with today's.
                today_orders = _take_out_orders(scoped, today) if template == "wholesale" else []
                for d in past:
                    if service.is_closed(s, d):
                        continue
                    if template == "clinic":
                        _clinic_day(scoped, s, d, names.get("patients") or ["Demo Patient"])
                    elif products:
                        _wholesale_day(scoped, d, products, names.get("shops") or ["Demo Shop"])
                _put_back_orders(scoped, today_orders)
        except db.Conflict:
            scoped.rollback()
            log.info("seed: another worker is adding the %s demo history", template)


def _preflight(template: str) -> None:
    """Everything reset_demo reads, read before it deletes anything: a broken YAML or CSV fails
    here, leaving the demo as it was."""
    base = loader.template_dir(template)
    loader.load_yaml("demo-tenant.yaml", base)
    if template == "wholesale":
        text = (base / "sample-catalog.csv").read_text(encoding="utf-8")
        if not text.lower().startswith("name,"):
            raise ValueError("sample-catalog.csv has no header row")


def reset_demo(conn: db.Conn, days: int = HISTORY_DAYS) -> list[str]:
    """Clear both demo businesses' data (settings and logins stay), then seed today and the
    history again, anchored to today. Returns the templates reset. `conn` is unchecked."""
    done = []
    ids = demo_ids(conn)
    for template in ids:
        _preflight(template)
    for template, tid in ids.items():
        scoped = conn.for_tenant(tid)
        with scoped:
            for table in DEMO_DATA_TABLES:
                scoped.execute(f"DELETE FROM {table} WHERE tenant_id = ?", (tid,))
        if template == "clinic":
            _clinic_today(scoped, tenancy.load_settings(scoped))
        else:
            _wholesale_today(scoped)
        done.append(template)
    history(conn, days)
    return done
