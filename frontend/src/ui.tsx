import { useEffect, type ReactNode } from "react";
import { Boxes, Search, X } from "lucide-react";
import type { Product } from "./types";
import { money, qty } from "./api";

export function Field({
  label,
  children
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function Modal({
  title,
  subtitle,
  children,
  onClose
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section className="modal">
        <div className="modal-heading">
          <div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          <button className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

export function PanelHeading({
  title,
  subtitle,
  search,
  setSearch,
  action
}: {
  title: string;
  subtitle?: string;
  search?: string;
  setSearch?: (v: string) => void;
  action?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="panel-tools">
        {setSearch && (
          <label className="search">
            <Search size={15} />
            <input
              placeholder="Search…"
              value={search || ""}
              onChange={e => setSearch(e.target.value)}
            />
          </label>
        )}
        {action}
      </div>
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <Boxes size={24} />
      <b>No records found</b>
      <p>{text}</p>
    </div>
  );
}

export function MetalTag({ metal }: { metal: string }) {
  return <span className={`metal-tag ${metal.toLowerCase()}`}>{metal}</span>;
}

export function Status({ active }: { active: boolean }) {
  return (
    <span className={`status ${active ? "active" : "inactive"}`}>
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function Metric({
  icon,
  label,
  value,
  foot
}: {
  icon: ReactNode;
  label: string;
  value: string;
  foot: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{foot}</small>
    </article>
  );
}

export function pretty(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c: string) => c.toUpperCase());
}

export function TransactionTable({
  transactions,
  productMap,
  showDue = false,
  showStatus = false,
  actions
}: {
  transactions: {
    id: number;
    reference: string;
    kind: string;
    status?: string;
    party_name: string;
    product_id: number;
    quantity_grams: number | string;
    total_amount: number | string;
    amount_paid: number | string;
  }[];
  productMap: Map<number, Product>;
  showDue?: boolean;
  showStatus?: boolean;
  actions?: (row: { id: number; status?: string; kind: string }) => ReactNode;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Reference</th>
            <th>Type</th>
            <th>Party</th>
            <th>Product</th>
            <th>Weight</th>
            <th>Total</th>
            <th>Paid</th>
            {showDue && <th>Due</th>}
            {showStatus && <th>Status</th>}
            {actions && <th></th>}
          </tr>
        </thead>
        <tbody>
          {transactions.map(t => (
            <tr key={t.id}>
              <td>{t.reference || `TX-${t.id}`}</td>
              <td>
                <span className={`kind ${t.kind}`}>{pretty(t.kind)}</span>
              </td>
              <td>{t.party_name || "—"}</td>
              <td>
                {productMap.get(t.product_id)?.name ||
                  `Product #${t.product_id}`}
              </td>
              <td>{qty(t.quantity_grams)} g</td>
              <td>
                <b>{money(t.total_amount)}</b>
              </td>
              <td>{money(t.amount_paid)}</td>
              {showDue && (
                <td className="due">
                  {money(
                    Math.max(
                      0,
                      Number(t.total_amount) - Number(t.amount_paid)
                    )
                  )}
                </td>
              )}
              {showStatus && (
                <td>
                  {t.status === "cancelled" ? (
                    <span className="status inactive">Cancelled</span>
                  ) : (
                    <span className="status active">Active</span>
                  )}
                </td>
              )}
              {actions && <td>{actions({ id: t.id, status: t.status, kind: t.kind })}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      {!transactions.length && (
        <Empty text="No transactions to display yet." />
      )}
    </div>
  );
}
