import { useEffect, useState, type FormEvent } from "react";
import { API_BASE, api, atLeast, getToken, type CurrentUser } from "../api";
import type {AppSettings, BackupInfo, SystemInfo} from "../types";
import { Empty, Field, Modal, PanelHeading } from "../ui";

interface RestoreResult {
  filename: string;
  restored: boolean;
  restored_at: string;
}

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

  const isAdmin = atLeast(user, "admin");

  useEffect(() => {
    let cancelled = false;

    const tasks: Promise<unknown>[] = [api<AppSettings>("/api/settings")];

    if (isAdmin) {
      tasks.push(api<BackupInfo[]>("/api/backups"));
      tasks.push(api<SystemInfo>("/api/settings/system"));
    }

    Promise.allSettled(tasks)
      .then(([set, bak, sys]) => {
        if (cancelled) return;
        if (set.status === "fulfilled") setSettings(set.value as AppSettings);
        else fail(set.reason);
        if (bak && bak.status === "fulfilled") {
          setBackups(bak.value as BackupInfo[]);
        }
        if (sys && sys.status === "fulfilled") {
          setSystemInfo(sys.value as SystemInfo);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, isAdmin, refreshKey]);

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
    </>
  );
}
