import { useEffect, useState, type FormEvent } from "react";
import { api, atLeast, type CurrentUser } from "../api";
import type {InventoryRow, Product, Transaction} from "../types";
import { Empty, Field, MetalTag, PanelHeading, pretty } from "../ui";

type Tab = "return" | "adjustment" | "transfer";

export default function MovementsPage({
  user,
  fail,
  notice,
  refreshKey,
  bump
}: {
  user: CurrentUser;
  fail: (e: unknown) => void;
  notice: (m: string) => void;
  refreshKey: number;
  bump: () => void;
}) {
  const [tab, setTab] = useState<Tab>("return");
  const [products, setProducts] = useState<Product[]>([]);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [saleId, setSaleId] = useState("");
  const [returnQty, setReturnQty] = useState("");
  const [returnNotes, setReturnNotes] = useState("");

  const [adjProductId, setAdjProductId] = useState("");
  const [adjDirection, setAdjDirection] = useState("increase");
  const [adjQty, setAdjQty] = useState("");
  const [adjLocation, setAdjLocation] = useState("Main Store");
  const [adjReason, setAdjReason] = useState("");

  const [trProductId, setTrProductId] = useState("");
  const [trQty, setTrQty] = useState("");
  const [trFrom, setTrFrom] = useState("Main Store");
  const [trTo, setTrTo] = useState("");
  const [trNotes, setTrNotes] = useState("");

  const canManage = atLeast(user, "manager");

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      api<Product[]>("/api/products?limit=1000"),
      api<InventoryRow[]>("/api/inventory"),
      api<{ default_location: string }>("/api/settings")
    ])
      .then(([prods, inv, settings]) => {
        if (cancelled) return;
        if (prods.status === "fulfilled") setProducts(prods.value);
        else fail(prods.reason);
        if (inv.status === "fulfilled") setInventory(inv.value);
        else fail(inv.reason);
        if (settings.status === "fulfilled") {
          setAdjLocation(settings.value.default_location);
          setTrFrom(settings.value.default_location);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey]);

  const activeProducts = products.filter(p => p.active);

  function balanceOf(productId: number, location: string): number {
    const row = inventory.find(
      r => r.product_id === productId && r.location === location
    );
    return Number(row?.balance_grams || 0);
  }

  async function submitReturn(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await api<Transaction>("/api/movements/sales-returns", {
        method: "POST",
        body: JSON.stringify({
          original_sale_id: Number(saleId),
          quantity_grams: Number(returnQty),
          notes: returnNotes
        })
      });
      notice(`Sales return ban gaya (${created.reference}). Stock restore ho gaya.`);
      setReturnQty("");
      setReturnNotes("");
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  async function submitAdjustment(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await api<Transaction>("/api/movements/adjustments", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(adjProductId),
          direction: adjDirection,
          quantity_grams: Number(adjQty),
          location: adjLocation,
          reason: adjReason
        })
      });
      notice(`Adjustment ban gaya (${created.reference}).`);
      setAdjQty("");
      setAdjReason("");
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  async function submitTransfer(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await api<Transaction>("/api/movements/transfers", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(trProductId),
          quantity_grams: Number(trQty),
          from_location: trFrom,
          to_location: trTo,
          notes: trNotes
        })
      });
      notice(
        `Transfer ban gaya (${created.reference}). Total stock unchanged.`
      );
      setTrQty("");
      setTrNotes("");
      setTrTo("");
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  if (!canManage) {
    return (
      <section className="panel">
        <PanelHeading
          title="Stock movements"
          subtitle="Returns, adjustments and transfers"
        />
        <Empty text="Manager or admin role chahiye yeh page use karne ke liye." />
      </section>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "return", label: "Sales return" },
    { id: "adjustment", label: "Stock adjustment" },
    { id: "transfer", label: "Stock transfer" }
  ];

  return (
    <section className="panel">
      <PanelHeading
        title="Stock movements"
        subtitle="Reversals and corrections — never delete the original record"
      />

      <div className="tab-bar" style={{ padding: "0 19px 6px" }}>
        {tabs.map(t => (
          <button
            key={t.id}
            className={`tab-button ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && <p className="hint">Loading…</p>}

      {tab === "return" && (
        <form className="form-grid" onSubmit={submitReturn}>
          <Field label="Original sale ID">
            <input
              required
              type="number"
              min="1"
              placeholder="e.g. 42"
              value={saleId}
              onChange={e => setSaleId(e.target.value)}
            />
          </Field>
          <Field label="Quantity returned (g)">
            <input
              required
              type="number"
              min="0.001"
              step="0.001"
              value={returnQty}
              onChange={e => setReturnQty(e.target.value)}
            />
          </Field>
          <Field label="Notes">
            <textarea
              rows={3}
              value={returnNotes}
              onChange={e => setReturnNotes(e.target.value)}
            />
          </Field>
          <div className="form-actions">
            <button
              type="submit"
              className="primary-button"
              disabled={busy || !saleId || !returnQty}
            >
              {busy ? "Saving…" : "Record sales return"}
            </button>
          </div>
          <p className="security-note">
            Return kabhi customer ki receivable bhi kam karta hai — backend
            khud calculate karta hai.
          </p>
        </form>
      )}

      {tab === "adjustment" && (
        <form className="form-grid" onSubmit={submitAdjustment}>
          <Field label="Product">
            <select
              required
              value={adjProductId}
              onChange={e => setAdjProductId(e.target.value)}
            >
              <option value="">Select product</option>
              {activeProducts.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.sku})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Direction">
            <select
              value={adjDirection}
              onChange={e => setAdjDirection(e.target.value)}
            >
              <option value="increase">Increase stock</option>
              <option value="decrease">Decrease stock</option>
            </select>
          </Field>
          <Field label="Quantity (g)">
            <input
              required
              type="number"
              min="0.001"
              step="0.001"
              value={adjQty}
              onChange={e => setAdjQty(e.target.value)}
            />
          </Field>
          <Field label="Location">
            <input
              required
              value={adjLocation}
              onChange={e => setAdjLocation(e.target.value)}
            />
          </Field>
          <Field label="Reason (required)">
            <input
              required
              minLength={3}
              value={adjReason}
              onChange={e => setAdjReason(e.target.value)}
            />
          </Field>
          <div className="form-actions">
            <button
              type="submit"
              className="primary-button"
              disabled={
                busy ||
                !adjProductId ||
                !adjQty ||
                !adjReason.trim() ||
                (adjDirection === "decrease" &&
                  Number(adjQty) >
                    balanceOf(Number(adjProductId), adjLocation))
              }
            >
              {busy ? "Saving…" : "Record adjustment"}
            </button>
          </div>
          <p className="security-note">
            {adjProductId
              ? `Balance at ${adjLocation}: ${balanceOf(
                  Number(adjProductId),
                  adjLocation
                )} g. Negative stock sirf settings allow karein tab mumkin hai.`
              : "Select a product to see its current balance."}
          </p>
        </form>
      )}

      {tab === "transfer" && (
        <form className="form-grid" onSubmit={submitTransfer}>
          <Field label="Product">
            <select
              required
              value={trProductId}
              onChange={e => setTrProductId(e.target.value)}
            >
              <option value="">Select product</option>
              {activeProducts.map(p => (
                <option key={p.id} value={p.id}>
                  <MetalTag metal={p.metal} /> {p.name} ({p.sku})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Quantity (g)">
            <input
              required
              type="number"
              min="0.001"
              step="0.001"
              value={trQty}
              onChange={e => setTrQty(e.target.value)}
            />
          </Field>
          <Field label="From location">
            <input
              required
              value={trFrom}
              onChange={e => setTrFrom(e.target.value)}
            />
          </Field>
          <Field label="To location">
            <input
              required
              value={trTo}
              onChange={e => setTrTo(e.target.value)}
            />
          </Field>
          <Field label="Notes">
            <textarea
              rows={3}
              value={trNotes}
              onChange={e => setTrNotes(e.target.value)}
            />
          </Field>
          <div className="form-actions">
            <button
              type="submit"
              className="primary-button"
              disabled={
                busy ||
                !trProductId ||
                !trQty ||
                !trTo.trim() ||
                trTo.trim() === trFrom.trim() ||
                (Number(trQty) > balanceOf(Number(trProductId), trFrom))
              }
            >
              {busy ? "Saving…" : "Record transfer"}
            </button>
          </div>
          <p className="security-note">
            {trProductId
              ? `Balance at ${trFrom}: ${balanceOf(
                  Number(trProductId),
                  trFrom
                )} g. Transfer total stock ko nahi badalta.`
              : `${pretty(trFrom)} se doosri location par stock move karein.`}
          </p>
        </form>
      )}
    </section>
  );
}
