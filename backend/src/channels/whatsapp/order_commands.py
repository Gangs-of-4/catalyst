"""Owner commands for a business with the `orders` module (wholesale; contracts.md §4).

Rule-parsed. A product is found only by its exact catalogue name: anything else replies with the
closest names and asks again, never guesses. Every write is previewed and applies on "Haan".
"""

import re
from datetime import timedelta

from ...core import config, db
from ...orders import catalog
from ...orders import service as orders

READS = ("orders_today",)
WRITES = ("set_rate", "stock_out", "stock_in", "order_status")

HELP = (
    "Commands:\n"
    "• aaj ke orders\n"
    "• order 42 confirm / dispatch / delivered / cancel\n"
    "• rate <product ka poora naam> 42\n"
    "• stock khatam <product>  |  stock aa gaya <product>\n"
    "• summary  |  callbacks\n"
    "Har badlav pehle preview hoga; 'Haan' bhejne par hi lagega."
)

STATUS_WORDS = {
    "confirm": "confirmed",
    "confirmed": "confirmed",
    "pakka": "confirmed",
    "dispatch": "dispatched",
    "dispatched": "dispatched",
    "bhej diya": "dispatched",
    "bhej do": "dispatched",
    "nikal gaya": "dispatched",
    "deliver": "delivered",
    "delivered": "delivered",
    "pahunch gaya": "delivered",
    "cancel": "cancelled",
    "cancelled": "cancelled",
    "radd": "cancelled",
}
STATUS_HINDI = {
    "new": "naya",
    "confirmed": "confirmed",
    "dispatched": "dispatched",
    "delivered": "delivered",
    "cancelled": "cancelled",
}
_STATUS = "|".join(sorted((re.escape(w) for w in STATUS_WORDS), key=len, reverse=True))
_ORDER = re.compile(
    rf"^order\s*(?:no\.?|number)?\s*#?\s*(\d+)\s+(?:ko\s+)?({_STATUS})(?:\s+karo|\s+kar do)?$"
)
# The product ends at a separator: "=", ":", "->", or a space (optionally then "ab"/"to" as their
# own words). Currency words are their own tokens, so "potato", "kabab" and "cars" stay whole.
_RATE = re.compile(
    r"^(?:rate|price|bhav|daam)\s+(.+?)(?:\s*(?:=|:|->)\s*|\s+(?:(?:ab|to)\s+)?)"
    r"(?:(?:₹|rs\.?|rupees?)\s*)?(\d+(?:\.\d{1,2})?)(?:\s*(?:rs|rupees?|rupaye))?$"
)
# (pattern, explicit). An explicit form starts with the stock words, so it is a stock command
# whatever the name. The trailing forms ("X khatam", "X aa gaya") read like everyday messages
# ("payment aaya", "driver aa gaya"), so they count only when X names catalogue products.
_OUT = (
    (re.compile(r"^(?:stock\s+khatam|out\s+of\s+stock|stock\s+out)\s+(.+)$"), True),
    (
        re.compile(
            r"^(.+?)\s+(?:ka\s+|ki\s+)?(?:stock\s+)?khatam(?:\s+hai|\s+ho\s+gaya|\s+ho\s+gayi)?$"
        ),
        False,
    ),
)
_IN = (
    (
        re.compile(r"^(?:stock\s+aa\s+gaya|stock\s+aaya|in\s+stock|back\s+in\s+stock)\s+(.+)$"),
        True,
    ),
    (
        re.compile(
            r"^(.+?)\s+(?:ka\s+|ki\s+)?(?:stock\s+)?(?:aa\s+gaya|aa\s+gayi|aaya|wapas\s+aaya)$"
        ),
        False,
    ),
)


def _product(conn: db.Conn, spoken: str) -> dict | str:
    """The exact product, or the reply asking which one."""
    try:
        return catalog.find(conn, spoken)
    except catalog.CatalogError as e:
        if e.matches:
            names = "; ".join(m["name"] for m in e.matches)
            return f"'{spoken}' ek exact product nahi hai. Catalogue mein: {names}. Poora naam bhejein."
        return f"'{spoken}' catalogue mein nahi mila. Naam check karke dobara bhejein."


def parse(conn: db.Conn, text: str, make) -> object | str | None:
    """A Command (via `make(**fields)`), a reply asking again, or None if not understood."""
    t = " ".join(text.lower().strip(" .!?।").split())
    if re.fullmatch(r"(?:aaj\s+ke\s+|today'?s?\s+)?orders?(?:\s+today|\s+aaj)?(?:\s+dikhao)?", t):
        return make(intent="orders_today")
    m = _ORDER.match(t)
    if m:
        number, status = int(m[1]), STATUS_WORDS[m[2]]
        order = orders.by_number(conn, number)
        if order is None:
            return f"Order {number} nahi mila."
        return make(intent="order_status", order_id=order["id"], status=status)
    m = _RATE.match(t)
    if m:
        p = _product(conn, m[1])
        if isinstance(p, str):
            return p
        try:
            paise = catalog.parse_rate(m[2])
        except ValueError as e:
            return str(e)
        return make(intent="set_rate", product_id=p["id"], rate_paise=paise)
    for intent, patterns in (("stock_out", _OUT), ("stock_in", _IN)):
        for pattern, explicit in patterns:
            m = pattern.match(t)
            if not m:
                continue
            if not explicit and not _names_a_product(conn, m[1]):
                return None  # "payment aaya": not a stock command; it goes to the ops inbox
            p = _product(conn, m[1])
            if isinstance(p, str):
                return p
            return make(intent=intent, product_id=p["id"])
    return None


def _names_a_product(conn: db.Conn, spoken: str) -> bool:
    """The words name a catalogue product exactly, or fit some (then we ask which one)."""
    try:
        catalog.find(conn, spoken)
        return True
    except catalog.CatalogError as e:
        return bool(e.matches)


def preview(conn: db.Conn, cmd) -> tuple[str, bool]:
    """(text, needs_confirm). needs_confirm False means the text explains why nothing will change."""
    if cmd.intent == "order_status":
        order = orders.get(conn, cmd.order_id)
        if order is None:
            return "Woh order ab nahi mila.", False
        if cmd.status not in orders.TRANSITIONS[order["status"]]:
            return (
                f"Order {order['number']} abhi {STATUS_HINDI[order['status']]} hai; "
                f"{STATUS_HINDI[cmd.status]} nahi ho sakta. Kuch nahi badla.",
                False,
            )
        return (
            f"Order {order['number']} ({order['shop_name']}) ko {STATUS_HINDI[cmd.status]} mark "
            "karein? Haan/Nahi",
            True,
        )
    p = catalog.get(conn, cmd.product_id)
    if p is None:
        return "Woh product ab catalogue mein nahi hai.", False
    label = p["name"] + (f" ({p['pack_size']})" if p["pack_size"] else "")
    if cmd.intent == "set_rate":
        new = catalog.format_inr(cmd.rate_paise)
        if cmd.rate_paise == p["rate_paise"]:
            return f"{label} ka rate pehle se {new} hai. Kuch nahi badla.", False
        return f"{label}: {p['rate']} → {new}. Sahi hai? Haan/Nahi", True
    if cmd.intent == "stock_out":
        if not p["in_stock"]:
            return f"{label} pehle se out of stock hai.", False
        return (
            f"{label} ko out of stock kar dein? Agent naye orders mein yeh nahi lega. Haan/Nahi",
            True,
        )
    if p["in_stock"]:
        return f"{label} pehle se in stock hai.", False
    return f"{label} ko in stock kar dein? Haan/Nahi", True


def apply(conn: db.Conn, cmd) -> str:
    """Apply a confirmed write. Re-checked here: things may have changed since the preview."""
    text, ok = preview(conn, cmd)
    if not ok:
        return text
    try:
        if cmd.intent == "order_status":
            orders.set_status(conn, cmd.order_id, cmd.status)
        elif cmd.intent == "set_rate":
            catalog.update(conn, cmd.product_id, rate_paise=cmd.rate_paise)
        else:
            catalog.update(conn, cmd.product_id, in_stock=cmd.intent == "stock_in")
    except (orders.OrderError, catalog.CatalogError) as e:
        return f"Nahi ho paya: {e}"
    return "Ho gaya — live hai."


def orders_today(conn: db.Conn) -> str:
    today = config.now().date().isoformat()
    found = orders.list_orders(conn, day=today, limit=15)
    if not found:
        return "Aaj abhi tak koi order nahi aaya."
    lines = [f"Aaj ke orders ({len(found)}{'+' if len(found) == 15 else ''}):"]
    for o in found:
        lines.append(
            f"• {o['number']}: {o['shop_name']} — {len(o['items'])} item, {o['total']}, "
            f"{STATUS_HINDI[o['status']]}"
        )
    return "\n".join(lines)


def summary(conn: db.Conn, name: str) -> str:
    """Today's and this week's (Monday to today, IST) order counts and value. Counts only."""
    today = config.now().date()
    tomorrow = (today + timedelta(days=1)).isoformat()
    monday = (today - timedelta(days=today.weekday())).isoformat()

    def line(start: str) -> str:
        t = orders.totals(conn, start, tomorrow)
        return f"{t['orders']} orders, {catalog.format_inr(t['value_paise'])}, {t['pending']} dispatch baaki"

    return f"{name}\nAaj: {line(today.isoformat())}\nIs hafte: {line(monday)}"
