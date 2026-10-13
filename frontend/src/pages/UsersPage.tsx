import { useEffect, useState, type FormEvent } from "react";
import { api, atLeast, type CurrentUser } from "../api";
import type {UserData} from "../types";
import { Empty, Field, Modal, PanelHeading, Status, pretty } from "../ui";

const ROLES = ["viewer", "operator", "manager", "admin"] as const;

const blank = { username: "", password: "", role: "operator" };

export default function UsersPage({
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
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    target: UserData;
    role?: string;
    active?: boolean;
  } | null>(null);

  const isAdmin = atLeast(user, "admin");

  useEffect(() => {
    let cancelled = false;

    api<UserData[]>("/api/users")
      .then(rows => {
        if (!cancelled) setUsers(rows);
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
  }, [fail, refreshKey]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);

    try {
      await api("/api/users", {
        method: "POST",
        body: JSON.stringify(form)
      });
      notice("User create ho gaya.");
      setShowForm(false);
      setForm(blank);
      const rows = await api<UserData[]>("/api/users");
      setUsers(rows);
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

  async function applyAction() {
    if (!confirmAction) return;

    try {
      if (confirmAction.role !== undefined) {
        await api(`/api/users/${confirmAction.target.id}/role`, {
          method: "PATCH",
          body: JSON.stringify({ role: confirmAction.role })
        });
        notice(
          `${confirmAction.target.username} ka role ${confirmAction.role} ho gaya.`
        );
      } else if (confirmAction.active !== undefined) {
        await api(`/api/users/${confirmAction.target.id}/active`, {
          method: "PATCH",
          body: JSON.stringify({ active: confirmAction.active })
        });
        notice(
          confirmAction.active
            ? `${confirmAction.target.username} activate ho gaya.`
            : `${confirmAction.target.username} deactivate ho gaya.`
        );
      }
      const rows = await api<UserData[]>("/api/users");
      setUsers(rows);
    } catch (error) {
      fail(error);
    } finally {
      setConfirmAction(null);
    }
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Users & roles"
        subtitle="Role changes are audit-logged by the backend"
        action={
          isAdmin ? (
            <button className="primary-button" onClick={() => setShowForm(true)}>
              Add user
            </button>
          ) : null
        }
      />

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              {isAdmin && <th></th>}
            </tr>
          </thead>
          <tbody>
            {users.map(row => (
              <tr key={row.id}>
                <td>
                  <b>{row.username}</b>
                  {row.id === user.id && (
                    <span style={{ fontSize: 9, color: "#66768b" }}> (you)</span>
                  )}
                </td>
                <td>{pretty(row.role)}</td>
                <td>
                  <Status active={row.active} />
                </td>
                <td>{new Date(row.created_at).toLocaleDateString()}</td>
                {isAdmin && (
                  <td>
                    <div style={{ display: "flex", gap: 10 }}>
                      <select
                        value={row.role}
                        disabled={row.id === user.id}
                        onChange={e =>
                          setConfirmAction({ target: row, role: e.target.value })
                        }
                        style={{
                          padding: "5px 7px",
                          border: "1px solid #e7ecf2",
                          borderRadius: 6,
                          fontSize: 10
                        }}
                      >
                        {ROLES.map(role => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                      <button
                        className="text-button"
                        disabled={row.id === user.id}
                        onClick={() =>
                          setConfirmAction({
                            target: row,
                            active: !row.active
                          })
                        }
                      >
                        {row.active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!users.length && !loading && (
          <Empty text="No users found." />
        )}
      </div>

      {showForm && (
        <Modal
          title="Add user"
          subtitle="Password must be at least 12 characters."
          onClose={() => setShowForm(false)}
        >
          <form className="form-grid modal-form" onSubmit={submit}>
            <Field label="Username">
              <input
                required
                minLength={3}
                value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })}
              />
            </Field>
            <Field label="Password">
              <input
                required
                type="password"
                minLength={12}
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
              />
            </Field>
            <Field label="Role">
              <select
                value={form.role}
                onChange={e => setForm({ ...form, role: e.target.value })}
              >
                {ROLES.map(role => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
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
                {saving ? "Saving…" : "Create user"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {confirmAction && (
        <Modal
          title="Confirm change"
          subtitle={`Update ${confirmAction.target.username}?`}
          onClose={() => setConfirmAction(null)}
        >
          <p className="hint">
            {confirmAction.role !== undefined
              ? `Role will become "${confirmAction.role}".`
              : confirmAction.active
                ? "The account will be able to log in again."
                : "The account will be blocked from logging in."}
          </p>
          <div className="form-actions">
            <button
              className="secondary-button"
              onClick={() => setConfirmAction(null)}
            >
              Cancel
            </button>
            <button className="primary-button" onClick={() => void applyAction()}>
              Confirm
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
