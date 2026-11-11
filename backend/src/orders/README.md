# orders

Catalogue and orders for templates whose `vertical.yaml` lists the `orders` module (wholesale, ADR-0037).

**Serves:** C4 (one shared order board, like the shared schedule), C7 (the desk's order board), C3 (rates come only from the catalogue).

**Contracts:** `context/contracts.md` §1.11 (wholesale tools), §3.1 (`products`, `orders`, `order_items`), §6.1 (`/api/catalog`, `/api/orders`).

- `catalog.py`: add, edit, find by spoken name, CSV import. Rates are integer paise; `format_inr` writes ₹1,23,456. `find` returns a product only for its exact name (case and punctuation aside); otherwise it raises `UNKNOWN_PRODUCT` with up to 3 full names to confirm with the caller, even when only one fits ("Crocin" vs "Crocin Advance" are different medicines). Never a substitute. A hidden product is "not available", never swapped for a visible one whose name contains it. Names of any script count (`name_key`). CSV import checks the whole file, then saves the good rows in one transaction.
- `service.py`: create an order at the catalogue's current rates (name, pack size and rate copied onto each line), a per-business order number, idempotency keys, duplicate check, and the lifecycle in one table (`TRANSITIONS`): new → confirmed → dispatched → delivered, or cancelled before dispatch.

**Must not:** suggest another product when one is out of stock or unknown; quote a rate that isn't in the catalogue; query without the business's `tenant_id` (every function takes a scoped connection).
