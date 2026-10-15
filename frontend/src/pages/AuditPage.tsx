import { useEffect, useState } from "react";
import { api, atLeast, type CurrentUser } from "../api";
import type {AuditEntry} from "../types";
import { Empty, PanelHeading, pretty } from "../ui";

interface AuditResponse {
  items?: AuditEntry[];
}

export default function AuditPage({
  user,
  fail,
  refreshKey
}: {
  user: CurrentUser;
  fail: (e: unknown) => void;
  refreshKey: number;
}) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");

  const isAdmin = atLeast(user, "admin");

  useEffect(() => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    const params = new URLSearchParams({ limit: "200" });
    if (username.trim()) params.set("username", username.trim());
    if (action.trim()) params.set("action", action.trim());
    if (entityType.trim()) params.set("entity_type", entityType.trim());

    api<AuditEntry[] | AuditResponse>(`/api/audit?${params.toString()}`)
      .then(data => {
        if (cancelled) return;
        setEntries(Array.isArray(data) ? data : data.items ?? []);
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
  }, [action, entityType, fail, isAdmin, refreshKey, username]);

  if (!isAdmin) {
    return (
      <section className="panel">
        <PanelHeading title="Audit log" subtitle="Admin only" />
        <Empty text="Yeh page sirf admin ke liye hai." />
      </section>
    );
  }

  return (
    <section className="panel">
      <PanelHeading
        title="Audit log"
        subtitle="Who changed what — written by the backend on every important action"
        action={
          <div className="panel-tools">
            <input
              placeholder="Username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              style={inputStyle}
            />
            <input
              placeholder="Action e.g. product.create"
              value={action}
              onChange={e => setAction(e.target.value)}
              style={inputStyle}
            />
            <input
              placeholder="Entity e.g. transaction"
              value={entityType}
              onChange={e => setEntityType(e.target.value)}
              style={inputStyle}
            />
          </div>
        }
      />

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>User</th>
              <th>Action</th>
              <th>Entity</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(entry => (
              <tr key={entry.id}>
                <td>{new Date(entry.created_at).toLocaleString()}</td>
                <td>
                  <b>{entry.username}</b>
                </td>
                <td>{pretty(entry.action)}</td>
                <td>
                  {pretty(entry.entity_type)}
                  {entry.entity_id ? ` #${entry.entity_id}` : ""}
                </td>
                <td>{entry.detail || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!entries.length && !loading && (
          <Empty text="No audit entries match these filters." />
        )}
      </div>
    </section>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "7px 9px",
  border: "1px solid var(--border)",
  borderRadius: 7,
  fontSize: 10,
  color: "var(--text-2)",
  minWidth: 130
};
