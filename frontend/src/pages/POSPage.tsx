import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, money, newIdempotencyKey, qty, type CurrentUser } from "../api";
import {
  allocatePayment,
  cartTotal,
  defaultRate,
  lineTotal,
  makingOf,
  money2,
  validateCart,
  type CartLine,
  type MakingChargeType
} from "../pos";
import type { InventoryRow, MetalRate, Party, Product } from "../types";
import ReceiptModal from "../ReceiptModal";
import { Empty, Field, Modal, PanelHeading } from "../ui";

interface CheckoutResult {
  sales: { id: number; reference: string }[];
  total: number;
  paid: number;
  change: number;
  due: number;
}

export default function POSPage({
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
  const [products, setProducts] = useState<Product[]>([]);
  const [rates, setRates] = useState<MetalRate[]>([]);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [location, setLocation] = useState("Main Store");
  const [customerMode, setCustomerMode] = useState<"walkin" | "existing">(
    "walkin"
  );
  const [partyId, setPartyId] = useState<number | "">("");
  const [walkinName, setWalkinName] = useState("");
  const [received, setReceived] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [notes, setNotes] = useState("");
  const [checkingOut, setCheckingOut] = useState(false);
  const [result, setResult] = useState<CheckoutResult | null>(null);
  const [receiptId, setReceiptId] = useState<number | null>(null);

  // The same key is reused if a checkout fails and is retried, so the
  // server records the sale only once. Cleared after a success.
  const checkoutKeyRef = useRef("");
  const keyCounterRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      api<Product[]>("/api/products?limit=1000"),
      api<MetalRate[]>("/api/rates?active_only=true"),
      api<InventoryRow[]>("/api/inventory"),
      api<Party[]>("/api/parties?limit=1000")
    ])
      .then(([prods, rateRows, inv, partyRows]) => {
        if (cancelled) return;
        if (prods.status === "fulfilled")
          setProducts(prods.value.filter(p => p.active));
        else fail(prods.reason);
        if (rateRows.status === "fulfilled") setRates(rateRows.value);
        else fail(rateRows.reason);
        if (inv.status === "fulfilled") setInventory(inv.value);
        else fail(inv.reason);
        if (partyRows.status === "fulfilled")
          setParties(partyRows.value.filter(p => p.active));
        else fail(partyRows.reason);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey]);

  const stockByProduct = useMemo(() => {
    const map = new Map<number, number>();
    for (const row of inventory) {
      if (row.location !== location) continue;
      map.set(
        row.product_id,
        money2((map.get(row.product_id) ?? 0) + Number(row.balance_grams))
      );
    }
    return map;
  }, [inventory, location]);

  const locations = useMemo(() => {
    const set = new Set<string>(["Main Store"]);
    for (const row of inventory) set.add(row.location);
    return [...set];
  }, [inventory]);

  const filteredProducts = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const list = needle
      ? products.filter(
          p =>
            p.name.toLowerCase().includes(needle) ||
            p.sku.toLowerCase().includes(needle) ||
            p.metal.toLowerCase().includes(needle)
        )
      : products;
    return list.slice(0, 40);
  }, [products, search]);

  const total = cartTotal(cart);
  const allocation = allocatePayment(cart, Number(received || 0));
  const cartError = validateCart(cart);

  function addProduct(product: Product) {
    const rate = defaultRate(rates, product.metal, product.purity);
    keyCounterRef.current += 1;
    setCart([
      ...cart,
      {
        key: `line-${keyCounterRef.current}`,
        product_id: product.id,
        sku: product.sku,
        name: product.name,
        metal: product.metal,
        purity: Number(product.purity),
        quantity_grams: 1,
        rate_per_gram: rate ?? 0,
        making_charge_type: "",
        making_charge_value: 0
      }
    ]);
    setSearch("");
  }

  function updateLine(key: string, patch: Partial<CartLine>) {
    setCart(cart.map(line => (line.key === key ? { ...line, ...patch } : line)));
  }

  function removeLine(key: string) {
    setCart(cart.filter(line => line.key !== key));
  }

  async function checkout(event: FormEvent) {
    event.preventDefault();
    if (cartError || checkingOut) return;

    setCheckingOut(true);

    const party =
      customerMode === "existing" && partyId !== ""
        ? parties.find(p => p.id === partyId) ?? null
        : null;

    const items = cart.map((line, index) => ({
      product_id: line.product_id,
      quantity_grams: line.quantity_grams,
      gross_weight_grams: line.quantity_grams,
      net_weight_grams: line.quantity_grams,
      deduction_grams: 0,
      purity: line.purity,
      rate_per_gram: line.rate_per_gram,
      rate_unit: "gram" as const,
      charges: 0,
      making_charge_type: line.making_charge_type,
      making_charge_value: line.making_charge_value,
      amount_paid: allocation.paidPerLine[index] ?? 0,
      payment_method: paymentMethod,
      party_id: party ? party.id : null,
      party_name: party ? party.name : walkinName.trim(),
      location,
      notes: notes.trim(),
      transaction_date: new Date().toISOString().slice(0, 10)
    }));

    try {
      // Reuse the key on a retry so a double-submit cannot sell twice.
      if (!checkoutKeyRef.current) {
        checkoutKeyRef.current = newIdempotencyKey();
      }
      const rows = await api<{ id: number; reference: string }[]>(
        "/api/sales/batch",
        {
          method: "POST",
          body: JSON.stringify({ items }),
          idempotencyKey: checkoutKeyRef.current
        }
      );
      checkoutKeyRef.current = "";
      setResult({
        sales: rows.map(r => ({ id: r.id, reference: r.reference })),
        total,
        paid: allocation.totalPaid,
        change: allocation.change,
        due: allocation.due
      });
      setCart([]);
      setReceived("");
      setNotes("");
      notice(`Sale complete: ${rows.length} item(s) sold.`);
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setCheckingOut(false);
    }
  }

  return (
    <>
      <section className="panel">
        <PanelHeading
          title="Point of sale"
          subtitle="Add items, take cash, checkout — every line becomes its own sale record"
        />

        <div
          className="form-grid"
          style={{ gridTemplateColumns: "1fr 1fr 1fr", marginBottom: 14 }}
        >
          <Field label="Stock location">
            <select
              value={location}
              onChange={e => setLocation(e.target.value)}
            >
              {locations.map(loc => (
                <option key={loc} value={loc}>
                  {loc}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Customer">
            <select
              value={customerMode}
              onChange={e => {
                const mode = e.target.value as "walkin" | "existing";
                setCustomerMode(mode);
                if (mode === "walkin") setPartyId("");
              }}
            >
              <option value="walkin">Walk-in customer</option>
              <option value="existing">Saved customer</option>
            </select>
          </Field>

          {customerMode === "walkin" ? (
            <Field label="Customer name (optional)">
              <input
                value={walkinName}
                onChange={e => setWalkinName(e.target.value)}
                placeholder="e.g. Ali Khan"
              />
            </Field>
          ) : (
            <Field label="Saved customer">
              <select
                value={partyId}
                onChange={e =>
                  setPartyId(e.target.value === "" ? "" : Number(e.target.value))
                }
              >
                <option value="">Select customer…</option>
                {parties
                  .filter(p => p.kind !== "supplier")
                  .map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </Field>
          )}
        </div>

        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1.2fr" }}>
          <div>
            <Field label="Search products (name, SKU or metal)">
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Type to find a product…"
                autoFocus
              />
            </Field>
            {loading && <p className="hint">Loading products…</p>}
            <div
              className="table-scroll"
              style={{ maxHeight: 380, marginTop: 8 }}
            >
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Stock</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map(p => {
                    const stock = stockByProduct.get(p.id) ?? 0;
                    return (
                      <tr key={p.id}>
                        <td>
                          <b>{p.name}</b>
                          <br />
                          <small className="hint">
                            {p.sku} · {p.metal} {Number(p.purity)}%
                          </small>
                        </td>
                        <td>{qty(stock)} g</td>
                        <td>
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => addProduct(p)}
                          >
                            Add
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {!filteredProducts.length && !loading && (
                <Empty text="No products match your search." />
              )}
            </div>
          </div>

          <form onSubmit={checkout}>
            <h3 style={{ marginBottom: 8 }}>
              Cart <span className="hint">({cart.length} items)</span>
            </h3>
            <div className="table-scroll" style={{ maxHeight: 300 }}>
              <table>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Weight (g)</th>
                    <th>Rate/g</th>
                    <th>Ujra</th>
                    <th>Total</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {cart.map(line => (
                    <tr key={line.key}>
                      <td>
                        {line.name}
                        <br />
                        <small className="hint">{Number(line.purity)}%</small>
                      </td>
                      <td style={{ width: 90 }}>
                        <input
                          type="number"
                          min="0"
                          step="0.0001"
                          value={line.quantity_grams}
                          onChange={e =>
                            updateLine(line.key, {
                              quantity_grams: Number(e.target.value)
                            })
                          }
                        />
                      </td>
                      <td style={{ width: 100 }}>
                        <input
                          type="number"
                          min="0"
                          step="0.0001"
                          value={line.rate_per_gram}
                          onChange={e =>
                            updateLine(line.key, {
                              rate_per_gram: Number(e.target.value)
                            })
                          }
                        />
                      </td>
                      <td style={{ width: 165 }}>
                        <div style={{ display: "flex", gap: 6 }}>
                          <select
                            value={line.making_charge_type}
                            onChange={e =>
                              updateLine(line.key, {
                                making_charge_type: e.target
                                  .value as MakingChargeType
                              })
                            }
                            style={{ flex: 1, minWidth: 0 }}
                          >
                            <option value="">No ujra</option>
                            <option value="per_gram">Rs / gram</option>
                            <option value="percent">% of metal</option>
                            <option value="fixed">Fixed</option>
                          </select>
                          {line.making_charge_type && (
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={line.making_charge_value}
                              aria-label="Making charge value"
                              onChange={e =>
                                updateLine(line.key, {
                                  making_charge_value: Number(e.target.value)
                                })
                              }
                              style={{ width: 72 }}
                            />
                          )}
                        </div>
                      </td>
                      <td>
                        {money(lineTotal(line))}
                        {makingOf(line) > 0 && (
                          <>
                            <br />
                            <small className="hint">
                              ujra {money(makingOf(line))}
                            </small>
                          </>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="text-button danger"
                          onClick={() => removeLine(line.key)}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!cart.length && (
                <Empty text="Cart is empty. Search a product and press Add." />
              )}
            </div>

            <div
              className="form-grid"
              style={{ gridTemplateColumns: "1fr 1fr", marginTop: 12 }}
            >
              <Field label="Payment method">
                <select
                  value={paymentMethod}
                  onChange={e => setPaymentMethod(e.target.value)}
                >
                  <option value="cash">Cash</option>
                  <option value="bank_transfer">Bank transfer</option>
                  <option value="other">Other</option>
                </select>
              </Field>
              <Field label="Cash received">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={received}
                  onChange={e => setReceived(e.target.value)}
                  placeholder="0"
                />
              </Field>
              <Field label="Notes (optional)">
                <input
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                />
              </Field>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  gap: 4
                }}
              >
                <div>
                  <b>Total:</b> {money(total)}
                </div>
                <div>
                  Paid: {money(allocation.totalPaid)} · Due:{" "}
                  {money(allocation.due)} · Change:{" "}
                  {money(allocation.change)}
                </div>
              </div>
            </div>

            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={
                  checkingOut ||
                  !cart.length ||
                  !!cartError ||
                  (customerMode === "existing" && partyId === "")
                }
              >
                {checkingOut
                  ? "Processing…"
                  : allocation.change > 0
                    ? `Checkout · return ${money(allocation.change)}`
                    : allocation.due > 0
                      ? `Checkout · due ${money(allocation.due)}`
                      : `Checkout · ${money(allocation.totalPaid)}`}
              </button>
            </div>
            {cartError && cart.length > 0 && (
              <p className="security-note">{cartError}</p>
            )}
            <p className="hint">
              Signed in as <b>{user.username}</b> ({user.role})
            </p>
          </form>
        </div>
      </section>

      {result && (
        <Modal
          title="Sale complete"
          subtitle="Stock updated. References for your records:"
          onClose={() => setResult(null)}
        >
          <ul style={{ margin: "8px 0", paddingLeft: 20 }}>
            {result.sales.map(sale => (
              <li
                key={sale.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12
                }}
              >
                <b>{sale.reference}</b>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setReceiptId(sale.id)}
                >
                  Receipt
                </button>
              </li>
            ))}
          </ul>
          <p>
            Total: <b>{money(result.total)}</b> · Paid:{" "}
            <b>{money(result.paid)}</b> · Change: <b>{money(result.change)}</b>{" "}
            · Due: <b>{money(result.due)}</b>
          </p>
          <div className="form-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => setResult(null)}
            >
              New sale
            </button>
          </div>
        </Modal>
      )}

      {receiptId !== null && (
        <ReceiptModal
          transactionId={receiptId}
          onClose={() => setReceiptId(null)}
        />
      )}
    </>
  );
}
