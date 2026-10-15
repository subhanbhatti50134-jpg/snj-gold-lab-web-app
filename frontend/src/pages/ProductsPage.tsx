import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api, atLeast, type CurrentUser } from "../api";
import type {Product} from "../types";
import { Empty, Field, MetalTag, Modal, PanelHeading, Status, pretty } from "../ui";

const CATEGORIES = [
  ["loose_metal", "Loose metal"],
  ["biscuit", "Biscuit"],
  ["jewellery", "Jewellery"],
  ["laboratory_material", "Laboratory material"]
] as const;

const METALS = [
  ["gold", "Gold"],
  ["silver", "Silver"],
  ["other", "Other"]
] as const;

const blank = {
  sku: "",
  name: "",
  category: "loose_metal",
  metal: "gold",
  purity: "99.99"
};

export default function ProductsPage({
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
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [form, setForm] = useState(blank);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);

  const canManage = atLeast(user, "manager");

  useEffect(() => {
    let cancelled = false;

    api<Product[]>(
      `/api/products?include_inactive=${includeInactive}&limit=1000`
    )
      .then(rows => {
        if (!cancelled) setProducts(rows);
      })
      .catch(err => {
        if (!cancelled) fail(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, includeInactive, refreshKey]);

  const filtered = products.filter(p =>
    `${p.name} ${p.sku} ${p.metal} ${p.category}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);

    try {
      await api("/api/products", {
        method: "POST",
        body: JSON.stringify({ ...form, purity: Number(form.purity) })
      });
      notice("Product save ho gaya.");
      setShowForm(false);
      setForm(blank);
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(product: Product) {
    try {
      await api(`/api/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !product.active })
      });
      notice(
        product.active
          ? `${product.name} deactivate ho gaya.`
          : `${product.name} activate ho gaya.`
      );
      setProducts(rows =>
        rows.map(row =>
          row.id === product.id ? { ...row, active: !product.active } : row
        )
      );
    } catch (error) {
      fail(error);
    }
  }

  async function submitDelete(event: FormEvent) {
    event.preventDefault();
    if (!deleteTarget) return;
    setSaving(true);

    try {
      await api(`/api/products/${deleteTarget.id}`, { method: "DELETE" });
      notice(`${deleteTarget.name} delete ho gaya.`);
      setProducts(rows => rows.filter(row => row.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Product catalogue"
        subtitle={`${products.length} registered products`}
        search={search}
        setSearch={setSearch}
        action={
          canManage ? (
            <button className="primary-button" onClick={() => setShowForm(true)}>
              <Plus size={16} /> Add product
            </button>
          ) : null
        }
      />

      <div style={{ padding: "12px 19px 0" }}>
        <label style={{ fontSize: 10, color: "var(--text-3)" }}>
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={e => setIncludeInactive(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          Show inactive products
        </label>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              <th>Category</th>
              <th>Metal</th>
              <th>Purity</th>
              <th>Status</th>
              {canManage && <th></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map(p => (
              <tr key={p.id}>
                <td>
                  <b>{p.name}</b>
                </td>
                <td>{p.sku}</td>
                <td>{pretty(p.category)}</td>
                <td>
                  <MetalTag metal={p.metal} />
                </td>
                <td>{p.purity}%</td>
                <td>
                  <Status active={p.active} />
                </td>
                {canManage && (
                  <td>
                    <button
                      className="text-button"
                      onClick={() => void toggleActive(p)}
                    >
                      {p.active ? "Deactivate" : "Activate"}
                    </button>
                    {"  "}
                    <button
                      className="text-button danger"
                      onClick={() => setDeleteTarget(p)}
                    >
                      Delete
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && !loading && (
          <Empty text="No products found. Add a product to begin." />
        )}
      </div>

      {showForm && (
        <Modal
          title="Add product"
          subtitle="Register metal, biscuit, jewellery or lab material."
          onClose={() => setShowForm(false)}
        >
          <form className="form-grid modal-form" onSubmit={submit}>
            <Field label="Product name">
              <input
                required
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="SKU / code">
              <input
                required
                value={form.sku}
                onChange={e => setForm({ ...form, sku: e.target.value })}
              />
            </Field>
            <Field label="Category">
              <select
                value={form.category}
                onChange={e => setForm({ ...form, category: e.target.value })}
              >
                {CATEGORIES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Metal">
              <select
                value={form.metal}
                onChange={e => setForm({ ...form, metal: e.target.value })}
              >
                {METALS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Purity (%)">
              <input
                required
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={form.purity}
                onChange={e => setForm({ ...form, purity: e.target.value })}
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setShowForm(false)}
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

      {deleteTarget && (
        <Modal
          title={`Delete ${deleteTarget.name}`}
          subtitle="Permanent — only products with no transactions or stock history can be deleted."
          onClose={() => setDeleteTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitDelete}>
            <p className="hint">
              {deleteTarget.sku} · {pretty(deleteTarget.metal)} ·{" "}
              {deleteTarget.purity}%
            </p>
            <p className="hint">
              Agar is product par koi transaction ya stock movement hai to
              delete block ho jayega — us case mein Deactivate use karein.
            </p>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setDeleteTarget(null)}
              >
                Keep it
              </button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "Deleting…" : "Delete forever"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
