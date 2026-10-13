import { useEffect, useState } from "react";
import {
  ArrowDownLeft, ArrowUpRight, Boxes, Users, Wallet
} from "lucide-react";
import { api, errorText, money, qty, type CurrentUser } from "../api";
import type {DashboardData, Product, Transaction} from "../types";
import { Empty, Metric, PanelHeading, TransactionTable } from "../ui";

const GRAMS_PER_TOLA = 11.6638;

export default function DashboardPage({
  user,
  fail,
  goTo,
  refreshKey
}: {
  user: CurrentUser;
  fail: (e: unknown) => void;
  goTo: (page: string) => void;
  refreshKey: number;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      api<DashboardData>("/api/dashboard"),
      api<Product[]>("/api/products?limit=1000")
    ])
      .then(([dash, prods]) => {
        if (cancelled) return;

        if (dash.status === "fulfilled") setData(dash.value);
        else fail(dash.reason);

        if (prods.status === "fulfilled") setProducts(prods.value);
        else fail(prods.reason);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey]);

  const productMap = new Map(products.map(p => [p.id, p]));
  const gold = data?.active_rates.find(r => r.metal === "gold");
  const silver = data?.active_rates.find(r => r.metal === "silver");

  return (
    <>
      <section className="hero">
        <div>
          <span className="hero-label">BUSINESS SNAPSHOT</span>
          <h2>Welcome back, {user.username}.</h2>
          <p>
            {loading
              ? "Loading live figures from your database…"
              : "Every number below is calculated by the backend from real records."}
          </p>
          <div className="hero-actions">
            <button className="light-button" onClick={() => goTo("Purchases")}>
              Record purchase
            </button>
            <button className="outline-button" onClick={() => goTo("Sales")}>
              Record sale
            </button>
          </div>
        </div>
        <div className="hero-coin">Au</div>
      </section>

      <div className="section-heading">
        <div>
          <h2>Key metrics</h2>
          <p>Computed server-side from transactions and stock movements</p>
        </div>
        <span className="live-badge">● LIVE DATA</span>
      </div>

      <section className="metrics">
        <Metric
          icon={<Boxes size={19} />}
          label="Total stock"
          value={`${qty(data?.stock_grams)} g`}
          foot={`${data?.product_count ?? 0} active products`}
        />
        <Metric
          icon={<Wallet size={19} />}
          label="Inventory value"
          value={money(data?.inventory_value)}
          foot={
            data?.unvalued_products?.length
              ? `${data.unvalued_products.length} products without a matching rate`
              : "Valued with active verified rates"
          }
        />
        <Metric
          icon={<ArrowUpRight size={19} />}
          label="Total sales"
          value={money(data?.sales.total_amount)}
          foot={`Due: ${money(data?.sales.remaining_amount)}`}
        />
        <Metric
          icon={<ArrowDownLeft size={19} />}
          label="Total purchases"
          value={money(data?.purchases.total_amount)}
          foot={`Payable: ${money(data?.purchases.remaining_amount)}`}
        />
      </section>

      <section className="metrics" style={{ marginTop: 13 }}>
        <Metric
          icon={<Users size={19} />}
          label="Customers & suppliers"
          value={String(data?.party_count ?? 0)}
          foot="Registered parties"
        />
        <Metric
          icon={<Wallet size={19} />}
          label="Transactions"
          value={String(data?.transaction_count ?? 0)}
          foot="Active records in the ledger"
        />
        <Metric
          icon={<Boxes size={19} />}
          label="Gold rate / tola"
          value={
            gold
              ? money(Number(gold.rate_per_gram) * GRAMS_PER_TOLA)
              : "Not set"
          }
          foot={gold ? `${qty(gold.purity)}% purity · verified` : "Add a rate"}
        />
        <Metric
          icon={<Boxes size={19} />}
          label="Silver rate / tola"
          value={
            silver
              ? money(Number(silver.rate_per_gram) * GRAMS_PER_TOLA)
              : "Not set"
          }
          foot={
            silver ? `${qty(silver.purity)}% purity · verified` : "Add a rate"
          }
        />
      </section>

      {data?.unvalued_products?.length ? (
        <section className="panel">
          <PanelHeading
            title="Products without a matching rate"
            subtitle="Stock exists but no active rate covers this metal and purity, so it is not valued yet"
          />
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Balance</th>
                </tr>
              </thead>
              <tbody>
                {data.unvalued_products.map(row => (
                  <tr key={row.product_id}>
                    <td>
                      <b>{row.name}</b>
                    </td>
                    <td>{qty(row.balance_grams)} g</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="panel">
        <PanelHeading
          title="Recent transactions"
          subtitle="Latest movements in your ledger"
          action={
            <button className="text-button" onClick={() => goTo("Transactions")}>
              View all →
            </button>
          }
        />
        <TransactionTable
          transactions={data?.recent_transactions ?? []}
          productMap={productMap}
          showDue
        />
        {!data?.recent_transactions?.length && !loading && (
          <Empty text="No transactions yet. Record a purchase to get started." />
        )}
      </section>
    </>
  );
}
