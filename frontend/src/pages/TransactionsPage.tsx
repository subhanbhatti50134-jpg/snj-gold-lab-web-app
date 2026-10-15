import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  atLeast,
  downloadCsv,
  money,
  newIdempotencyKey,
  qty,
  type CurrentUser
} from "../api";
import type {Payment, Product, Transaction} from "../types";
import ReceiptModal from "../ReceiptModal";
import {
  Empty,
  Field,
  Modal,
  PanelHeading,
  pretty,
  TransactionTable
} from "../ui";

export default function TransactionsPage({
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
  const [rows, setRows] = useState<Transaction[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [exporting, setExporting] = useState(false);
  const [status, setStatus] = useState<"active" | "cancelled" | "all">(
    "active"
  );

  const [cancelTarget, setCancelTarget] = useState<Transaction | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [includePayments, setIncludePayments] = useState(false);
  const [payTarget, setPayTarget] = useState<Transaction | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("cash");
  const [payNote, setPayNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [receiptId, setReceiptId] = useState<number | null>(null);

  // Reused if a payment submit fails and is retried, so the server
  // records the payment only once. Cleared after a success.
  const payKeyRef = useRef("");

  const canManage = atLeast(user, "manager");
  const canOperate = atLeast(user, "operator");

  const load = useCallback(async () => {
    const params = new URLSearchParams({ status, limit: "200" });
    if (kind) params.set("kind", kind);
    if (search.trim()) params.set("search", search.trim());

    try {
      const data = await api<Transaction[]>(
        `/api/transactions?${params.toString()}`
      );
      setRows(data);
    } catch (error) {
      fail(error);
    } finally {
      setLoading(false);
    }
  }, [fail, kind, search, status]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    api<Product[]>("/api/products?limit=1000")
      .then(setProducts)
      .catch(fail);
  }, [fail, refreshKey]);

  const productMap = new Map(products.map(p => [p.id, p]));

  async function submitCancel(event: FormEvent) {
    event.preventDefault();
    if (!cancelTarget) return;
    setBusy(true);

    try {
      await api(`/api/transactions/${cancelTarget.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({
          reason: cancelReason,
          include_payments: includePayments
        })
      });
      notice(
        `Transaction ${cancelTarget.reference} cancel ho gayi (reversal entries bani).`
      );
      setCancelTarget(null);
      setCancelReason("");
      setIncludePayments(false);
      bump();
      void load();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  async function openPayments(transaction: Transaction) {
    setPayTarget(transaction);
    setPayAmount("");
    setPayNote("");
    try {
      const data = await api<Payment[]>(
        `/api/transactions/${transaction.id}/payments`
      );
      setPayments(data);
    } catch (error) {
      fail(error);
      setPayments([]);
    }
  }

  async function submitPayment(event: FormEvent) {
    event.preventDefault();
    if (!payTarget) return;
    setBusy(true);

    try {
      // Reuse the key on a retry so a double-submit cannot pay twice.
      if (!payKeyRef.current) {
        payKeyRef.current = newIdempotencyKey();
      }
      await api(`/api/transactions/${payTarget.id}/payments`, {
        method: "POST",
        body: JSON.stringify({
          amount: Number(payAmount),
          method: payMethod,
          note: payNote
        }),
        idempotencyKey: payKeyRef.current
      });
      payKeyRef.current = "";
      notice("Payment record ho gayi.");
      const data = await api<Payment[]>(
        `/api/transactions/${payTarget.id}/payments`
      );
      setPayments(data);
      setPayAmount("");
      setPayNote("");
      bump();
      void load();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  const dueOf = (t: Transaction) =>
    Math.max(0, Number(t.total_amount) - Number(t.amount_paid));

  async function handleExport() {
    setExporting(true);
    try {
      const params = new URLSearchParams({ status });
      if (kind) params.set("kind", kind);
      if (search.trim()) params.set("search", search.trim());
      await downloadCsv(
        `/api/export/transactions.csv?${params.toString()}`,
        "transactions.csv"
      );
    } catch (error) {
      fail(error);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Transaction history"
        subtitle="Every record stays in the ledger — cancellations never delete rows"
        search={search}
        setSearch={setSearch}
        action={
          <div className="panel-tools">
            <select
              value={kind}
              onChange={e => setKind(e.target.value)}
              style={selectStyle}
            >
              <option value="">All types</option>
              <option value="purchase">Purchase</option>
              <option value="sale">Sale</option>
              <option value="sales_return">Sales return</option>
              <option value="stock_adjustment">Adjustment</option>
              <option value="stock_transfer">Transfer</option>
            </select>
            <select
              value={status}
              onChange={e => setStatus(e.target.value as typeof status)}
              style={selectStyle}
            >
              <option value="active">Active</option>
              <option value="cancelled">Cancelled</option>
              <option value="all">All</option>
            </select>
            <button
              className="secondary-button"
              onClick={() => void handleExport()}
              disabled={exporting}
            >
              {exporting ? "Exporting…" : "Export CSV"}
            </button>
          </div>
        }
      />

      <div className="table-scroll">
        <TransactionTable
          transactions={rows}
          productMap={productMap}
          showDue
          showStatus
          actions={t => {
            const row = rows.find(r => r.id === t.id);
            if (!row) return null;
            const due = dueOf(row);

            return (
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  className="text-button"
                  onClick={() => setReceiptId(row.id)}
                >
                  Receipt
                </button>
                {canOperate && due > 0 && row.status === "active" && (
                  <button
                    className="text-button"
                    onClick={() => void openPayments(row)}
                  >
                    Pay in
                  </button>
                )}
                {canOperate && Number(row.amount_paid) > 0 && (
                  <button
                    className="text-button"
                    onClick={() => void openPayments(row)}
                  >
                    History
                  </button>
                )}
                {canManage &&
                  row.status === "active" &&
                  (row.kind === "purchase" || row.kind === "sale") && (
                    <button
                      className="text-button danger"
                      onClick={() => {
                        setCancelTarget(row);
                        setCancelReason("");
                        setIncludePayments(false);
                      }}
                    >
                      Cancel
                    </button>
                  )}
              </div>
            );
          }}
        />
        {!rows.length && !loading && (
          <Empty text="No transactions match these filters." />
        )}
      </div>

      {cancelTarget && (
        <Modal
          title={`Cancel ${cancelTarget.reference}`}
          subtitle="The record stays; reversal movements and audit entries are created."
          onClose={() => setCancelTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitCancel}>
            <p className="hint">
              {pretty(cancelTarget.kind)} · {qty(cancelTarget.quantity_grams)} g
              · {money(cancelTarget.total_amount)} (paid:{" "}
              {money(cancelTarget.amount_paid)})
            </p>
            <Field label="Reason (required)">
              <textarea
                required
                rows={3}
                minLength={3}
                value={cancelReason}
                onChange={e => setCancelReason(e.target.value)}
              />
            </Field>
            {Number(cancelTarget.amount_paid) > 0 && (
              <label style={{ fontSize: 10, color: "var(--text-3)" }}>
                <input
                  type="checkbox"
                  checked={includePayments}
                  onChange={e => setIncludePayments(e.target.checked)}
                  style={{ marginRight: 6 }}
                />
                Also post a refund payment (amount_paid is{" "}
                {money(cancelTarget.amount_paid)})
              </label>
            )}
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setCancelTarget(null)}
              >
                Keep it
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={busy || cancelReason.trim().length < 3}
              >
                {busy ? "Cancelling…" : "Cancel transaction"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {payTarget && (
        <Modal
          title={`Payments · ${payTarget.reference}`}
          subtitle={`Total ${money(payTarget.total_amount)} · paid ${money(
            payTarget.amount_paid
          )} · due ${money(dueOf(payTarget))}`}
          onClose={() => setPayTarget(null)}
        >
          <div className="table-scroll" style={{ marginBottom: 14 }}>
            <table>
              <thead>
                <tr>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Note</th>
                  <th>Recorded</th>
                </tr>
              </thead>
              <tbody>
                {payments.map(p => (
                  <tr key={p.id}>
                    <td>
                      <b>{money(p.amount)}</b>
                    </td>
                    <td>{pretty(p.method)}</td>
                    <td>{p.note || "—"}</td>
                    <td>{new Date(p.paid_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!payments.length && <Empty text="No payments yet." />}
          </div>

          {canOperate &&
            payTarget.status === "active" &&
            dueOf(payTarget) > 0 && (
              <form className="form-grid modal-form" onSubmit={submitPayment}>
                <Field label="Amount (PKR)">
                  <input
                    required
                    type="number"
                    min="0.01"
                    step="0.01"
                    max={dueOf(payTarget)}
                    value={payAmount}
                    onChange={e => setPayAmount(e.target.value)}
                  />
                </Field>
                <Field label="Method">
                  <select
                    value={payMethod}
                    onChange={e => setPayMethod(e.target.value)}
                  >
                    <option value="cash">Cash</option>
                    <option value="bank_transfer">Bank transfer</option>
                    <option value="other">Other</option>
                  </select>
                </Field>
                <Field label="Note">
                  <input
                    value={payNote}
                    onChange={e => setPayNote(e.target.value)}
                  />
                </Field>
                <div className="form-actions">
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={busy || !payAmount}
                  >
                    {busy ? "Saving…" : "Add payment"}
                  </button>
                </div>
              </form>
            )}
        </Modal>
      )}

      {receiptId !== null && (
        <ReceiptModal
          transactionId={receiptId}
          onClose={() => setReceiptId(null)}
        />
      )}
    </section>
  );
}

const selectStyle: React.CSSProperties = {
  padding: "7px 9px",
  border: "1px solid var(--border)",
  borderRadius: 7,
  fontSize: 10,
  color: "var(--text-2)"
};
