import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  api,
  atLeast,
  newIdempotencyKey,
  type CurrentUser
} from "../api";
import type { AppSettings, InventoryRow, Product } from "../types";
import { Empty, Field, MetalTag, Modal, PanelHeading } from "../ui";

export default function InventoryPage({
  user,
  fail,
  notice,
  refreshKey
}: {
  user: CurrentUser;
  fail: (e: unknown) => void;
  notice: (m: string) => void;
  refreshKey: number;
}) {
  const [rows, setRows] = useState<InventoryRow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [localKey, setLocalKey] = useState(0);

  const [stockInRow, setStockInRow] = useState<InventoryRow | null>(null);
  const [stockForm, setStockForm] = useState({
    qty: "",
    rate: "",
    unit: "gram",
    supplier: "",
    paid: "",
    method: "cash"
  });
  const [adjustRow, setAdjustRow] = useState<InventoryRow | null>(null);
  const [adjForm, setAdjForm] = useState({
    direction: "decrease",
    quantity: "",
    reason: ""
  });
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    sku: "",
    purity: "",
    active: true
  });
  const [saving, setSaving] = useState(false);

  const canOperate = atLeast(user, "operator");
  const canManage = atLeast(user, "manager");

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      api<InventoryRow[]>("/api/inventory"),
      api<Product[]>("/api/products?limit=1000"),
      api<AppSettings>("/api/settings")
    ])
      .then(([inv, prods, set]) => {
        if (cancelled) return;
        if (inv.status === "fulfilled") setRows(inv.value);
        else fail(inv.reason);
        if (prods.status === "fulfilled") setProducts(prods.value);
        else fail(prods.reason);
        if (set.status === "fulfilled") setSettings(set.value);
        else fail(set.reason);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey, localKey]);

  const threshold = useMemo(() => {
    const value = Number(settings?.low_stock_threshold || 0);
    return Number.isFinite(value) && value > 0 ? value : 0;
  }, [settings]);

  const productMap = useMemo(
    () => new Map(products.map(p => [p.id, p])),
    [products]
  );

  const locations = useMemo(
    () => [...new Set(rows.map(r => r.location))].sort(),
    [rows]
  );

  const filtered = rows.filter(row => {
    const product = productMap.get(row.product_id);
    const haystack = `${product?.name || ""} ${product?.sku || ""} ${row.location}`;

    return (
      haystack.toLowerCase().includes(search.toLowerCase()) &&
      (!location || row.location === location)
    );
  });

  const lowCount =
    threshold > 0
      ? filtered.filter(row => Number(row.balance_grams) <= threshold).length
      : 0;

  const bump = () => setLocalKey(k => k + 1);

  function openStockIn(row: InventoryRow) {
    setStockForm({
      qty: "",
      rate: "",
      unit: settings?.default_rate_unit || "gram",
      supplier: "",
      paid: "",
      method: "cash"
    });
    setStockInRow(row);
  }

  function openAdjust(row: InventoryRow) {
    setAdjForm({ direction: "decrease", quantity: "", reason: "" });
    setAdjustRow(row);
  }

  function openEdit(product: Product) {
    setEditForm({
      name: product.name,
      sku: product.sku,
      purity: String(product.purity),
      active: product.active
    });
    setEditProduct(product);
  }

  async function submitStockIn(e: FormEvent) {
    e.preventDefault();
    if (!stockInRow) return;
    const product = productMap.get(stockInRow.product_id);
    const weight = Number(stockForm.qty);
    const rate = Number(stockForm.rate);
    if (!(weight > 0) || !(rate > 0)) {
      fail("Quantity aur rate dono 0 se zyada hone chahiye.");
      return;
    }
    setSaving(true);
    try {
      await api("/api/purchases", {
        method: "POST",
        idempotencyKey: newIdempotencyKey(),
        body: JSON.stringify({
          product_id: stockInRow.product_id,
          quantity_grams: weight,
          gross_weight_grams: weight,
          net_weight_grams: weight,
          deduction_grams: 0,
          purity: product ? Number(product.purity) : 0,
          rate_per_gram: rate,
          rate_unit: stockForm.unit,
          charges: 0,
          amount_paid: Number(stockForm.paid) || 0,
          payment_method: stockForm.method,
          party_name: stockForm.supplier.trim(),
          location: stockInRow.location,
          transaction_date: new Date().toISOString().slice(0, 10)
        })
      });
      notice(
        `Stock in recorded: +${weight} g ${
          product?.name || "stock"
        } at ${stockInRow.location}.`
      );
      setStockInRow(null);
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  async function submitAdjust(e: FormEvent) {
    e.preventDefault();
    if (!adjustRow) return;
    const amount = Number(adjForm.quantity);
    if (!(amount > 0)) {
      fail("Quantity 0 se zyada honi chahiye.");
      return;
    }
    if (!adjForm.reason.trim()) {
      fail("Reason zaroori hai — correction audit mein jata hai.");
      return;
    }
    setSaving(true);
    try {
      await api("/api/movements/adjustments", {
        method: "POST",
        body: JSON.stringify({
          product_id: adjustRow.product_id,
          direction: adjForm.direction,
          quantity_grams: amount,
          location: adjustRow.location,
          reason: adjForm.reason.trim()
        })
      });
      notice(
        `${adjForm.direction === "increase" ? "Increased" : "Decreased"} ${
          adjustRow.location
        } by ${amount} g (adjustment entry recorded).`
      );
      setAdjustRow(null);
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  async function submitEdit(e: FormEvent) {
    e.preventDefault();
    if (!editProduct) return;
    const purity = Number(editForm.purity);
    if (!editForm.name.trim() || !editForm.sku.trim()) {
      fail("Name aur SKU zaroori hain.");
      return;
    }
    if (!(purity >= 0 && purity <= 100)) {
      fail("Purity 0 se 100 ke darmiyan honi chahiye.");
      return;
    }
    setSaving(true);
    try {
      await api(`/api/products/${editProduct.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editForm.name.trim(),
          sku: editForm.sku.trim(),
          purity,
          active: editForm.active
        })
      });
      notice(`Product ${editForm.name.trim()} updated.`);
      setEditProduct(null);
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Stock on hand"
        subtitle="Current balance by product and location, calculated from stock movements"
        search={search}
        setSearch={setSearch}
        action={
          <select
            value={location}
            onChange={e => setLocation(e.target.value)}
            style={{
              padding: "7px 9px",
              border: "1px solid var(--border)",
              borderRadius: 7,
              fontSize: 10,
              color: "var(--text-2)"
            }}
          >
            <option value="">All locations</option>
            {locations.map(loc => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>
        }
      />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              <th>Location</th>
              <th>Balance</th>
              <th>Metal</th>
              <th>Purity</th>
              {(canOperate || canManage) && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => {
              const product = productMap.get(row.product_id);
              return (
                <tr key={`${row.product_id}-${row.location}-${i}`}>
                  <td>
                    <b>{product?.name || `Product #${row.product_id}`}</b>
                  </td>
                  <td>{product?.sku || "—"}</td>
                  <td>{row.location}</td>
                  <td>
                    <b>{row.balance_grams} g</b>
                    {threshold > 0 &&
                      Number(row.balance_grams) <= threshold && (
                        <span
                          className="kind purchase"
                          style={{ marginLeft: 6 }}
                          title={`At or below the ${threshold} g low-stock threshold`}
                        >
                          Low
                        </span>
                      )}
                  </td>
                  <td>
                    <MetalTag metal={product?.metal || "other"} />
                  </td>
                  <td>{product ? `${product.purity}%` : "—"}</td>
                  {(canOperate || canManage) && (
                    <td>
                      <div style={{ display: "flex", gap: 10 }}>
                        {canOperate && (
                          <button
                            className="text-button"
                            onClick={() => openStockIn(row)}
                          >
                            Stock in
                          </button>
                        )}
                        {canManage && (
                          <>
                            <button
                              className="text-button"
                              onClick={() => openAdjust(row)}
                            >
                              Adjust
                            </button>
                            {product && (
                              <button
                                className="text-button"
                                onClick={() => openEdit(product)}
                              >
                                Edit
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {!filtered.length && !loading && (
          <Empty text="No inventory rows found. Record a purchase to add stock." />
        )}
      </div>
      {threshold > 0 && lowCount > 0 && (
        <p className="hint" style={{ padding: "0 19px 16px" }}>
          {lowCount} of {filtered.length} rows at or below the {threshold} g
          low-stock threshold (set in Settings → Inventory & trading).
        </p>
      )}

      {stockInRow && (
        <Modal
          title="Stock in (purchase)"
          subtitle={`${productMap.get(stockInRow.product_id)?.name || ""} · ${
            stockInRow.location
          } · current ${stockInRow.balance_grams} g`}
          onClose={() => setStockInRow(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitStockIn}>
            <Field label="Quantity (grams)">
              <input
                type="number"
                step="any"
                min="0"
                required
                value={stockForm.qty}
                onChange={e =>
                  setStockForm({ ...stockForm, qty: e.target.value })
                }
                placeholder="e.g. 10"
              />
            </Field>
            <Field label="Rate">
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  type="number"
                  step="any"
                  min="0"
                  required
                  value={stockForm.rate}
                  onChange={e =>
                    setStockForm({ ...stockForm, rate: e.target.value })
                  }
                  placeholder="e.g. 23500"
                  style={{ flex: 1, minWidth: 0 }}
                />
                <select
                  value={stockForm.unit}
                  onChange={e =>
                    setStockForm({ ...stockForm, unit: e.target.value })
                  }
                  style={{ width: 92 }}
                >
                  <option value="gram">/ gram</option>
                  <option value="tola">/ tola</option>
                  <option value="kilogram">/ kg</option>
                </select>
              </div>
            </Field>
            <Field label="Supplier (optional)">
              <input
                value={stockForm.supplier}
                onChange={e =>
                  setStockForm({ ...stockForm, supplier: e.target.value })
                }
                placeholder="Supplier name"
              />
            </Field>
            <Field label="Pay now (optional)">
              <input
                type="number"
                step="any"
                min="0"
                value={stockForm.paid}
                onChange={e =>
                  setStockForm({ ...stockForm, paid: e.target.value })
                }
                placeholder="0 = full due"
              />
            </Field>
            <Field label="Payment method">
              <select
                value={stockForm.method}
                onChange={e =>
                  setStockForm({ ...stockForm, method: e.target.value })
                }
              >
                <option value="cash">Cash</option>
                <option value="bank_transfer">Bank transfer</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setStockInRow(null)}
              >
                Cancel
              </button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "Saving…" : "Record stock in"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {adjustRow && (
        <Modal
          title="Adjust stock (correction)"
          subtitle={`${productMap.get(adjustRow.product_id)?.name || ""} · ${
            adjustRow.location
          } · current ${adjustRow.balance_grams} g`}
          onClose={() => setAdjustRow(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitAdjust}>
            <Field label="Direction">
              <select
                value={adjForm.direction}
                onChange={e =>
                  setAdjForm({ ...adjForm, direction: e.target.value })
                }
              >
                <option value="decrease">Decrease (stock kam)</option>
                <option value="increase">Increase (stock zyada)</option>
              </select>
            </Field>
            <Field label="Quantity (grams)">
              <input
                type="number"
                step="any"
                min="0"
                required
                value={adjForm.quantity}
                onChange={e =>
                  setAdjForm({ ...adjForm, quantity: e.target.value })
                }
                placeholder="e.g. 2"
              />
            </Field>
            <Field label="Reason (audit mein jayega)">
              <textarea
                rows={3}
                required
                value={adjForm.reason}
                onChange={e =>
                  setAdjForm({ ...adjForm, reason: e.target.value })
                }
                placeholder="e.g. weighing mismatch found in weekly count"
              />
            </Field>
            <p className="security-note">
              Correction ek alag stock-adjustment entry banata hai — purana
              record delete nahi hota. Decrease available balance se zyada
              hone par 409 dega.
            </p>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setAdjustRow(null)}
              >
                Cancel
              </button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "Saving…" : "Record adjustment"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editProduct && (
        <Modal
          title="Edit product"
          subtitle={`SKU ${editProduct.sku} — changes apply to every row of this product`}
          onClose={() => setEditProduct(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitEdit}>
            <Field label="Name">
              <input
                required
                value={editForm.name}
                onChange={e =>
                  setEditForm({ ...editForm, name: e.target.value })
                }
              />
            </Field>
            <Field label="SKU">
              <input
                required
                value={editForm.sku}
                onChange={e => setEditForm({ ...editForm, sku: e.target.value })}
              />
            </Field>
            <Field label="Purity %">
              <input
                type="number"
                step="any"
                min="0"
                max="100"
                required
                value={editForm.purity}
                onChange={e =>
                  setEditForm({ ...editForm, purity: e.target.value })
                }
              />
            </Field>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 10,
                color: "var(--text-2)",
                fontWeight: 700
              }}
            >
              <input
                type="checkbox"
                checked={editForm.active}
                onChange={e =>
                  setEditForm({ ...editForm, active: e.target.checked })
                }
              />
              Active (trading ke liye available)
            </label>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setEditProduct(null)}
              >
                Cancel
              </button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "Saving…" : "Save product"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
