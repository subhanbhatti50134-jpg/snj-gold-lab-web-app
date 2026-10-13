import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api, money, type CurrentUser } from "../api";
import type {MetalRate, Party, Product, RateUnit} from "../types";
import { Empty, Field } from "../ui";

const GRAMS_PER_TOLA = 11.6638;

const UNITS: { value: RateUnit; label: string }[] = [
  { value: "tola", label: "Tola" },
  { value: "gram", label: "Gram" },
  { value: "kilogram", label: "Kilogram" }
];

type Kind = "purchase" | "sale";

const blank = (location: string) => ({
  product_id: "",
  party_id: "",
  gross_weight_grams: "",
  net_weight_grams: "",
  deduction_grams: "0",
  purity: "99.99",
  rate_per_gram: "",
  rate_unit: "tola" as RateUnit,
  charges: "0",
  amount_paid: "0",
  payment_method: "cash",
  location,
  notes: "",
  transaction_date: new Date().toISOString().slice(0, 10)
});

export default function PurchaseSalePage({
  kind,
  user,
  fail,
  notice,
  refreshKey,
  goTo
}: {
  kind: Kind;
  user: CurrentUser;
  fail: (e: unknown) => void;
  notice: (m: string) => void;
  refreshKey: number;
  goTo: (page: string) => void;
}) {
  const [products, setProducts] = useState<Product[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [rates, setRates] = useState<MetalRate[]>([]);
  const [form, setForm] = useState(blank("Main Store"));
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      api<Product[]>("/api/products?limit=1000"),
      api<Party[]>("/api/parties?include_inactive=false"),
      api<MetalRate[]>("/api/rates"),
      api<{ default_location: string }>("/api/settings")
    ])
      .then(([prods, pars, rt, settings]) => {
        if (cancelled) return;
        if (prods.status === "fulfilled") setProducts(prods.value);
        else fail(prods.reason);
        if (pars.status === "fulfilled") setParties(pars.value);
        else fail(pars.reason);
        if (rt.status === "fulfilled") setRates(rt.value);
        else fail(rt.reason);
        if (settings.status === "fulfilled") {
          setForm(f => ({ ...f, location: settings.value.default_location }));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey]);

  const selectedProduct = products.find(
    p => p.id === Number(form.product_id)
  );

  // Suggested rate: the entered value expressed in the chosen unit.
  const suggestedRate = selectedProduct
    ? rates
        .filter(
          r =>
            r.active &&
            r.metal === selectedProduct.metal &&
            Number(r.purity) === Number(selectedProduct.purity)
        )
        .map(r =>
          (Number(r.rate_per_gram) *
            (form.rate_unit === "tola"
              ? GRAMS_PER_TOLA
              : form.rate_unit === "kilogram"
                ? 1000
                : 1)) /
          (r.unit === "tola"
            ? GRAMS_PER_TOLA
            : r.unit === "kilogram"
              ? 1000
              : 1)
        )[0]
    : undefined;

  const gross = Number(form.gross_weight_grams || 0);
  const deduction = Number(form.deduction_grams || 0);
  const net = Number(form.net_weight_grams || 0);
  const rate = Number(form.rate_per_gram || suggestedRate || 0);
  const charges = Number(form.charges || 0);
  const purity = Number(form.purity || 0);

  const factor =
    form.rate_unit === "tola"
      ? GRAMS_PER_TOLA
      : form.rate_unit === "kilogram"
        ? 1000
        : 1;

  const estimatedTotal =
    net > 0 && rate > 0
      ? (net * (rate / factor) * purity) / 100 + charges
      : 0;

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (net <= 0 || gross <= 0) {
      fail(new Error("Gross aur net weight zero se zyada honi chahiye."));
      return;
    }

    if (net + deduction > gross + 0.0001) {
      fail(
        new Error(
          "Net weight aur deduction ka total gross weight se zyada nahi ho sakta."
        )
      );
      return;
    }

    setSaving(true);

    const payload: Record<string, unknown> = {
      product_id: Number(form.product_id),
      quantity_grams: net,
      gross_weight_grams: gross,
      net_weight_grams: net,
      deduction_grams: deduction,
      purity,
      charges: Number(form.charges || 0),
      amount_paid: Number(form.amount_paid || 0),
      payment_method: form.payment_method,
      location: form.location,
      notes: form.notes,
      transaction_date: form.transaction_date
    };

    if (form.party_id) payload.party_id = Number(form.party_id);

    if (form.rate_per_gram) {
      payload.rate_per_gram = Number(form.rate_per_gram);
      payload.rate_unit = form.rate_unit;
    }

    try {
      await api(`/api/${kind === "purchase" ? "purchases" : "sales"}`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      notice(
        kind === "purchase"
          ? "Purchase save ho gayi. Stock barh gaya."
          : "Sale save ho gayi. Stock kam hua."
      );
      setForm(blank(form.location));
      goTo("Transactions");
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  const activeProducts = products.filter(p => p.active);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{kind === "purchase" ? "Record purchase" : "Record sale"}</h2>
          <p>
            {kind === "purchase"
              ? "A successful purchase increases stock."
              : "The backend validates available stock before accepting a sale."}
          </p>
        </div>
      </div>

      {!activeProducts.length && !loading && (
        <p className="hint">
          Pehle Products page se product create karein.
        </p>
      )}

      <form className="form-grid" onSubmit={submit}>
        <Field label="Product">
          <select
            required
            value={form.product_id}
            onChange={e => {
              const product = products.find(
                p => p.id === Number(e.target.value)
              );
              setForm({
                ...form,
                product_id: e.target.value,
                purity: product ? String(product.purity) : form.purity
              });
            }}
          >
            <option value="">Select product</option>
            {activeProducts.map(p => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
        </Field>

        <Field
          label={
            kind === "purchase" ? "Supplier (optional)" : "Customer (optional)"
          }
        >
          <select
            value={form.party_id}
            onChange={e => setForm({ ...form, party_id: e.target.value })}
          >
            <option value="">No linked party</option>
            {parties
              .filter(p => kind === "purchase" || p.kind !== "supplier")
              .map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.kind})
                </option>
              ))}
          </select>
        </Field>

        <Field label="Gross weight (g)">
          <input
            required
            type="number"
            min="0.001"
            step="0.001"
            value={form.gross_weight_grams}
            onChange={e =>
              setForm({
                ...form,
                gross_weight_grams: e.target.value,
                net_weight_grams: form.net_weight_grams || e.target.value
              })
            }
          />
        </Field>

        <Field label="Deduction (g)">
          <input
            type="number"
            min="0"
            step="0.001"
            value={form.deduction_grams}
            onChange={e => {
              const value = Number(e.target.value || 0);
              setForm({
                ...form,
                deduction_grams: e.target.value,
                net_weight_grams: String(Math.max(0, gross - value))
              });
            }}
          />
        </Field>

        <Field label="Net weight (g)">
          <input
            required
            type="number"
            min="0.001"
            step="0.001"
            value={form.net_weight_grams}
            onChange={e =>
              setForm({ ...form, net_weight_grams: e.target.value })
            }
          />
        </Field>

        <Field label="Purity (%)">
          <input
            required
            type="number"
            min="0.01"
            max="100"
            step="0.01"
            value={form.purity}
            onChange={e => setForm({ ...form, purity: e.target.value })}
          />
        </Field>

        <Field
          label={
            suggestedRate !== undefined
              ? `Rate per ${form.rate_unit} (active: ~${money(suggestedRate)})`
              : `Rate per ${form.rate_unit} (override, optional)`
          }
        >
          <input
            type="number"
            min="0.01"
            step="0.01"
            placeholder={
              suggestedRate !== undefined
                ? String(Math.round(suggestedRate * 100) / 100)
                : "Use matching active rate"
            }
            value={form.rate_per_gram}
            onChange={e =>
              setForm({ ...form, rate_per_gram: e.target.value })
            }
          />
        </Field>

        <Field label="Rate unit">
          <select
            value={form.rate_unit}
            onChange={e =>
              setForm({ ...form, rate_unit: e.target.value as RateUnit })
            }
          >
            {UNITS.map(unit => (
              <option key={unit.value} value={unit.value}>
                Per {unit.label.toLowerCase()}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Charges (PKR)">
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.charges}
            onChange={e => setForm({ ...form, charges: e.target.value })}
          />
        </Field>

        <Field label="Amount paid now (PKR)">
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.amount_paid}
            onChange={e => setForm({ ...form, amount_paid: e.target.value })}
          />
        </Field>

        <Field label="Payment method">
          <select
            value={form.payment_method}
            onChange={e =>
              setForm({ ...form, payment_method: e.target.value })
            }
          >
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="other">Other</option>
          </select>
        </Field>

        <Field label="Transaction date">
          <input
            required
            type="date"
            value={form.transaction_date}
            onChange={e =>
              setForm({ ...form, transaction_date: e.target.value })
            }
          />
        </Field>

        <Field label="Stock location">
          <input
            required
            value={form.location}
            onChange={e => setForm({ ...form, location: e.target.value })}
          />
        </Field>

        <Field label="Notes">
          <textarea
            rows={3}
            value={form.notes}
            onChange={e => setForm({ ...form, notes: e.target.value })}
          />
        </Field>

        <div className="form-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => setForm(blank(form.location))}
          >
            Clear
          </button>
          <button
            type="submit"
            className="primary-button"
            disabled={saving || !activeProducts.length}
          >
            <Plus size={16} />
            {saving
              ? "Saving…"
              : estimatedTotal > 0
                ? `Save ${kind} · ${money(estimatedTotal)}`
                : `Save ${kind}`}
          </button>
        </div>

        <p className="security-note">
          Total hamesha backend calculate karta hai; yeh sirf ek estimate
          hai. Rate ki jagah khali chhoren to matching active verified rate
          apne aap use hogi.
        </p>
      </form>
    </section>
  );
}
