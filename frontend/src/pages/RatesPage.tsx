import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api, atLeast, money, qty, type CurrentUser } from "../api";
import type {MetalRate, RateUnit} from "../types";
import { Empty, Field, MetalTag, Modal, PanelHeading, Status } from "../ui";

const GRAMS_PER_TOLA = 11.6638;

const UNITS: { value: RateUnit; label: string; factor: number }[] = [
  { value: "tola", label: "Tola", factor: GRAMS_PER_TOLA },
  { value: "gram", label: "Gram", factor: 1 },
  { value: "kilogram", label: "Kilogram", factor: 1000 }
];

const blank = {
  metal: "gold",
  purity: "99.99",
  rate_per_gram: "",
  unit: "tola" as RateUnit,
  source_note: "Manually verified",
  verified_by: ""
};

export default function RatesPage({
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
  const [rates, setRates] = useState<MetalRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [includeHistory, setIncludeHistory] = useState(false);
  const [form, setForm] = useState({ ...blank, verified_by: user.username });
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const canManage = atLeast(user, "manager");

  useEffect(() => {
    let cancelled = false;

    api<MetalRate[]>(`/api/rates?active_only=${!includeHistory}`)
      .then(rows => {
        if (!cancelled) setRates(rows);
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
  }, [fail, includeHistory, refreshKey]);

  const active = rates.filter(r => r.active);
  const gold = active.find(r => r.metal === "gold");
  const silver = active.find(r => r.metal === "silver");

  const filtered = rates.filter(r =>
    `${r.metal} ${r.source_note || ""} ${r.verified_by || ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  function perTola(rate?: MetalRate) {
    if (!rate) return "Not set";
    return money(Number(rate.rate_per_gram) * GRAMS_PER_TOLA);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);

    try {
      // The value the operator typed stays in the chosen unit; the
      // backend normalizes it to a per-gram rate before calculating.
      await api("/api/rates", {
        method: "POST",
        body: JSON.stringify({
          metal: form.metal,
          purity: Number(form.purity),
          rate_per_gram: Number(form.rate_per_gram),
          unit: form.unit,
          source_note: form.source_note,
          verified_by: form.verified_by
        })
      });
      notice("Metal rate save ho gaya (history preserved).");
      setShowForm(false);
      setForm({ ...blank, verified_by: user.username });
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <section className="rate-cards">
        <article className="rate-card">
          <span>Gold rate / tola</span>
          <strong>{perTola(gold)}</strong>
          <small>
            {gold
              ? `${qty(gold.purity)}% purity · entered as ${qty(gold.entered_rate)} per ${gold.unit}`
              : "Add a verified rate to begin"}
          </small>
        </article>
        <article className="rate-card">
          <span>Silver rate / tola</span>
          <strong>{perTola(silver)}</strong>
          <small>
            {silver
              ? `${qty(silver.purity)}% purity · entered as ${qty(silver.entered_rate)} per ${silver.unit}`
              : "Add a verified rate to begin"}
          </small>
        </article>
      </section>

      <section className="panel">
        <PanelHeading
          title="Metal rate records"
          subtitle="Manually verified rates with full history"
          search={search}
          setSearch={setSearch}
          action={
            canManage ? (
              <button
                className="primary-button"
                onClick={() => setShowForm(true)}
              >
                <Plus size={16} /> Add verified rate
              </button>
            ) : null
          }
        />

        <div style={{ padding: "12px 19px 0" }}>
          <label style={{ fontSize: 10, color: "var(--text-3)" }}>
            <input
              type="checkbox"
              checked={includeHistory}
              onChange={e => setIncludeHistory(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            Show full rate history
          </label>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Metal</th>
                <th>Purity</th>
                <th>Entered rate</th>
                <th>Rate / tola</th>
                <th>Source note</th>
                <th>Verified by</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id}>
                  <td>
                    <MetalTag metal={r.metal} />
                  </td>
                  <td>{qty(r.purity)}%</td>
                  <td>
                    <b>{money(r.entered_rate)}</b> / {r.unit}
                  </td>
                  <td>{money(Number(r.rate_per_gram) * GRAMS_PER_TOLA)}</td>
                  <td>{r.source_note || "—"}</td>
                  <td>{r.verified_by || "—"}</td>
                  <td>
                    <Status active={r.active} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && !loading && (
            <Empty text="No rates found. Add a verified rate." />
          )}
        </div>
      </section>

      {showForm && (
        <Modal
          title="Add verified metal rate"
          subtitle="Enter the rate your business verified. History is never overwritten."
          onClose={() => setShowForm(false)}
        >
          <form className="form-grid modal-form" onSubmit={submit}>
            <Field label="Metal">
              <select
                value={form.metal}
                onChange={e => setForm({ ...form, metal: e.target.value })}
              >
                <option value="gold">Gold</option>
                <option value="silver">Silver</option>
              </select>
            </Field>
            <Field label="Purity (%)">
              <input
                required
                type="number"
                min="0.01"
                max="100"
                step="0.01"
                value={form.purity}
                onChange={e => setForm({ ...form, purity: e.target.value })}
              />
            </Field>
            <Field label="Rate">
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={form.rate_per_gram}
                onChange={e =>
                  setForm({ ...form, rate_per_gram: e.target.value })
                }
              />
            </Field>
            <Field label="Rate unit">
              <select
                value={form.unit}
                onChange={e =>
                  setForm({ ...form, unit: e.target.value as RateUnit })
                }
              >
                {UNITS.map(unit => (
                  <option key={unit.value} value={unit.value}>
                    Per {unit.label.toLowerCase()}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Verified by">
              <input
                required
                value={form.verified_by}
                onChange={e =>
                  setForm({ ...form, verified_by: e.target.value })
                }
              />
            </Field>
            <Field label="Source / note">
              <input
                value={form.source_note}
                onChange={e =>
                  setForm({ ...form, source_note: e.target.value })
                }
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
                {saving ? "Saving…" : "Save rate"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
