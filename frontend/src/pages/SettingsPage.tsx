import { useEffect, useState, type FormEvent } from "react";
import { API_BASE, api, atLeast, getToken, type CurrentUser } from "../api";
import type {AppSettings, BackupInfo} from "../types";
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
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
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
    }

    Promise.allSettled(tasks)
      .then(([set, bak]) => {
        if (cancelled) return;
        if (set.status === "fulfilled") setSettings(set.value as AppSettings);
        else fail(set.reason);
        if (bak && bak.status === "fulfilled") {
          setBackups(bak.value as BackupInfo[]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fail, isAdmin, refreshKey]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);

    try {
      const updated = await api<AppSettings>("/api/settings", {
        method: "PUT",
        body: JSON.stringify(settings)
      });
      setSettings(updated);
      notice("Settings save ho gayi.");
      bump();
    } catch (error) {
      fail(error);
    } finally {
      setSaving(false);
    }
  }

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

  return (
    <>
      <section className="panel">
        <PanelHeading
          title="Business settings"
          subtitle="Stored in the settings table and editable by managers"
        />
        {!settings && loading && <p className="hint">Loading…</p>}
        {settings && (
          <form className="form-grid" onSubmit={submit}>
            <Field label="Business name">
              <input
                value={settings.business_name}
                onChange={e =>
                  setSettings({ ...settings, business_name: e.target.value })
                }
              />
            </Field>
            <Field label="Currency">
              <input
                value={settings.currency}
                onChange={e =>
                  setSettings({ ...settings, currency: e.target.value })
                }
              />
            </Field>
            <Field label="Default stock location">
              <input
                value={settings.default_location}
                onChange={e =>
                  setSettings({ ...settings, default_location: e.target.value })
                }
              />
            </Field>
            <Field label="Allow negative stock">
              <select
                value={settings.allow_negative_stock}
                onChange={e =>
                  setSettings({
                    ...settings,
                    allow_negative_stock: e.target.value
                  })
                }
              >
                <option value="false">No — block negative stock</option>
                <option value="true">Yes — allow negative stock</option>
              </select>
            </Field>
            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={saving || !isAdmin}
              >
                {saving ? "Saving…" : "Save settings"}
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
                  <td>{b.kind === "json" ? "JSON data" : "pg_dump"}</td>
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
                    {b.filename} · {b.kind === "json" ? "JSON data" : "pg_dump"} ·{" "}
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
