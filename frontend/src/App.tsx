import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent
} from "react";
import {
  ArrowLeftRight,
  Boxes,
  ClipboardList,
  Coins,
  History,
  LayoutDashboard,
  LogOut,
  Moon,
  Package,
  RefreshCw,
  ScrollText,
  Settings as SettingsIcon,
  ShieldCheck,
  ShoppingCart,
  ShoppingBag,
  Store,
  Sun,
  Users,
  Wallet
} from "lucide-react";
import {
  api,
  clearToken,
  errorText,
  getToken,
  login,
  setCurrency,
  UNAUTHORIZED_EVENT,
  type CurrentUser
} from "./api";
import type { AppSettings } from "./types";
import DashboardPage from "./pages/DashboardPage";
import ProductsPage from "./pages/ProductsPage";
import RatesPage from "./pages/RatesPage";
import InventoryPage from "./pages/InventoryPage";
import POSPage from "./pages/POSPage";
import PurchaseSalePage from "./pages/PurchaseSalePage";
import TransactionsPage from "./pages/TransactionsPage";
import PartiesPage from "./pages/PartiesPage";
import MovementsPage from "./pages/MovementsPage";
import ReportsPage from "./pages/ReportsPage";
import AuditPage from "./pages/AuditPage";
import SettingsPage from "./pages/SettingsPage";
import { Field } from "./ui";

type Page =
  | "Dashboard"
  | "POS"
  | "Products"
  | "Metal Rates"
  | "Inventory"
  | "Purchases"
  | "Sales"
  | "Transactions"
  | "Parties"
  | "Stock Movements"
  | "Reports"
  | "Users"
  | "Audit Log"
  | "Settings";

const NAV: { label: Page; icon: typeof LayoutDashboard; min: "viewer" | "operator" | "manager" | "admin" }[] = [
  { label: "Dashboard", icon: LayoutDashboard, min: "viewer" },
  { label: "POS", icon: Store, min: "operator" },
  { label: "Products", icon: Package, min: "viewer" },
  { label: "Metal Rates", icon: Coins, min: "viewer" },
  { label: "Inventory", icon: Boxes, min: "viewer" },
  { label: "Purchases", icon: ShoppingCart, min: "operator" },
  { label: "Sales", icon: ShoppingBag, min: "operator" },
  { label: "Transactions", icon: ArrowLeftRight, min: "viewer" },
  { label: "Parties", icon: Users, min: "viewer" },
  { label: "Stock Movements", icon: ClipboardList, min: "manager" },
  { label: "Reports", icon: ScrollText, min: "viewer" },
  { label: "Audit Log", icon: History, min: "admin" },
  // Visible to managers so they can view settings; the page itself
  // restricts saving to admins only.
  { label: "Settings", icon: SettingsIcon, min: "manager" }
];

const RANK = { viewer: 0, operator: 1, manager: 2, admin: 3 } as const;

function allowed(role: string, min: (typeof NAV)[number]["min"]): boolean {
  return RANK[role as keyof typeof RANK] >= RANK[min];
}

export default function App() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [booting, setBooting] = useState(true);
  const [page, setPage] = useState<Page>("Dashboard");
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [darkTheme, setDarkTheme] = useState(
    () => document.documentElement.dataset.theme === "dark"
  );
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const noticeTimer = useRef<number | undefined>(undefined);

  // Restore an existing session.
  useEffect(() => {
    if (!getToken()) {
      setBooting(false);
      setLoading(false);
      return;
    }

    api<CurrentUser>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setBooting(false));
  }, []);

  // Drop back to login when the backend rejects the token.
  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener(UNAUTHORIZED_EVENT, onExpired);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onExpired);
  }, []);

  // Apply the money currency from settings (refreshed after any bump so
  // a currency change on the Settings page takes effect immediately).
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api<AppSettings>("/api/settings")
      .then(s => {
        if (!cancelled) setCurrency(s.currency);
      })
      .catch(() => {
        // Keep the default currency when settings are unreachable.
      });
    return () => {
      cancelled = true;
    };
  }, [user, refreshKey]);

  const fail = useCallback((err: unknown) => {
    setError(errorText(err));
  }, []);

  const noticeMessage = useCallback((message: string) => {
    setError("");
    setNotice(message);
    window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(""), 6000);
  }, []);

  const refresh = useCallback(() => {
    setRefreshKey(key => key + 1);
    setLoading(true);
    window.setTimeout(() => setLoading(false), 500);
  }, []);

  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setLoggingIn(true);
    setLoginError("");

    try {
      await login(loginForm.username.trim(), loginForm.password);
      const me = await api<CurrentUser>("/api/auth/me");
      setUser(me);
      setLoginForm({ username: "", password: "" });
      setPage("Dashboard");
      refresh();
    } catch (err) {
      setLoginError(errorText(err));
    } finally {
      setLoggingIn(false);
    }
  }

  function logout() {
    clearToken();
    setUser(null);
    setPage("Dashboard");
    setError("");
    setNotice("");
  }

  if (booting) {
    return (
      <div className="app-shell" style={{ display: "grid", placeItems: "center" }}>
        <p className="loading">Restoring session…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app-shell" style={{ display: "grid", placeItems: "center" }}>
        <section className="modal" style={{ width: "min(100%, 420px)" }}>
          <div className="modal-heading">
            <div>
              <h2>SNJ Gold Lab</h2>
              <p>Sign in with your account to continue.</p>
            </div>
            <ShieldCheck size={20} color="#b08a42" />
          </div>
          <form className="form-grid modal-form" onSubmit={submitLogin}>
            <Field label="Username">
              <input
                required
                autoComplete="username"
                value={loginForm.username}
                onChange={e =>
                  setLoginForm({ ...loginForm, username: e.target.value })
                }
              />
            </Field>
            <Field label="Password">
              <input
                required
                type="password"
                autoComplete="current-password"
                value={loginForm.password}
                onChange={e =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
              />
            </Field>
            {loginError && <p className="security-note">{loginError}</p>}
            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={loggingIn}
              >
                {loggingIn ? "Signing in…" : "Sign in"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }

  const navItems = NAV.filter(item => allowed(user.role, item.min));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Coins size={18} />
          </div>
          <div>
            <b>SNJ Gold Lab</b>
            <small>INVENTORY & TRANSACTIONS</small>
          </div>
        </div>

        <div className="workspace">
          <span className="workspace-avatar">
            {user.username.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <b>{user.username}</b>
            <small>{user.role.toUpperCase()}</small>
          </div>
        </div>

        <p className="nav-label">MENU</p>
        <nav>
          {navItems.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                className={`nav-item ${page === item.label ? "active" : ""}`}
                onClick={() => setPage(item.label)}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="secure-card">
            <ShieldCheck size={16} />
            <div>
              <b>JWT secured</b>
              <small>Every action is audit logged on the backend.</small>
            </div>
          </div>
          <button className="nav-item" onClick={logout}>
            <LogOut size={16} />
            <span>Sign out</span>
          </button>
          <p className="sidebar-footer">FastAPI · PostgreSQL · React</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs">
            SNJ Gold Lab <span>/</span> <b>{page}</b>
          </div>
          <div className="top-actions">
            <span className="date-label">
              {new Date().toLocaleDateString("en-GB")}
            </span>
            <button
              className="icon-button"
              title={darkTheme ? "Switch to light mode" : "Switch to dark mode"}
              onClick={() => {
                const next = !darkTheme;
                setDarkTheme(next);
                document.documentElement.dataset.theme = next ? "dark" : "light";
                localStorage.setItem(
                  "hisabpro_theme",
                  next ? "dark" : "light"
                );
              }}
            >
              {darkTheme ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <button
              className="icon-button"
              title="Refresh data"
              onClick={refresh}
            >
              <RefreshCw size={15} className={loading ? "spin" : ""} />
            </button>
            <span className="admin-chip">
              <span>
                <Wallet size={15} />
              </span>
              {user.username}
            </span>
          </div>
        </header>

        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">HISABPRO WORKSPACE</p>
              <h1>{page}</h1>
              <p>
                {page === "Dashboard"
                  ? "Live business numbers straight from PostgreSQL"
                  : `Signed in as ${user.username} (${user.role})`}
              </p>
            </div>
          </div>

          {error && (
            <div className="alert error">
              <span>{error}</span>
              <button onClick={() => setError("")}>✕</button>
            </div>
          )}
          {notice && (
            <div className="alert success">
              <span>{notice}</span>
              <button onClick={() => setNotice("")}>✕</button>
            </div>
          )}

          <PageBody
            page={page}
            user={user}
            fail={fail}
            notice={noticeMessage}
            refreshKey={refreshKey}
            bump={refresh}
            goTo={target => setPage(target as Page)}
          />

          <footer className="footer">
            <span>SNJ Gold Lab · Inventory & Transactions</span>
            <span>FastAPI backend · PostgreSQL · JWT auth</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function PageBody({
  page,
  user,
  fail,
  notice,
  refreshKey,
  bump,
  goTo
}: {
  page: Page;
  user: CurrentUser;
  fail: (e: unknown) => void;
  notice: (m: string) => void;
  refreshKey: number;
  bump: () => void;
  goTo: (page: string) => void;
}) {
  switch (page) {
    case "Dashboard":
      return (
        <DashboardPage
          user={user}
          fail={fail}
          goTo={goTo}
          refreshKey={refreshKey}
        />
      );
    case "Products":
      return (
        <ProductsPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
        />
      );
    case "Metal Rates":
      return (
        <RatesPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
        />
      );
    case "Inventory":
      return (
        <InventoryPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
        />
      );
    case "POS":
      return (
        <POSPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
          bump={bump}
        />
      );
    case "Purchases":
      return (
        <PurchaseSalePage
          kind="purchase"
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
          goTo={goTo}
        />
      );
    case "Sales":
      return (
        <PurchaseSalePage
          kind="sale"
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
          goTo={goTo}
        />
      );
    case "Transactions":
      return (
        <TransactionsPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
          bump={bump}
        />
      );
    case "Parties":
      return (
        <PartiesPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
        />
      );
    case "Stock Movements":
      return (
        <MovementsPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
          bump={bump}
        />
      );
    case "Reports":
      return <ReportsPage user={user} fail={fail} refreshKey={refreshKey} />;
    case "Audit Log":
      return <AuditPage user={user} fail={fail} refreshKey={refreshKey} />;
    case "Settings":
      return (
        <SettingsPage
          user={user}
          fail={fail}
          notice={notice}
          refreshKey={refreshKey}
          bump={bump}
        />
      );
    default:
      return null;
  }
}
