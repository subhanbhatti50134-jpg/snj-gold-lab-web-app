import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, money } from "./api";

export interface ReceiptData {
  id: number;
  reference: string;
  kind: string;
  status: string;
  product_name: string;
  product_sku: string;
  quantity_grams: string;
  gross_weight_grams: string;
  net_weight_grams: string;
  deduction_grams: string;
  purity: string;
  rate_per_gram: string;
  charges: string;
  total_amount: string;
  party_name: string;
  location: string;
  created_by: string;
  transaction_date: string | null;
  created_at: string | null;
  cancel_reason: string | null;
  paid_total: string;
  due_amount: string;
  payments: {
    id: number;
    amount: string;
    method: string;
    note: string;
    recorded_by: string;
    paid_at: string | null;
  }[];
  business: {
    name: string;
    address: string;
    phone: string;
    currency: string;
    receipt_note: string;
  };
}

const KIND_LABELS: Record<string, string> = {
  sale: "Sale",
  purchase: "Purchase",
  sales_return: "Sales return",
  stock_adjustment: "Stock adjustment",
  stock_transfer: "Stock transfer"
};

function fmt(value: string | number | null | undefined): string {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n.toFixed(4).replace(/\.?0+$/, "") || "0" : "0";
}

function stamp(value: string | null): string {
  if (!value) return "";
  return value.replace("T", " ").slice(0, 16);
}

export default function ReceiptModal({
  transactionId,
  onClose
}: {
  transactionId: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<ReceiptData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    document.body.classList.add("receipt-mode");
    api<ReceiptData>(`/api/transactions/${transactionId}`)
      .then(res => {
        if (!cancelled) setData(res);
      })
      .catch(err => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
      document.body.classList.remove("receipt-mode");
    };
  }, [transactionId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const body = data ? (
    <div className="receipt">
      <div className="receipt-header">
        <h2>{data.business.name}</h2>
        {data.business.address && <p>{data.business.address}</p>}
        {data.business.phone && <p>{data.business.phone}</p>}
      </div>

      <div className="receipt-title">
        <b>{KIND_LABELS[data.kind] ?? data.kind} Receipt</b>
        {data.status === "cancelled" && <span className="receipt-cancelled">CANCELLED</span>}
      </div>

      <table className="receipt-table">
        <tbody>
          <tr>
            <td>Reference</td>
            <td>{data.reference}</td>
          </tr>
          <tr>
            <td>Date</td>
            <td>{stamp(data.transaction_date ?? data.created_at)}</td>
          </tr>
          <tr>
            <td>Item</td>
            <td>
              {data.product_name}
              {data.product_sku ? ` (${data.product_sku})` : ""}
            </td>
          </tr>
          <tr>
            <td>Gross weight</td>
            <td>{fmt(data.gross_weight_grams)} g</td>
          </tr>
          <tr>
            <td>Net weight</td>
            <td>{fmt(data.net_weight_grams)} g</td>
          </tr>
          {Number(data.deduction_grams) > 0 && (
            <tr>
              <td>Deduction</td>
              <td>{fmt(data.deduction_grams)} g</td>
            </tr>
          )}
          <tr>
            <td>Purity</td>
            <td>{fmt(data.purity)}%</td>
          </tr>
          <tr>
            <td>Rate</td>
            <td>{money(data.rate_per_gram)} / g</td>
          </tr>
          {Number(data.charges) > 0 && (
            <tr>
              <td>Charges</td>
              <td>{money(data.charges)}</td>
            </tr>
          )}
          {data.party_name && (
            <tr>
              <td>Party</td>
              <td>{data.party_name}</td>
            </tr>
          )}
          <tr>
            <td>Cashier</td>
            <td>{data.created_by}</td>
          </tr>
        </tbody>
      </table>

      <div className="receipt-totals">
        <div>
          <span>Total</span>
          <b>{money(data.total_amount)}</b>
        </div>
        <div>
          <span>Received</span>
          <b>{money(data.paid_total)}</b>
        </div>
        <div className={Number(data.due_amount) > 0 ? "due" : ""}>
          <span>Due</span>
          <b>{money(data.due_amount)}</b>
        </div>
      </div>

      {data.payments.length > 1 && (
        <div className="receipt-payments">
          <b>Payments</b>
          {data.payments.map(p => (
            <div key={p.id}>
              <span>{stamp(p.paid_at)} · {p.method}</span>
              <span>{money(p.amount)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="receipt-footer">
        {data.business.receipt_note || "Thank you — visit again!"}
      </div>
      {data.status === "cancelled" && data.cancel_reason && (
        <div className="receipt-cancel-note">Cancel reason: {data.cancel_reason}</div>
      )}
    </div>
  ) : (
    <div className="loading" style={{ padding: "30px 0", textAlign: "center" }}>
      {error || "Loading receipt…"}
    </div>
  );

  return createPortal(
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-heading">
          <div>
            <h2>Receipt</h2>
            <p>Print or save as PDF (browser print dialog)</p>
          </div>
          <button
            type="button"
            className="icon-button receipt-close"
            aria-label="Close receipt"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        {body}
        {!error && data && (
          <div className="form-actions receipt-actions">
            <button type="button" className="secondary-button" onClick={onClose}>
              Close
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={() => window.print()}
            >
              Print
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
