import { useEffect, useState } from "react";
import { api, money, qty, type CurrentUser } from "../api";
import type {
  AppSettings,
  CashflowReport,
  OutstandingItem,
  ProfitEstimate,
  ReportSummary
} from "../types";
import { Empty, Field, Metric, PanelHeading, pretty } from "../ui";
import { duesReminder, waLink } from "../whatsapp";

interface OutstandingResponse {
  items: OutstandingItem[];
  count: number;
  skip: number;
  limit: number;
}

interface LedgerResponse {
  party_name: string;
  transactions: {
    transaction_id: number;
    reference: string;
    kind: string;
    created_at: string;
    quantity_grams: number | string;
    total_amount: number | string;
    amount_paid: number | string;
    remaining_amount: number | string;
    payments: {
      id: number;
      amount: number | string;
      method: string;
      note: string;
      paid_at: string;
    }[];
  }[];
  transaction_count: number;
}

export default function ReportsPage({
  user: _user,
  fail,
  refreshKey
}: {
  user: CurrentUser;
  fail: (e: unknown) => void;
  refreshKey: number;
}) {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [profit, setProfit] = useState<ProfitEstimate | null>(null);
  const [outstanding, setOutstanding] = useState<OutstandingResponse | null>(
    null
  );
  const [cashflow, setCashflow] = useState<CashflowReport | null>(null);
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [partyName, setPartyName] = useState("");
  const [outstandingKind, setOutstandingKind] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [ledgerLoading, setLedgerLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const params = new URLSearchParams({ limit: "200" });
    if (outstandingKind) params.set("kind", outstandingKind);

    const range = new URLSearchParams();
    if (dateFrom) range.set("date_from", dateFrom);
    if (dateTo) range.set("date_to", dateTo);
    const rangeQuery = range.toString() ? `?${range}` : "";

    Promise.allSettled([
      api<AppSettings>("/api/settings"),
      api<ReportSummary>(`/api/reports/summary${rangeQuery}`),
      api<ProfitEstimate>(`/api/reports/profit${rangeQuery}`),
      api<OutstandingResponse>(`/api/reports/outstanding?${params}`),
      api<CashflowReport>(`/api/reports/cashflow${rangeQuery}`)
    ])
      .then(([set, sum, prof, out, cash]) => {
        if (cancelled) return;
        if (set.status === "fulfilled") setSettings(set.value);
        else fail(set.reason);
        if (sum.status === "fulfilled") setSummary(sum.value);
        else fail(sum.reason);
        if (prof.status === "fulfilled") setProfit(prof.value);
        else fail(prof.reason);
        if (out.status === "fulfilled") setOutstanding(out.value);
        else fail(out.reason);
        if (cash.status === "fulfilled") setCashflow(cash.value);
        else fail(cash.reason);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo, fail, outstandingKind, refreshKey]);

  async function loadLedger() {
    if (!partyName.trim()) return;
    setLedgerLoading(true);

    try {
      const data = await api<LedgerResponse>(
        `/api/reports/party-ledger?party_name=${encodeURIComponent(
          partyName.trim()
        )}`
      );
      setLedger(data);
    } catch (error) {
      fail(error);
      setLedger(null);
    } finally {
      setLedgerLoading(false);
    }
  }

  return (
    <>
      <div className="print-header">
        <h1>{settings?.business_name || "SNJ Gold Lab"}</h1>
        <h2>Financial report</h2>
        {(settings?.business_address || settings?.business_phone) && (
          <p>
            {settings?.business_address}
            {settings?.business_address && settings?.business_phone ? " · " : ""}
            {settings?.business_phone}
          </p>
        )}
        <p>
          {dateFrom || dateTo
            ? `Period: ${dateFrom || "beginning"} to ${dateTo || "today"}`
            : "Period: all time"}{" "}
          · Printed {new Date().toLocaleString()}
        </p>
      </div>

      <section className="panel print-hidden">
        <PanelHeading
          title="Report options"
          subtitle="Filter by date, then print or save as PDF"
          action={
            <button
              className="primary-button"
              onClick={() => window.print()}
            >
              Print / Save PDF
            </button>
          }
        />
        <div
          className="form-grid"
          style={{ gridTemplateColumns: "200px 200px auto", alignItems: "end" }}
        >
          <Field label="From date">
            <input
              type="date"
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
            />
          </Field>
          <Field label="To date">
            <input
              type="date"
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
            />
          </Field>
          <div className="form-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setDateFrom("");
                setDateTo("");
              }}
            >
              Clear dates
            </button>
          </div>
        </div>
      </section>

      <section className="metrics">
        <Metric
          icon={<span>🛒</span>}
          label="Purchase total"
          value={money(summary?.purchase.total_amount)}
          foot={`Paid ${money(summary?.purchase.amount_paid)} · due ${money(
            summary?.purchase.remaining_amount
          )}`}
        />
        <Metric
          icon={<span>💰</span>}
          label="Sale total"
          value={money(summary?.sale.total_amount)}
          foot={`Paid ${money(summary?.sale.amount_paid)} · due ${money(
            summary?.sale.remaining_amount
          )}`}
        />
        <Metric
          icon={<span>↩️</span>}
          label="Sales returns"
          value={String(summary?.sales_returns.count ?? 0)}
          foot={`Adjustments: ${summary?.stock_adjustments.count ?? 0}`}
        />
        <Metric
          icon={<span>🏦</span>}
          label="Net cashflow"
          value={money(cashflow?.net_cashflow)}
          foot={`Received ${money(cashflow?.money_received)} · paid ${money(
            cashflow?.money_paid
          )} · ${cashflow?.payment_count ?? 0} payments`}
        />
        <Metric
          icon={<span>📊</span>}
          label="Est. profit"
          value={money(profit?.estimated_profit)}
          foot={`Sales ${money(profit?.sales_total)} · returns ${money(
            profit?.sales_returns_value
          )} · purchases ${money(profit?.purchases_total)} (estimate only)`}
        />
      </section>

      <section className="panel">
        <PanelHeading
          title="Outstanding amounts"
          subtitle="Active purchases and sales that still have a balance due"
          action={
            <select
              value={outstandingKind}
              onChange={e => setOutstandingKind(e.target.value)}
              style={{
                padding: "7px 9px",
                border: "1px solid var(--border)",
                borderRadius: 7,
                fontSize: 10,
                color: "var(--text-2)"
              }}
            >
              <option value="">All kinds</option>
              <option value="purchase">Purchases (payable)</option>
              <option value="sale">Sales (receivable)</option>
            </select>
          }
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Type</th>
                <th>Party</th>
                <th>Total</th>
                <th>Paid</th>
                <th>Remaining</th>
                <th>Date</th>
                <th>Remind</th>
              </tr>
            </thead>
            <tbody>
              {(outstanding?.items ?? []).map(row => {
                const link =
                  row.party_phone && Number(row.remaining_amount) > 0
                    ? waLink(
                        row.party_phone,
                        duesReminder(
                          row.party_name,
                          settings?.business_name || "Saleem Nadeem Jewellers",
                          money(row.remaining_amount)
                        )
                      )
                    : null;
                return (
                  <tr key={row.transaction_id}>
                    <td>{row.reference}</td>
                    <td>
                      <span className={`kind ${row.kind}`}>{row.kind}</span>
                    </td>
                    <td>{row.party_name || "—"}</td>
                    <td>{money(row.total_amount)}</td>
                    <td>{money(row.amount_paid)}</td>
                    <td className="due">
                      <b>{money(row.remaining_amount)}</b>
                    </td>
                    <td>{new Date(row.created_at).toLocaleDateString()}</td>
                    <td>
                      {link && (
                        <button
                          className="text-button"
                          onClick={() =>
                            window.open(link, "_blank", "noopener,noreferrer")
                          }
                        >
                          WhatsApp
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!outstanding?.items.length && !loading && (
            <Empty text="No outstanding balances — sab clear hai." />
          )}
        </div>
      </section>

      <section className="panel">
        <PanelHeading
          title="Party ledger"
          subtitle="Full transaction and payment history for one party"
        />
        <div className="panel-tools" style={{ padding: "0 19px 14px" }}>
          <label className="search">
            <input
              placeholder="Party name (exact)"
              value={partyName}
              onChange={e => setPartyName(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") void loadLedger();
              }}
            />
          </label>
          <button
            className="secondary-button"
            onClick={() => void loadLedger()}
            disabled={ledgerLoading || !partyName.trim()}
          >
            {ledgerLoading ? "Loading…" : "View ledger"}
          </button>
        </div>

        {ledger && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Type</th>
                  <th>Weight</th>
                  <th>Total</th>
                  <th>Paid</th>
                  <th>Remaining</th>
                  <th>Payments</th>
                </tr>
              </thead>
              <tbody>
                {ledger.transactions.map(row => (
                  <tr key={row.transaction_id}>
                    <td>{row.reference}</td>
                    <td>{pretty(row.kind)}</td>
                    <td>{qty(row.quantity_grams)} g</td>
                    <td>{money(row.total_amount)}</td>
                    <td>{money(row.amount_paid)}</td>
                    <td className="due">{money(row.remaining_amount)}</td>
                    <td>
                      {row.payments.length
                        ? row.payments
                            .map(p => `${money(p.amount)} (${p.method})`)
                            .join(", ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!ledger.transactions.length && (
              <Empty text={`No transactions found for ${ledger.party_name}.`} />
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <PanelHeading
          title="Cashflow detail"
          subtitle="Every payment received or paid, including refund payments"
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Reference</th>
                <th>Party</th>
                <th>Direction</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {(cashflow?.items ?? []).map(row => (
                <tr key={row.payment_id}>
                  <td>{new Date(row.paid_at).toLocaleString()}</td>
                  <td>{row.reference}</td>
                  <td>{row.party_name || "—"}</td>
                  <td>
                    <span className={`kind ${row.direction === "received" ? "sale" : "purchase"}`}>
                      {row.direction}
                    </span>
                  </td>
                  <td>
                    <b>{money(row.amount)}</b>
                  </td>
                  <td>{pretty(row.method)}</td>
                  <td>{row.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!cashflow?.items.length && !loading && (
            <Empty text="No payments recorded yet." />
          )}
        </div>
      </section>

      {settings?.receipt_note && (
        <p className="print-only" style={{ textAlign: "center", marginTop: 24 }}>
          {settings.receipt_note}
        </p>
      )}

    </>
  );
}
