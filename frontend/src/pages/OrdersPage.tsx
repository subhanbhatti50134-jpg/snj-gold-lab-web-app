import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import {
  api,
  atLeast,
  money,
  newIdempotencyKey,
  qty,
  type CurrentUser
} from "../api";
import type { LayawayOrder, Party, Product } from "../types";
import { Empty, Field, Modal, PanelHeading } from "../ui";

const blankOrder = {
  party_id: "",
  party_name: "",
  description: "",
  estimated_weight_grams: "",
  agreed_rate_per_gram: "",
  advance_amount: "0",
  due_date: "",
  notes: ""
};

// Captured once at page load so render stays pure (no Date.now in render).
const TODAY = new Date().toISOString().slice(0, 10);

function dueSoon(order: LayawayOrder): boolean {
  if (!order.due_date || order.status !== "pending") return false;
  const days = Math.round(
    (Date.parse(order.due_date) - Date.parse(TODAY)) / 86_400_000
  );
  return days <= 3;
}

export default function OrdersPage({
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
  const [orders, setOrders] = useState<LayawayOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [parties, setParties] = useState<Party[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(blankOrder);
  const [saving, setSaving] = useState(false);

  const [advanceTarget, setAdvanceTarget] = useState<LayawayOrder | null>(
    null
  );
  const [advanceAmount, setAdvanceAmount] = useState("");
  const [advanceBusy, setAdvanceBusy] = useState(false);

  const [deliverTarget, setDeliverTarget] = useState<LayawayOrder | null>(
    null
  );
  const [deliverForm, setDeliverForm] = useState({
    product_id: "",
    actual_weight_grams: "",
    location: "Main Store"
  });
  const [deliverBusy, setDeliverBusy] = useState(false);

  const [editTarget, setEditTarget] = useState<LayawayOrder | null>(null);
  const [editForm, setEditForm] = useState({
    description: "",
    estimated_weight_grams: "",
    agreed_rate_per_gram: "",
    due_date: "",
    notes: ""
  });
  const [editBusy, setEditBusy] = useState(false);

  const [cancelTarget, setCancelTarget] = useState<LayawayOrder | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelBusy, setCancelBusy] = useState(false);

  const canOperate = atLeast(user, "operator");
  const canManage = atLeast(user, "manager");

  const createTotal =
    Number(form.estimated_weight_grams || 0) *
    Number(form.agreed_rate_per_gram || 0);
  const createAdvance = Number(form.advance_amount || 0);
  const createInvalid =
    !form.description.trim() ||
    !(Number(form.estimated_weight_grams) > 0) ||
    !(Number(form.agreed_rate_per_gram) > 0) ||
    (form.party_id === "" && !form.party_name.trim()) ||
    createAdvance > createTotal;

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      api<Party[]>("/api/parties?limit=1000"),
      api<Product[]>("/api/products?limit=1000")
    ])
      .then(([partyRows, productRows]) => {
        if (cancelled) return;
        if (partyRows.status === "fulfilled")
          setParties(partyRows.value.filter(p => p.active));
        else fail(partyRows.reason);
        if (productRows.status === "fulfilled")
          setProducts(productRows.value.filter(p => p.active));
        else fail(productRows.reason);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey]);

  useEffect(() => {
    let cancelled = false;

    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (search.trim()) params.set("search", search.trim());

    api<LayawayOrder[]>(`/api/orders?${params.toString()}`)
      .then(rows => {
        if (!cancelled) setOrders(rows);
      })
      .catch(error => {
        if (!cancelled) fail(error);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey, search, statusFilter]);

  function openCreate() {
    setForm(blankOrder);
    setShowCreate(true);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (createInvalid || saving) return;
    setSaving(true);
    try {
      await api("/api/orders", {
        method: "POST",
        idempotencyKey: newIdempotencyKey(),
        body: JSON.stringify({
          party_id: form.party_id ? Number(form.party_id) : null,
          party_name: form.party_name.trim(),
          description: form.description.trim(),
          estimated_weight_grams: Number(form.estimated_weight_grams),
          agreed_rate_per_gram: Number(form.agreed_rate_per_gram),
          advance_amount: Number(form.advance_amount || 0),
          due_date: form.due_date || null,
          notes: form.notes.trim()
        })
      });
      notice("Bayana order create ho gaya.");
      setShowCreate(false);
      setForm(blankOrder);
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  async function submitAdvance(event: FormEvent) {
    event.preventDefault();
    if (!advanceTarget || advanceBusy) return;
    setAdvanceBusy(true);
    try {
      await api(`/api/orders/${advanceTarget.id}/advance`, {
        method: "POST",
        idempotencyKey: newIdempotencyKey(),
        body: JSON.stringify({ amount: Number(advanceAmount) })
      });
      notice("Advance record ho gaya.");
      setAdvanceTarget(null);
      setAdvanceAmount("");
    } catch (error) {
      fail(error);
    } finally {
      setAdvanceBusy(false);
    }
  }

  async function submitDeliver(event: FormEvent) {
    event.preventDefault();
    if (!deliverTarget || deliverBusy) return;
    setDeliverBusy(true);
    try {
      const sale = await api<{ reference: string }>(
        `/api/orders/${deliverTarget.id}/deliver`,
        {
          method: "POST",
          idempotencyKey: newIdempotencyKey(),
          body: JSON.stringify({
            product_id: Number(deliverForm.product_id),
            actual_weight_grams: deliverForm.actual_weight_grams
              ? Number(deliverForm.actual_weight_grams)
              : null,
            location: deliverForm.location.trim() || "Main Store"
          })
        }
      );
      notice(`Delivered: sale ${sale.reference} bana.`);
      setDeliverTarget(null);
    } catch (error) {
      fail(error);
    } finally {
      setDeliverBusy(false);
    }
  }

  function openEdit(order: LayawayOrder) {
    setEditTarget(order);
    setEditForm({
      description: order.description,
      estimated_weight_grams: String(order.estimated_weight_grams),
      agreed_rate_per_gram: String(order.agreed_rate_per_gram),
      due_date: order.due_date ?? "",
      notes: order.notes
    });
  }

  async function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!editTarget || editBusy) return;
    setEditBusy(true);
    try {
      await api(`/api/orders/${editTarget.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          description: editForm.description.trim(),
          estimated_weight_grams: Number(editForm.estimated_weight_grams),
          agreed_rate_per_gram: Number(editForm.agreed_rate_per_gram),
          due_date: editForm.due_date || null,
          notes: editForm.notes.trim()
        })
      });
      notice("Order update ho gaya.");
      setEditTarget(null);
    } catch (error) {
      fail(error);
    } finally {
      setEditBusy(false);
    }
  }

  async function submitCancel(event: FormEvent) {
    event.preventDefault();
    if (!cancelTarget || cancelBusy) return;
    setCancelBusy(true);
    try {
      await api(`/api/orders/${cancelTarget.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: cancelReason.trim() })
      });
      notice("Order cancel ho gaya.");
      setCancelTarget(null);
      setCancelReason("");
    } catch (error) {
      fail(error);
    } finally {
      setCancelBusy(false);
    }
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Bayana orders"
        subtitle="Advance bookings — rate locked now, delivered later"
        search={search}
        setSearch={setSearch}
        action={
          <div className="panel-tools">
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              style={{
                padding: "7px 9px",
                border: "1px solid var(--border)",
                borderRadius: 7,
                fontSize: 10,
                color: "var(--text-2)"
              }}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="delivered">Delivered</option>
              <option value="cancelled">Cancelled</option>
            </select>
            {canOperate && (
              <button className="primary-button" onClick={openCreate}>
                <Plus size={16} /> New order
              </button>
            )}
          </div>
        }
      />

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Ref</th>
              <th>Party</th>
              <th>Item</th>
              <th>Weight</th>
              <th>Rate/g</th>
              <th>Total</th>
              <th>Advance</th>
              <th>Balance</th>
              <th>Due</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(order => (
              <tr key={order.id}>
                <td>{order.reference}</td>
                <td>{order.party_name || "—"}</td>
                <td title={order.notes || undefined}>{order.description}</td>
                <td>{qty(order.estimated_weight_grams)} g</td>
                <td>{money(order.agreed_rate_per_gram)}</td>
                <td>{money(order.estimated_total)}</td>
                <td>{money(order.advance_amount)}</td>
                <td className="due">
                  <b>{money(order.balance)}</b>
                </td>
                <td>
                  {order.due_date
                    ? new Date(order.due_date).toLocaleDateString()
                    : "—"}
                  {dueSoon(order) && (
                    <>
                      <br />
                      <small className="hint">due soon</small>
                    </>
                  )}
                </td>
                <td>
                  <span className={`kind ${order.status}`}>{order.status}</span>
                </td>
                <td>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {order.status === "pending" && canOperate && (
                      <>
                        <button
                          className="text-button"
                          onClick={() => {
                            setAdvanceTarget(order);
                            setAdvanceAmount("");
                          }}
                        >
                          Advance
                        </button>
                        <button
                          className="text-button"
                          onClick={() => {
                            setDeliverTarget(order);
                            setDeliverForm({
                              product_id: "",
                              actual_weight_grams: String(
                                order.estimated_weight_grams
                              ),
                              location: "Main Store"
                            });
                          }}
                        >
                          Deliver
                        </button>
                      </>
                    )}
                    {order.status === "pending" && canManage && (
                      <>
                        <button
                          className="text-button"
                          onClick={() => openEdit(order)}
                        >
                          Edit
                        </button>
                        <button
                          className="text-button danger"
                          onClick={() => {
                            setCancelTarget(order);
                            setCancelReason("");
                          }}
                        >
                          Cancel
                        </button>
                      </>
                    )}
                    {order.status === "delivered" && order.sale_id && (
                      <small className="hint">Sale #{order.sale_id}</small>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!orders.length && !loading && (
          <Empty
            text={
              search || statusFilter
                ? "No orders match these filters."
                : "No bayana orders yet — create one with New order."
            }
          />
        )}
      </div>

      {showCreate && (
        <Modal
          title="New bayana order"
          subtitle="Book the item, lock the rate, collect the advance"
          onClose={() => setShowCreate(false)}
        >
          <form className="form-grid modal-form" onSubmit={submitCreate}>
            <Field label="Saved party (optional)">
              <select
                value={form.party_id}
                onChange={e => setForm({ ...form, party_id: e.target.value })}
              >
                <option value="">Walk-in customer</option>
                {parties.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            {form.party_id === "" && (
              <Field label="Walk-in name">
                <input
                  value={form.party_name}
                  onChange={e =>
                    setForm({ ...form, party_name: e.target.value })
                  }
                  placeholder="Customer ka naam"
                />
              </Field>
            )}
            <Field label="Item description">
              <input
                value={form.description}
                onChange={e =>
                  setForm({ ...form, description: e.target.value })
                }
                placeholder="e.g. 22K necklace with meena"
              />
            </Field>
            <Field label="Estimated weight (g)">
              <input
                type="number"
                min="0"
                step="0.0001"
                value={form.estimated_weight_grams}
                onChange={e =>
                  setForm({ ...form, estimated_weight_grams: e.target.value })
                }
              />
            </Field>
            <Field label="Agreed rate (PKR/g)">
              <input
                type="number"
                min="0"
                step="0.0001"
                value={form.agreed_rate_per_gram}
                onChange={e =>
                  setForm({ ...form, agreed_rate_per_gram: e.target.value })
                }
              />
            </Field>
            <Field label="Advance now (PKR)">
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.advance_amount}
                onChange={e =>
                  setForm({ ...form, advance_amount: e.target.value })
                }
              />
            </Field>
            <Field label="Expected delivery">
              <input
                type="date"
                value={form.due_date}
                onChange={e => setForm({ ...form, due_date: e.target.value })}
              />
            </Field>
            <Field label="Notes (optional)">
              <input
                value={form.notes}
                onChange={e => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
            <p className="hint" style={{ gridColumn: "1 / -1" }}>
              Estimated total:{" "}
              <b>
                {createTotal > 0 ? money(createTotal) : "—"}
              </b>{" "}
              · balance on delivery:{" "}
              <b>
                {createTotal > 0
                  ? money(Math.max(0, createTotal - createAdvance))
                  : "—"}
              </b>
              {createAdvance > createTotal && createTotal >= 0 && (
                <span style={{ color: "#c05640" }}>
                  {" "}
                  · advance estimated total se zyada hai
                </span>
              )}
            </p>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={saving || createInvalid}
              >
                {saving ? "Saving…" : "Create order"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {advanceTarget && (
        <Modal
          title={`Advance · ${advanceTarget.reference}`}
          subtitle={`${advanceTarget.description} · current advance ${money(
            advanceTarget.advance_amount
          )} of ${money(advanceTarget.estimated_total)}`}
          onClose={() => setAdvanceTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitAdvance}>
            <Field label="Advance amount (PKR)">
              <input
                type="number"
                min="0"
                step="0.01"
                value={advanceAmount}
                autoFocus
                onChange={e => setAdvanceAmount(e.target.value)}
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setAdvanceTarget(null)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={advanceBusy || !(Number(advanceAmount) > 0)}
              >
                {advanceBusy ? "Saving…" : "Record advance"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {deliverTarget && (
        <Modal
          title={`Deliver · ${deliverTarget.reference}`}
          subtitle={`${deliverTarget.description} · agreed rate ${money(
            deliverTarget.agreed_rate_per_gram
          )}/g · advance ${money(deliverTarget.advance_amount)}`}
          onClose={() => setDeliverTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitDeliver}>
            <Field label="Product">
              <select
                value={deliverForm.product_id}
                onChange={e =>
                  setDeliverForm({
                    ...deliverForm,
                    product_id: e.target.value
                  })
                }
              >
                <option value="">Select product…</option>
                {products.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Actual weight (g)">
              <input
                type="number"
                min="0"
                step="0.0001"
                value={deliverForm.actual_weight_grams}
                onChange={e =>
                  setDeliverForm({
                    ...deliverForm,
                    actual_weight_grams: e.target.value
                  })
                }
              />
            </Field>
            <Field label="Stock location">
              <input
                value={deliverForm.location}
                onChange={e =>
                  setDeliverForm({ ...deliverForm, location: e.target.value })
                }
              />
            </Field>
            {(() => {
              const weight = Number(deliverForm.actual_weight_grams || 0);
              const total = weight * Number(deliverTarget.agreed_rate_per_gram);
              const advance = Number(deliverTarget.advance_amount);
              const paid = Math.min(advance, total);
              const due = Math.max(0, total - advance);
              return (
                <p className="hint" style={{ gridColumn: "1 / -1" }}>
                  Sale total: <b>{money(total)}</b> · advance applied:{" "}
                  <b>{money(paid)}</b> · due after delivery:{" "}
                  <b>{money(due)}</b>
                </p>
              );
            })()}
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setDeliverTarget(null)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={deliverBusy || !deliverForm.product_id}
              >
                {deliverBusy ? "Delivering…" : "Deliver & create sale"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editTarget && (
        <Modal
          title={`Edit · ${editTarget.reference}`}
          subtitle="Pending orders only — advance stays as recorded"
          onClose={() => setEditTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitEdit}>
            <Field label="Item description">
              <input
                value={editForm.description}
                onChange={e =>
                  setEditForm({ ...editForm, description: e.target.value })
                }
              />
            </Field>
            <Field label="Estimated weight (g)">
              <input
                type="number"
                min="0"
                step="0.0001"
                value={editForm.estimated_weight_grams}
                onChange={e =>
                  setEditForm({
                    ...editForm,
                    estimated_weight_grams: e.target.value
                  })
                }
              />
            </Field>
            <Field label="Agreed rate (PKR/g)">
              <input
                type="number"
                min="0"
                step="0.0001"
                value={editForm.agreed_rate_per_gram}
                onChange={e =>
                  setEditForm({
                    ...editForm,
                    agreed_rate_per_gram: e.target.value
                  })
                }
              />
            </Field>
            <Field label="Expected delivery">
              <input
                type="date"
                value={editForm.due_date}
                onChange={e =>
                  setEditForm({ ...editForm, due_date: e.target.value })
                }
              />
            </Field>
            <Field label="Notes">
              <input
                value={editForm.notes}
                onChange={e =>
                  setEditForm({ ...editForm, notes: e.target.value })
                }
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setEditTarget(null)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={
                  editBusy ||
                  !editForm.description.trim() ||
                  !(Number(editForm.estimated_weight_grams) > 0) ||
                  !(Number(editForm.agreed_rate_per_gram) > 0)
                }
              >
                {editBusy ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {cancelTarget && (
        <Modal
          title={`Cancel · ${cancelTarget.reference}`}
          subtitle={`${cancelTarget.description} · advance held ${money(
            cancelTarget.advance_amount
          )} (refund manually and note it in audit)`}
          onClose={() => setCancelTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitCancel}>
            <Field label="Reason (optional)">
              <input
                value={cancelReason}
                autoFocus
                onChange={e => setCancelReason(e.target.value)}
                placeholder="e.g. Customer changed mind"
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setCancelTarget(null)}
              >
                Keep order
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={cancelBusy}
              >
                {cancelBusy ? "Cancelling…" : "Cancel order"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
