import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api, atLeast, money, type CurrentUser } from "../api";
import type {Party} from "../types";
import { Empty, Field, Modal, PanelHeading, Status, pretty } from "../ui";

const blank = {
  name: "",
  kind: "customer",
  phone: "",
  address: "",
  notes: ""
};

export default function PartiesPage({
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
  const [parties, setParties] = useState<Party[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [form, setForm] = useState(blank);
  const [editing, setEditing] = useState<Party | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const canManage = atLeast(user, "manager");

  useEffect(() => {
    let cancelled = false;

    const params = new URLSearchParams({
      include_inactive: String(includeInactive)
    });
    if (search.trim()) params.set("search", search.trim());
    if (kind) params.set("kind", kind);

    api<Party[]>(`/api/parties?${params.toString()}`)
      .then(rows => {
        if (!cancelled) setParties(rows);
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
  }, [fail, includeInactive, kind, refreshKey, search]);

  function openCreate() {
    setForm(blank);
    setEditing(null);
    setShowForm(true);
  }

  function openEdit(party: Party) {
    setForm({
      name: party.name,
      kind: party.kind,
      phone: party.phone,
      address: party.address,
      notes: party.notes
    });
    setEditing(party);
    setShowForm(true);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);

    try {
      if (editing) {
        await api(`/api/parties/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(form)
        });
        notice("Party update ho gaya.");
      } else {
        await api("/api/parties", {
          method: "POST",
          body: JSON.stringify(form)
        });
        notice("Party save ho gaya.");
      }
      setShowForm(false);
      setEditing(null);
      setForm(blank);
      refresh();
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(party: Party) {
    try {
      await api(`/api/parties/${party.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !party.active })
      });
      notice(party.active ? "Party deactivate ho gaya." : "Party activate ho gaya.");
      refresh();
    } catch (error) {
      fail(error);
    }
  }

  function refresh() {
    const params = new URLSearchParams({
      include_inactive: String(includeInactive)
    });
    if (search.trim()) params.set("search", search.trim());
    if (kind) params.set("kind", kind);

    api<Party[]>(`/api/parties?${params.toString()}`)
      .then(setParties)
      .catch(fail);
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Customers & suppliers"
        subtitle="Balances are calculated from active transactions"
        search={search}
        setSearch={setSearch}
        action={
          <div className="panel-tools">
            <select
              value={kind}
              onChange={e => setKind(e.target.value)}
              style={{
                padding: "7px 9px",
                border: "1px solid #e7ecf2",
                borderRadius: 7,
                fontSize: 10,
                color: "#526176"
              }}
            >
              <option value="">All kinds</option>
              <option value="customer">Customers</option>
              <option value="supplier">Suppliers</option>
              <option value="both">Both</option>
            </select>
            {canManage && (
              <button className="primary-button" onClick={openCreate}>
                <Plus size={16} /> Add party
              </button>
            )}
          </div>
        }
      />

      <div style={{ padding: "12px 19px 0" }}>
        <label style={{ fontSize: 10, color: "#66768b" }}>
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={e => setIncludeInactive(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          Show inactive parties
        </label>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Phone</th>
              <th>Receivable</th>
              <th>Payable</th>
              <th>Net</th>
              <th>Status</th>
              {canManage && <th></th>}
            </tr>
          </thead>
          <tbody>
            {parties.map(p => (
              <tr key={p.id}>
                <td>
                  <b>{p.name}</b>
                  {p.address && (
                    <div style={{ fontSize: 9, color: "#66768b" }}>
                      {p.address}
                    </div>
                  )}
                </td>
                <td>{pretty(p.kind)}</td>
                <td>{p.phone || "—"}</td>
                <td>{money(p.receivable)}</td>
                <td>{money(p.payable)}</td>
                <td>
                  <b>{money(p.net)}</b>
                </td>
                <td>
                  <Status active={p.active} />
                </td>
                {canManage && (
                  <td>
                    <div style={{ display: "flex", gap: 10 }}>
                      <button
                        className="text-button"
                        onClick={() => openEdit(p)}
                      >
                        Edit
                      </button>
                      <button
                        className="text-button"
                        onClick={() => void toggleActive(p)}
                      >
                        {p.active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!parties.length && !loading && (
          <Empty text="No parties found. Add a customer or supplier." />
        )}
      </div>

      {showForm && (
        <Modal
          title={editing ? "Edit party" : "Add party"}
          subtitle="Customers get receivables, suppliers get payables."
          onClose={() => {
            setShowForm(false);
            setEditing(null);
          }}
        >
          <form className="form-grid modal-form" onSubmit={submit}>
            <Field label="Name">
              <input
                required
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="Kind">
              <select
                value={form.kind}
                onChange={e => setForm({ ...form, kind: e.target.value })}
              >
                <option value="customer">Customer</option>
                <option value="supplier">Supplier</option>
                <option value="both">Both</option>
              </select>
            </Field>
            <Field label="Phone">
              <input
                value={form.phone}
                onChange={e => setForm({ ...form, phone: e.target.value })}
              />
            </Field>
            <Field label="Address">
              <input
                value={form.address}
                onChange={e => setForm({ ...form, address: e.target.value })}
              />
            </Field>
            <Field label="Notes">
              <textarea
                rows={3}
                value={form.notes}
                onChange={e => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setShowForm(false);
                  setEditing(null);
                }}
              >
                Cancel
              </button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "Saving…" : editing ? "Save changes" : "Save party"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
