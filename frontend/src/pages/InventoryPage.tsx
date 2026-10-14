import { useEffect, useMemo, useState } from "react";
import { api, type CurrentUser } from "../api";
import type {AppSettings, InventoryRow, Product} from "../types";
import { Empty, MetalTag, PanelHeading } from "../ui";

export default function InventoryPage({
  user: _user,
  fail,
  refreshKey
}: {
  user: CurrentUser;
  fail: (e: unknown) => void;
  refreshKey: number;
}) {
  const [rows, setRows] = useState<InventoryRow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [threshold, setThreshold] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");

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
        if (set.status === "fulfilled") {
          const value = Number(set.value.low_stock_threshold || 0);
          setThreshold(Number.isFinite(value) && value > 0 ? value : 0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, refreshKey]);

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
              border: "1px solid #e7ecf2",
              borderRadius: 7,
              fontSize: 10,
              color: "#526176"
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
    </section>
  );
}
