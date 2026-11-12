import { Loader2, Plus, Search, Trash2 } from "lucide-react";
import * as React from "react";

import { Field } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import { createOrder, formatInr, type Order, type Product } from "./api";
import { type Draft, draftTotal, type Line, newLine, qtyOf } from "./draft";

function matches(products: Product[], query: string, taken: Set<number>) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  return products
    .filter((p) => !taken.has(p.id) && words.every((w) => `${p.name} ${p.pack_size}`.toLowerCase().includes(w)))
    .slice(0, 6);
}

/** Type a few letters, tap the product. Out-of-stock products show but can't be picked. */
function ProductPicker({
  line,
  index,
  products,
  taken,
  error,
  onChange,
}: {
  line: Line;
  index: number;
  products: Product[];
  taken: Set<number>;
  error?: string;
  onChange: (line: Line) => void;
}) {
  const id = React.useId();
  if (line.product) {
    const p = line.product;
    return (
      <div className="flex min-h-10 items-center justify-between gap-2 rounded-md border bg-muted px-3 py-2">
        <span className="min-w-0 text-sm">
          <span className="font-medium">{p.name}</span>
          <span className="text-muted-foreground">
            {p.pack_size && ` · ${p.pack_size}`} · {p.rate}
          </span>
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-8 px-2"
          onClick={() => onChange({ ...line, product: null, query: "" })}
          aria-label={`Change product ${index + 1}`}
        >
          Change
        </Button>
      </div>
    );
  }
  const found = matches(products, line.query, taken);
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="sr-only">
        Product {index + 1}
      </Label>
      <div className="relative">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id={id}
          value={line.query}
          onChange={(e) => onChange({ ...line, query: e.target.value })}
          placeholder="Type a product name"
          autoComplete="off"
          className="pl-9"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
        />
      </div>
      {line.query.trim() && (
        <ul aria-label={`Matches for product ${index + 1}`} className="flex flex-col overflow-hidden rounded-md border">
          {found.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">No product by that name in your catalogue.</li>}
          {found.map((p) => (
            <li key={p.id} className="border-b last:border-b-0">
              <button
                type="button"
                disabled={!p.in_stock}
                onClick={() => onChange({ ...line, product: p, query: "" })}
                className="flex min-h-10 w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-accent focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="min-w-0">
                  {p.name}
                  {p.pack_size && <span className="text-muted-foreground"> · {p.pack_size}</span>}
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground">{p.in_stock ? p.rate : "Out of stock"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-[13px] font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

type Props = {
  draft: Draft;
  onDraft: (d: Draft) => void;
  products: Product[];
  catalogError: string | null;
  onSaved: (order: Order) => void;
  /** After an error that may mean the catalogue changed (out of stock), reload it. */
  onCatalogStale: () => void;
  onAuthError: (err: unknown) => boolean;
  /** Called when the owner keeps the existing order instead of saving a duplicate. */
  onDiscard: () => void;
};

/**
 * The add-order form (phase2-plan §6 order board): shop and phone, product rows with qty, a running
 * total and Save. What was typed is kept through any error, and through closing the sheet.
 */
export function OrderForm({ draft, onDraft, products, catalogError, onSaved, onCatalogStale, onAuthError, onDiscard }: Props) {
  const [saving, setSaving] = React.useState(false);
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);
  const [duplicate, setDuplicate] = React.useState<Order | null>(null);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => onDraft({ ...draft, [k]: v });
  const setLine = (i: number, l: Line) => onDraft({ ...draft, lines: draft.lines.map((x, j) => (j === i ? l : x)) });
  const taken = new Set(draft.lines.map((l) => l.product?.id).filter((x): x is number => x !== undefined));
  const total = draftTotal(draft);

  function check(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!draft.shop_name.trim()) e.shop_name = "Please write the shop's name.";
    draft.lines.forEach((l, i) => {
      if (!l.product && l.query.trim()) e[`line-${i}`] = "Pick a product from the list.";
      if (l.product && !(qtyOf(l) >= 1 && qtyOf(l) <= 9999)) e[`qty-${i}`] = "Qty must be a whole number from 1 to 9999.";
    });
    if (!draft.lines.some((l) => l.product)) e.items = "Add at least one product.";
    return e;
  }

  async function save(allowDuplicate = false, retried = false): Promise<void> {
    const e = check();
    setErrors(e);
    setProblem(null);
    setDuplicate(null);
    if (Object.keys(e).length) return;
    setSaving(true);
    try {
      const order = await createOrder({
        shop_name: draft.shop_name.trim(),
        contact_name: draft.contact_name.trim(),
        phone: draft.phone.trim(),
        notes: draft.notes.trim(),
        source: draft.source,
        items: draft.lines.filter((l) => l.product).map((l) => ({ product_id: l.product!.id, qty: qtyOf(l) })),
        idempotency_key: draft.idempotencyKey,
        allow_duplicate: allowDuplicate,
      });
      onSaved(order);
    } catch (err) {
      if (onAuthError(err)) return;
      if (!(err instanceof ApiError)) {
        setProblem("Couldn't save the order. Please try again.");
      } else if (err.code === "TRY_AGAIN" && !retried) {
        setSaving(false);
        return save(allowDuplicate, true); // several orders took the same number at once: just save again
      } else if (err.code === "DUPLICATE_ORDER") {
        const existing = err.alternatives[0] as Order | undefined;
        setDuplicate(existing ?? null);
        setProblem(existing ? null : err.detail);
      } else {
        const f: Record<string, string> = {};
        if (err.fields.shop_name) f.shop_name = err.fields.shop_name;
        if (err.fields.phone) f.phone = err.fields.phone;
        setErrors(f);
        setProblem(Object.keys(f).length ? null : err.detail);
        if (err.code === "OUT_OF_STOCK" || err.code === "UNKNOWN_PRODUCT") onCatalogStale();
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
      className="flex flex-col gap-4"
    >
      <Field label="Shop name" error={errors.shop_name}>
        <Input value={draft.shop_name} onChange={(e) => set("shop_name", e.target.value)} autoComplete="off" maxLength={120} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
        <Field label="Contact name" optional>
          <Input value={draft.contact_name} onChange={(e) => set("contact_name", e.target.value)} autoComplete="off" maxLength={80} />
        </Field>
        <Field label="Mobile number" optional error={errors.phone}>
          <Input value={draft.phone} onChange={(e) => set("phone", e.target.value)} type="tel" inputMode="tel" autoComplete="off" />
        </Field>
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1.5 text-sm font-medium">Products</legend>
        {catalogError && <p className="text-sm text-destructive">{catalogError}</p>}
        {!catalogError && products.length === 0 && (
          <p className="text-sm text-muted-foreground">Your catalogue is empty. Add products in settings first.</p>
        )}
        {draft.lines.map((l, i) => (
          <div key={l.key} className="flex flex-col gap-2 rounded-lg border p-3">
            <ProductPicker line={l} index={i} products={products} taken={taken} error={errors[`line-${i}`]} onChange={(x) => setLine(i, x)} />
            <div className="flex items-end gap-2">
              <Field label="Qty" error={errors[`qty-${i}`]} className="w-24">
                <Input value={l.qty} onChange={(e) => setLine(i, { ...l, qty: e.target.value })} inputMode="numeric" aria-label={`Qty for product ${i + 1}`} />
              </Field>
              <span className="flex-1 pb-2.5 text-right text-sm font-medium tabular-nums">
                {l.product && qtyOf(l) > 0 ? formatInr(l.product.rate_paise * qtyOf(l)) : ""}
              </span>
              {draft.lines.length > 1 && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove product ${i + 1}`}
                  onClick={() => onDraft({ ...draft, lines: draft.lines.filter((_, j) => j !== i) })}
                >
                  <Trash2 />
                </Button>
              )}
            </div>
          </div>
        ))}
        {errors.items && (
          <p role="alert" className="text-[13px] font-medium text-destructive">
            {errors.items}
          </p>
        )}
        {draft.lines.length < 30 && (
          <Button variant="outline" className="w-fit" onClick={() => onDraft({ ...draft, lines: [...draft.lines, newLine()] })}>
            <Plus /> Add product
          </Button>
        )}
      </fieldset>

      <Field label="Notes" optional>
        <Input value={draft.notes} onChange={(e) => set("notes", e.target.value)} autoComplete="off" maxLength={300} />
      </Field>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1.5 text-sm font-medium">Came in by</legend>
        <RadioGroup value={draft.source} onValueChange={(v) => set("source", v as Draft["source"])} className="flex gap-6">
          <div className="flex items-center gap-2">
            <RadioGroupItem value="walk_in" id="order-src-walk-in" />
            <Label htmlFor="order-src-walk-in">Walk-in</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="whatsapp" id="order-src-whatsapp" />
            <Label htmlFor="order-src-whatsapp">WhatsApp</Label>
          </div>
        </RadioGroup>
      </fieldset>

      {problem && (
        <p role="alert" className="rounded-md bg-destructive-soft px-3 py-2.5 text-sm text-destructive-text">
          {problem}
        </p>
      )}
      {duplicate && (
        <div role="alert" className="flex flex-col gap-2 rounded-md bg-live-soft px-3 py-2.5 text-sm text-live-text">
          <p>
            Order #{duplicate.number} for {duplicate.shop_name} with the same items is still open ({duplicate.total}).
          </p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={onDiscard}>
              Keep #{duplicate.number}
            </Button>
            <Button size="sm" onClick={() => void save(true)}>
              Save as a new order
            </Button>
          </div>
        </div>
      )}

      <div className={cn("flex items-center justify-between gap-3 border-t pt-4")}>
        <div className="flex flex-col">
          <span className="text-[13px] text-muted-foreground">Total</span>
          <span className="text-lg font-semibold tabular-nums" aria-live="polite">
            {formatInr(total)}
          </span>
        </div>
        <Button type="submit" size="lg" disabled={saving}>
          {saving && <Loader2 aria-hidden className="animate-spin" />} Save order
        </Button>
      </div>
    </form>
  );
}
