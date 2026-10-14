import { useEffect, useState, type FormEvent } from "react";
import { API_BASE, api, atLeast, getToken, type CurrentUser } from "../api";
import type {AppSettings, BackupInfo, SystemInfo, UserData} from "../types";
import { Empty, Field, Modal, PanelHeading, Status, pretty } from "../ui";

interface RestoreResult {
  filename: string;
  restored: boolean;
  restored_at: string;
}

const ROLES = ["viewer", "operator", "manager", "admin"] as const;

const blankUser = { username: "", password: "", role: "operator" };

export default function SettingsPage({
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
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKeys, setSavingKeys] = useState<string[]>([]);
  const [creatingBackup, setCreatingBackup] = useState(false);
  const [creatingJsonBackup, setCreatingJsonBackup] = useState(false);
  const [restorePickerOpen, setRestorePickerOpen] = useState(false);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [restoring, setRestoring] = useState(false);

  // User management (admin only).
  const [users, setUsers] = useState<UserData[]>([]);
  const [showAddUser, setShowAddUser] = useState(false);
  const [addUserForm, setAddUserForm] = useState(blankUser);
  const [savingUser, setSavingUser] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<UserData | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [renameTarget, setRenameTarget] = useState<UserData | null>(null);
  const [newUsername, setNewUsername] = useState("");
  const [confirmAction, setConfirmAction] = useState<{
    target: UserData;
    role?: string;
    active?: boolean;
  } | null>(null);

  const isAdmin = atLeast(user, "admin");

  useEffect(() => {
    let cancelled = false;

    const tasks: Promise<unknown>[] = [api<AppSettings>("/api/settings")];

    if (isAdmin) {
      tasks.push(api<BackupInfo[]>("/api/backups"));
      tasks.push(api<SystemInfo>("/api/settings/system"));
      tasks.push(api<UserData[]>("/api/users"));
    }

    Promise.allSettled(tasks)
      .then(([set, bak, sys, usr]) => {
        if (cancelled) return;
        if (set.status === "fulfilled") setSettings(set.value as AppSettings);
        else fail(set.reason);
        if (bak && bak.status === "fulfilled") {
          setBackups(bak.value as BackupInfo[]);
        }
        if (sys && sys.status === "fulfilled") {
          setSystemInfo(sys.value as SystemInfo);
        }
        if (usr && usr.status === "fulfilled") {
          setUsers(usr.value as UserData[]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, isAdmin, refreshKey]);

  async function reloadUsers() {
    const rows = await api<UserData[]>("/api/users");
    setUsers(rows);
  }

  async function submitAddUser(event: FormEvent) {
    event.preventDefault();
    setSavingUser(true);

    try {
      await api("/api/users", {
        method: "POST",
        body: JSON.stringify(addUserForm)
      });
      notice("User create ho gaya.");
      setShowAddUser(false);
      setAddUserForm(blankUser);
      await reloadUsers();
    } catch (error) {
      fail(error);
    } finally {
      setSavingUser(false);
    }
  }

  async function applyUserAction() {
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
      await reloadUsers();
    } catch (error) {
      fail(error);
    } finally {
      setConfirmAction(null);
    }
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (!passwordTarget) return;
    setSavingUser(true);

    try {
      await api(`/api/users/${passwordTarget.id}/password`, {
        method: "PATCH",
        body: JSON.stringify({ password: newPassword })
      });
      notice(`${passwordTarget.username} ka password change ho gaya.`);
      setPasswordTarget(null);
      setNewPassword("");
    } catch (error) {
      fail(error);
    } finally {
      setSavingUser(false);
    }
  }

  async function submitRename(event: FormEvent) {
    event.preventDefault();
    if (!renameTarget) return;
    setSavingUser(true);

    try {
      await api(`/api/users/${renameTarget.id}/username`, {
        method: "PATCH",
        body: JSON.stringify({ username: newUsername })
      });
      notice(`Username "${renameTarget.username}" → "${newUsername}".`);
      setRenameTarget(null);
      setNewUsername("");
      await reloadUsers();
    } catch (error) {
      fail(error);
    } finally {
      setSavingUser(false);
    }
  }

  function patch(partial: Partial<AppSettings>) {
    setSettings(prev => (prev ? { ...prev, ...partial } : prev));
  }

  // Save a specific group of keys. The backend accepts partial payloads,
  // so each section only sends what it owns.
  async function saveKeys(keys: string[]) {
    if (!settings) return;
    const payload: Record<string, string> = {};
    for (const key of keys) {
      payload[key] = settings[key as keyof AppSettings];
    }

    setSavingKeys(keys);

    try {
      const updated = await api<AppSettings>("/api/settings", {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      setSettings(updated);
      notice("Settings save ho gayi.");
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setSavingKeys([]);
    }
  }

  const isSaving = (keys: string[]) =>
    keys.length > 0 && savingKeys.length > 0 &&
    keys.every(k => savingKeys.includes(k));

  async function createBackup() {
    setCreatingBackup(true);

    try {
      const created = await api<BackupInfo>("/api/backups", {
        method: "POST"
      });
      notice(`Backup ban gaya: ${created.filename}`);
      const rows = await api<BackupInfo[]>("/api/backups");
      setBackups(rows);
    } catch (error) {
      fail(error);
    } finally {
      setCreatingBackup(false);
    }
  }

  async function createJsonBackup() {
    setCreatingJsonBackup(true);

    try {
      const created = await api<BackupInfo>("/api/backups/json", {
        method: "POST"
      });
      notice(`JSON backup ban gaya: ${created.filename}`);
      const rows = await api<BackupInfo[]>("/api/backups");
      setBackups(rows);
    } catch (error) {
      fail(error);
    } finally {
      setCreatingJsonBackup(false);
    }
  }

  async function downloadJsonBackup(filename: string) {
    try {
      const response = await fetch(
        `${API_BASE}/api/backups/json/${encodeURIComponent(filename)}/download`,
        {
          headers: {
            Authorization: `Bearer ${getToken()}`
          }
        }
      );
      if (!response.ok) {
        throw new Error(`Download failed: HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      fail(error);
    }
  }

  async function restore() {
    const picked = backups.find(b => b.filename === selectedFilename);
    if (!picked) return;

    setRestoring(true);
    const base =
      picked.kind === "json"
        ? `/api/backups/json/${encodeURIComponent(picked.filename)}`
        : `/api/backups/${encodeURIComponent(picked.filename)}`;

    try {
      const result = await api<RestoreResult>(`${base}/restore`, {
        method: "POST",
        body: JSON.stringify({ confirm: confirmText })
      });
      notice(
        result.restored
          ? `Restore complete: ${result.filename}`
          : "Restore reported no changes."
      );
      setRestorePickerOpen(false);
      setSelectedFilename("");
      setConfirmText("");
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setRestoring(false);
    }
  }

  const PROFILE_KEYS = [
    "business_name",
    "business_phone",
    "business_address",
    "currency"
  ];
  const INVENTORY_KEYS = [
    "default_location",
    "default_rate_unit",
    "allow_negative_stock",
    "low_stock_threshold"
  ];
  const REPORT_KEYS = ["receipt_note"];

  return (
    <>
      <section className="panel">
        <PanelHeading
          title="Business profile"
          subtitle="Shown on printed reports and used for all money formatting"
        />
        {!settings && loading && <p className="hint">Loading…</p>}
        {settings && (
          <form
            className="form-grid"
            onSubmit={e => {
              e.preventDefault();
              void saveKeys(PROFILE_KEYS);
            }}
          >
            <Field label="Business name">
              <input
                value={settings.business_name}
                onChange={e => patch({ business_name: e.target.value })}
              />
            </Field>
            <Field label="Phone (optional)">
              <input
                value={settings.business_phone}
                placeholder="+92 300 1234567"
                onChange={e => patch({ business_phone: e.target.value })}
              />
            </Field>
            <Field label="Address (optional)">
              <input
                value={settings.business_address}
                placeholder="Gold Market, Lahore"
                onChange={e => patch({ business_address: e.target.value })}
              />
            </Field>
            <Field label="Currency code">
              <input
                value={settings.currency}
                maxLength={10}
                onChange={e => patch({ currency: e.target.value })}
              />
            </Field>
            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={isSaving(PROFILE_KEYS) || !isAdmin}
              >
                {isSaving(PROFILE_KEYS) ? "Saving…" : "Save profile"}
              </button>
            </div>
            {!isAdmin && (
              <p className="security-note">
                Settings sirf admin edit kar sakta hai.
              </p>
            )}
          </form>
        )}
      </section>

      <section className="panel">
        <PanelHeading
          title="Inventory & trading"
          subtitle="Defaults for new transactions and stock warnings"
        />
        {settings && (
          <form
            className="form-grid"
            onSubmit={e => {
              e.preventDefault();
              void saveKeys(INVENTORY_KEYS);
            }}
          >
            <Field label="Default stock location">
              <input
                value={settings.default_location}
                onChange={e => patch({ default_location: e.target.value })}
              />
            </Field>
            <Field label="Default rate unit">
              <select
                value={settings.default_rate_unit}
                onChange={e =>
                  patch({
                    default_rate_unit: e.target.value as AppSettings["default_rate_unit"]
                  })
                }
              >
                <option value="tola">Tola</option>
                <option value="gram">Gram</option>
                <option value="kilogram">Kilogram</option>
              </select>
            </Field>
            <Field label="Allow negative stock">
              <select
                value={settings.allow_negative_stock}
                onChange={e => patch({ allow_negative_stock: e.target.value })}
              >
                <option value="false">No — block negative stock</option>
                <option value="true">Yes — allow negative stock</option>
              </select>
            </Field>
            <Field label="Low stock warning (grams)">
              <input
                type="number"
                min="0"
                step="any"
                value={settings.low_stock_threshold}
                placeholder="0 = off"
                onChange={e => patch({ low_stock_threshold: e.target.value })}
              />
            </Field>
            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={isSaving(INVENTORY_KEYS) || !isAdmin}
              >
                {isSaving(INVENTORY_KEYS) ? "Saving…" : "Save inventory settings"}
              </button>
            </div>
          </form>
        )}
      </section>

      <section className="panel">
        <PanelHeading
          title="Reports & printing"
          subtitle="Footer note printed at the bottom of every report"
        />
        {settings && (
          <form
            className="form-grid"
            onSubmit={e => {
              e.preventDefault();
              void saveKeys(REPORT_KEYS);
            }}
          >
            <Field label="Report footer note (optional)">
              <input
                value={settings.receipt_note}
                maxLength={255}
                placeholder="Thank you for your business"
                onChange={e => patch({ receipt_note: e.target.value })}
              />
            </Field>
            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={isSaving(REPORT_KEYS) || !isAdmin}
              >
                {isSaving(REPORT_KEYS) ? "Saving…" : "Save report settings"}
              </button>
            </div>
          </form>
        )}
      </section>

      {isAdmin && (
        <section className="panel">
          <PanelHeading
            title="System status"
            subtitle="Read-only facts about this installation (no secrets)"
          />
          {systemInfo ? (
            <div className="table-scroll">
              <table>
                <tbody>
                  <tr>
                    <td>App version</td>
                    <td>{systemInfo.app_version}</td>
                  </tr>
                  <tr>
                    <td>Database</td>
                    <td>{systemInfo.database_backend}</td>
                  </tr>
                  <tr>
                    <td>Backups encrypted</td>
                    <td>{systemInfo.backup_encrypted ? "Yes (AES-256)" : "No"}</td>
                  </tr>
                  <tr>
                    <td>Backup retention</td>
                    <td>
                      {systemInfo.backup_retention_days} days · keep newest{" "}
                      {systemInfo.backup_keep_min}
                    </td>
                  </tr>
                  <tr>
                    <td>Login rate limit</td>
                    <td>
                      {systemInfo.login_rate_limit === 0
                        ? "Disabled"
                        : `${systemInfo.login_rate_limit}/min per user`}
                    </td>
                  </tr>
                  <tr>
                    <td>Schema</td>
                    <td>
                      {systemInfo.auto_create_tables
                        ? "Auto-create (dev)"
                        : "Alembic migrations only"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : loading ? (
            <p className="hint">Loading…</p>
          ) : (
            <Empty text="System status unavailable." />
          )}
        </section>
      )}

      {isAdmin && (
        <section className="panel">
          <PanelHeading
            title="Users & access"
            subtitle="Add users, change roles, reset passwords or rename accounts. Every change is audit-logged."
            action={
              <button
                className="primary-button"
                onClick={() => {
                  setAddUserForm(blankUser);
                  setShowAddUser(true);
                }}
              >
                Add user
              </button>
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
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map(row => (
                  <tr key={row.id}>
                    <td>
                      <b>{row.username}</b>
                      {row.id === user.id && (
                        <span style={{ fontSize: 9, color: "#66768b" }}>
                          {" "}
                          (you)
                        </span>
                      )}
                    </td>
                    <td>{pretty(row.role)}</td>
                    <td>
                      <Status active={row.active} />
                    </td>
                    <td>{new Date(row.created_at).toLocaleDateString()}</td>
                    <td>
                      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                        <select
                          value={row.role}
                          disabled={row.id === user.id}
                          onChange={e =>
                            setConfirmAction({
                              target: row,
                              role: e.target.value
                            })
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
                          onClick={() => {
                            setPasswordTarget(row);
                            setNewPassword("");
                          }}
                        >
                          Password
                        </button>
                        <button
                          className="text-button"
                          onClick={() => {
                            setRenameTarget(row);
                            setNewUsername(row.username);
                          }}
                        >
                          Rename
                        </button>
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
                  </tr>
                ))}
              </tbody>
            </table>
            {!users.length && !loading && (
              <Empty text="No users found." />
            )}
          </div>
        </section>
      )}

      <section className="panel">
        <PanelHeading
          title="Database backups"
          subtitle="JSON backups save all data to the backups folder. Restore lets you pick which one to load back."
          action={
            isAdmin ? (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="primary-button"
                  onClick={() => void createJsonBackup()}
                  disabled={creatingJsonBackup}
                >
                  {creatingJsonBackup ? "Creating…" : "Backup (JSON)"}
                </button>
                <button
                  className="secondary-button"
                  onClick={() => {
                    setSelectedFilename("");
                    setConfirmText("");
                    setRestorePickerOpen(true);
                  }}
                  disabled={backups.length === 0}
                >
                  Restore
                </button>
                <button
                  className="secondary-button"
                  onClick={() => void createBackup()}
                  disabled={creatingBackup}
                  title="Full PostgreSQL dump (requires pg_dump on server)"
                >
                  {creatingBackup ? "Creating…" : "Full DB dump"}
                </button>
              </div>
            ) : null
          }
        />

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Type</th>
                <th>Size</th>
                <th>Created</th>
                {isAdmin && <th></th>}
              </tr>
            </thead>
            <tbody>
              {backups.map(b => (
                <tr key={b.filename}>
                  <td>
                    <b>{b.filename}</b>
                  </td>
                  <td>
                    {b.kind === "json" ? "JSON data" : "pg_dump"}
                    {b.encrypted ? " · Encrypted" : ""}
                  </td>
                  <td>{(b.size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                  <td>{new Date(b.created_at).toLocaleString()}</td>
                  {isAdmin && (
                    <td style={{ whiteSpace: "nowrap" }}>
                      {b.kind === "json" && (
                        <button
                          className="text-button"
                          onClick={() => void downloadJsonBackup(b.filename)}
                        >
                          Download
                        </button>
                      )}{" "}
                      <button
                        className="text-button danger"
                        onClick={() => {
                          setSelectedFilename(b.filename);
                          setConfirmText("");
                          setRestorePickerOpen(true);
                        }}
                      >
                        Restore
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {!backups.length && !loading && (
            <Empty text="No backups yet. Create one before risky changes." />
          )}
        </div>
        {!isAdmin && (
          <p className="hint" style={{ padding: "0 19px 16px" }}>
            Backup and restore are restricted to the admin role.
          </p>
        )}
      </section>

      {restorePickerOpen && (
        <Modal
          title="Restore a backup"
          subtitle="This OVERWRITES the current data with the selected backup. This cannot be undone."
          onClose={() => setRestorePickerOpen(false)}
        >
          <form
            className="form-grid modal-form"
            onSubmit={e => {
              e.preventDefault();
              void restore();
            }}
          >
            <Field label="Choose a backup">
              <select
                required
                value={selectedFilename}
                onChange={e => {
                  setSelectedFilename(e.target.value);
                  setConfirmText("");
                }}
              >
                <option value="" disabled>
                  — Select backup —
                </option>
                {backups.map(b => (
                  <option key={b.filename} value={b.filename}>
                    {b.filename} · {b.kind === "json" ? "JSON data" : "pg_dump"}
                    {b.encrypted ? " · Encrypted" : ""} ·{" "}
                    {(b.size_bytes / 1024 / 1024).toFixed(2)} MB ·{" "}
                    {new Date(b.created_at).toLocaleString()}
                  </option>
                ))}
              </select>
            </Field>
            {selectedFilename && (
              <Field label="Type the filename to confirm">
                <input
                  required
                  placeholder={selectedFilename}
                  value={confirmText}
                  onChange={e => setConfirmText(e.target.value)}
                />
              </Field>
            )}
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setRestorePickerOpen(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={restoring || confirmText !== selectedFilename || !selectedFilename}
              >
                {restoring ? "Restoring…" : "Restore selected backup"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showAddUser && (
        <Modal
          title="Add user"
          subtitle="Password must be at least 12 characters."
          onClose={() => setShowAddUser(false)}
        >
          <form className="form-grid modal-form" onSubmit={submitAddUser}>
            <Field label="Username">
              <input
                required
                minLength={3}
                value={addUserForm.username}
                onChange={e =>
                  setAddUserForm({ ...addUserForm, username: e.target.value })
                }
              />
            </Field>
            <Field label="Password">
              <input
                required
                type="password"
                minLength={12}
                value={addUserForm.password}
                onChange={e =>
                  setAddUserForm({ ...addUserForm, password: e.target.value })
                }
              />
            </Field>
            <Field label="Role">
              <select
                value={addUserForm.role}
                onChange={e =>
                  setAddUserForm({ ...addUserForm, role: e.target.value })
                }
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
                onClick={() => setShowAddUser(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={savingUser}
              >
                {savingUser ? "Saving…" : "Create user"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {passwordTarget && (
        <Modal
          title="Change password"
          subtitle={`Set a new password for ${passwordTarget.username}. Minimum 12 characters.`}
          onClose={() => setPasswordTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitPassword}>
            <Field label="New password">
              <input
                required
                type="password"
                minLength={12}
                autoFocus
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setPasswordTarget(null)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={savingUser}
              >
                {savingUser ? "Saving…" : "Change password"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {renameTarget && (
        <Modal
          title="Change username"
          subtitle={`Rename ${renameTarget.username}. The user logs in with the new name.`}
          onClose={() => setRenameTarget(null)}
        >
          <form className="form-grid modal-form" onSubmit={submitRename}>
            <Field label="New username">
              <input
                required
                minLength={3}
                maxLength={80}
                autoFocus
                value={newUsername}
                onChange={e => setNewUsername(e.target.value)}
              />
            </Field>
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setRenameTarget(null)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={savingUser || newUsername === renameTarget.username}
              >
                {savingUser ? "Saving…" : "Change username"}
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
            <button
              className="primary-button"
              onClick={() => void applyUserAction()}
            >
              Confirm
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
