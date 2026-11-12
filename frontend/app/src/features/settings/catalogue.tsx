import { Download, Loader2, PackageOpen, Pencil, Plus, Search, Upload } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { Field } from "@/components/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  addProduct,
  getAllProducts,
  type ImportResult,
  importCatalog,
  type Product,
  type ProductIn,
  updateProduct,
} from "@/features/orders/api";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX_CSV_BYTES = 1_000_000;

/** Paise → rupees as the owner would type them ("120" or "120.50"). */
const rupees = (paise: number) => (paise % 100 === 0 ? String(paise / 100) : (paise / 100).toFixed(2));

type Editing = { product: Product | null }; // null = a new product

/** Add or change one product. Saves straight away (its own endpoint), not through the page's Save bar. */
function ProductDialog({
  editing,
  onClose,
  onSaved,
  onAuthError,
}: {
  editing: Editing | null;
  onClose: () => void;
  onSaved: (p: Product, message: string) => void;
  onAuthError: (err: unknown) => boolean;
}) {
  const p = editing?.product ?? null;
  const [form, setForm] = React.useState<ProductIn>({
    name: p?.name ?? "",
    pack_size: p?.pack_size ?? "",
    rate: p ? rupees(p.rate_paise) : "",
    in_stock: p?.in_stock ?? true,
  });
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  async function run(action: () => Promise<Product>, message: string) {
    setSaving(true);
    setProblem(null);
    try {
      onSaved(await action(), message);
    } catch (err) {
      if (onAuthError(err)) return;
      if (err instanceof ApiError) {
        setErrors(err.fields);
        setProblem(err.fields.rate ? null : err.detail);
      } else {
        setProblem("Couldn't save the product. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = "Write the product's name.";
    if (!form.rate.trim()) errs.rate = "Write the rate in rupees, like 120 or 120.50.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const body = { ...form, name: form.name.trim(), pack_size: form.pack_size.trim(), rate: form.rate.trim() };
    void run(() => (p ? updateProduct(p.id, body) : addProduct(body)), p ? `${body.name} saved.` : `${body.name} added.`);
  }

  return (
    <Dialog open={editing !== null} onOpenChange={(open) => !open && !saving && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{p ? "Change product" : "Add a product"}</DialogTitle>
          <DialogDescription>Your front desk quotes only these names and rates.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <Field label="Name" error={errors.name}>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoComplete="off" maxLength={120} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Pack size" optional error={errors.pack_size}>
              <Input value={form.pack_size} onChange={(e) => setForm({ ...form, pack_size: e.target.value })} placeholder="Strip of 10" maxLength={60} />
            </Field>
            <Field label="Rate (₹)" error={errors.rate}>
              <Input value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} inputMode="decimal" placeholder="120.50" />
            </Field>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="product-in-stock" checked={form.in_stock} onCheckedChange={(v) => setForm({ ...form, in_stock: v === true })} />
            <Label htmlFor="product-in-stock">In stock</Label>
          </div>
          {problem && (
            <p role="alert" className="rounded-md bg-destructive-soft px-3 py-2.5 text-sm text-destructive-text">
              {problem}
            </p>
          )}
          <DialogFooter className="sm:justify-between">
            {p ? (
              <Button
                variant="ghost"
                className={p.active ? "text-destructive" : undefined}
                disabled={saving}
                onClick={() => void run(() => updateProduct(p.id, { active: !p.active }), p.active ? `${p.name} hidden.` : `${p.name} is back.`)}
              >
                {p.active ? "Hide from catalogue" : "Show again"}
              </Button>
            ) : (
              <span />
            )}
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <Button variant="outline" onClick={onClose} disabled={saving}>
                Back
              </Button>
              <Button type="submit" disabled={saving}>
                {saving && <Loader2 aria-hidden className="animate-spin" />} {p ? "Save product" : "Add product"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The wholesale catalogue (orders template): search, add, change, mark out of stock, hide, and
 * CSV upload with a downloadable sample. Every change saves straight away.
 */
export function CatalogueSection({
  template,
  onAuthError,
}: {
  /** The business's template, for the sample CSV link (shown once it's known). */
  template: string | null;
  onAuthError: (err: unknown) => boolean;
}) {
  const [products, setProducts] = React.useState<Product[] | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState("");
  const [showHidden, setShowHidden] = React.useState(false);
  const [editing, setEditing] = React.useState<Editing | null>(null);
  const [stockId, setStockId] = React.useState<number | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [result, setResult] = React.useState<ImportResult | null>(null);
  const [uploadError, setUploadError] = React.useState<string | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(
    async (signal?: AbortSignal) => {
      try {
        const r = await getAllProducts(signal);
        setProducts(r.products);
        setLoadError(null);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!onAuthError(err)) setLoadError(err instanceof ApiError ? err.detail : "Your catalogue didn't load.");
      }
    },
    [onAuthError],
  );

  // The first load is written out here rather than calling load(): the React lint rule
  // (react-hooks/set-state-in-effect) rejects an effect that calls a state-setting callback.
  React.useEffect(() => {
    const ctrl = new AbortController();
    getAllProducts(ctrl.signal)
      .then((r) => setProducts(r.products))
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!onAuthError(err)) setLoadError(err instanceof ApiError ? err.detail : "Your catalogue didn't load.");
      });
    return () => ctrl.abort();
  }, [onAuthError]);

  function replace(p: Product) {
    setProducts((list) => {
      if (!list) return [p];
      return list.some((x) => x.id === p.id) ? list.map((x) => (x.id === p.id ? p : x)) : [...list, p];
    });
  }

  async function toggleStock(p: Product) {
    setStockId(p.id);
    try {
      const fresh = await updateProduct(p.id, { in_stock: !p.in_stock });
      replace(fresh);
      toast.success(fresh.in_stock ? `${p.name} is in stock.` : `${p.name} marked out of stock.`);
    } catch (err) {
      if (!onAuthError(err)) toast.error(err instanceof ApiError ? err.detail : "Couldn't change it. Please try again.");
    } finally {
      setStockId(null);
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // the same file can be picked again after fixing it
    if (!file) return;
    setResult(null);
    setUploadError(null);
    if (file.size > MAX_CSV_BYTES) {
      setUploadError("That file is too big. Keep it under 1 MB.");
      return;
    }
    setUploading(true);
    try {
      const r = await importCatalog(file);
      setResult(r);
      await load();
    } catch (err) {
      if (!onAuthError(err)) setUploadError(err instanceof ApiError ? err.detail : "Couldn't upload the file. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const list = (products ?? [])
    .filter((p) => showHidden || p.active)
    .filter((p) => words.every((w) => `${p.name} ${p.pack_size}`.toLowerCase().includes(w)))
    .sort((a, b) => a.name.localeCompare(b.name));
  const hiddenCount = (products ?? []).filter((p) => !p.active).length;

  return (
    <div className="flex flex-col gap-4">
      {/* Upload */}
      <div className="flex flex-col gap-3 rounded-lg bg-surface-soft p-3">
        <p className="text-sm text-body">
          Have a price list in Excel or Google Sheets? Save it as CSV with the columns <span className="font-medium">name, pack_size, rate, in_stock</span>.
          Names already here are updated; nothing is deleted.
        </p>
        <div className="flex flex-wrap gap-2">
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="sr-only" aria-label="CSV file" onChange={(e) => void onFile(e)} />
          <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 aria-hidden className="animate-spin" /> : <Upload aria-hidden />} Upload CSV
          </Button>
          {template && (
            <Button asChild variant="ghost">
              <a href={`/api/templates/${encodeURIComponent(template)}/sample-catalog.csv`} download>
                <Download aria-hidden /> Download sample
              </a>
            </Button>
          )}
        </div>
        {uploadError && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {uploadError}
          </p>
        )}
        {result && (
          <div role="status" className="flex flex-col gap-1.5 text-sm">
            <p className="font-medium">
              Added {result.added}, updated {result.updated}.
              {result.errors.length > 0 && ` ${result.errors.length} ${result.errors.length === 1 ? "row was" : "rows were"} skipped:`}
            </p>
            {result.errors.length > 0 && (
              <ul className="flex max-h-48 flex-col gap-1 overflow-y-auto rounded-md border bg-background p-2 text-[13px]">
                {result.errors.map((e, i) => (
                  <li key={i}>
                    <span className="font-medium tabular-nums">Row {e.row}:</span> {e.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* List */}
      {loadError ? (
        <p className="text-sm text-destructive">{loadError}</p>
      ) : products === null ? (
        <div className="h-40 animate-pulse rounded-lg bg-muted" role="status" aria-label="Loading your catalogue" />
      ) : (
        <>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search products" aria-label="Search products" className="pl-9" />
            </div>
            <Button onClick={() => setEditing({ product: null })}>
              <Plus aria-hidden /> Add product
            </Button>
          </div>
          {hiddenCount > 0 && (
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox checked={showHidden} onCheckedChange={(v) => setShowHidden(v === true)} aria-label="Show hidden products" />
              Show {hiddenCount} hidden {hiddenCount === 1 ? "product" : "products"}
            </label>
          )}
          {list.length === 0 ? (
            <EmptyState
              icon={PackageOpen}
              title={products.length === 0 ? "No products yet" : "Nothing matches"}
              description={products.length === 0 ? "Add them one by one, or upload your price list as CSV." : "Try fewer letters."}
            />
          ) : (
            <ul aria-label="Products" className="flex flex-col divide-y rounded-lg border">
              {list.map((p) => (
                <li key={p.id} className={cn("flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between", !p.active && "bg-surface-soft")}>
                  <div className="flex min-w-0 flex-col">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="font-medium">{p.name}</span>
                      {!p.in_stock && <Badge variant="destructive">Out of stock</Badge>}
                      {!p.active && <Badge>Hidden</Badge>}
                    </div>
                    <span className="text-[13px] text-muted-foreground">
                      {p.pack_size && `${p.pack_size} · `}
                      <span className="tabular-nums">{p.rate}</span>
                    </span>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {p.active && (
                      <Button size="sm" variant="outline" disabled={stockId === p.id} onClick={() => void toggleStock(p)}>
                        {p.in_stock ? "Mark out of stock" : "Mark in stock"}
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setEditing({ product: p })} aria-label={`Change ${p.name}`}>
                      <Pencil aria-hidden /> Change
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <ProductDialog
        key={editing ? (editing.product?.id ?? "new") : "closed"}
        editing={editing}
        onClose={() => setEditing(null)}
        onSaved={(p, message) => {
          replace(p);
          setEditing(null);
          toast.success(message);
        }}
        onAuthError={onAuthError}
      />
    </div>
  );
}
