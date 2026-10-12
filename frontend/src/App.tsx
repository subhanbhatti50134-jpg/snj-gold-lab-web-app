import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity, ArrowDownLeft, ArrowLeftRight, ArrowUpRight, Boxes,
  Coins, LayoutDashboard, LockKeyhole, Package, Plus, RefreshCw,
  Search, ShieldCheck, ShoppingBag, ShoppingCart, Wallet, X
} from "lucide-react";
import { api, getApiKey, money, qty, setApiKey } from "./api";
import type { Product, MetalRate, InventoryRow, Transaction } from "./types";

type Page =
  | "Dashboard" | "Products" | "Metal Rates" | "Inventory"
  | "Purchases" | "Sales" | "Transactions";

const nav: { label: Page; icon: typeof LayoutDashboard }[] = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Products", icon: Package },
  { label: "Metal Rates", icon: Coins },
  { label: "Inventory", icon: Boxes },
  { label: "Purchases", icon: ShoppingCart },
  { label: "Sales", icon: ShoppingBag },
  { label: "Transactions", icon: ArrowLeftRight }
];

const blankProduct = {
  sku: "", name: "", category: "loose_metal", metal: "gold", purity: "99.99"
};

const GRAMS_PER_TOLA = 11.6638;

const blankRate = {
  metal: "gold", purity: "99.99", rate_per_gram: "",
  source_note: "Manually verified", verified_by: "Admin"
};

const blankTransaction = {
  product_id: "", party_name: "", gross_weight_grams: "",
  net_weight_grams: "", deduction_grams: "0", purity: "99.99",
  rate_per_gram: "", charges: "0", amount_paid: "0", payment_method: "cash",
  location: "Main Store", destination: "", notes: "", created_by: "Admin"
};

export default function App() {
  const [page, setPage] = useState<Page>("Dashboard");
  const [products, setProducts] = useState<Product[]>([]);
  const [rates, setRates] = useState<MetalRate[]>([]);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");

  const [apiKey, setKey] = useState(getApiKey());
  const [keyDraft, setKeyDraft] = useState(getApiKey());
  const [showKey, setShowKey] = useState(!getApiKey());

  const [showProductForm, setShowProductForm] = useState(false);
  const [showRateForm, setShowRateForm] = useState(false);
  const [productForm, setProductForm] = useState(blankProduct);
  const [rateForm, setRateForm] = useState(blankRate);
  const [txForm, setTxForm] = useState(blankTransaction);

  const load = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);

    setError("");

    const results = await Promise.allSettled([
      api<Product[]>("/api/products"),
      api<MetalRate[]>("/api/rates"),
      api<InventoryRow[]>("/api/inventory"),
      api<Transaction[]>("/api/transactions")
    ]);

    const failed: string[] = [];

    if (results[0].status === "fulfilled") setProducts(results[0].value);
    else failed.push("Products: " + errorText(results[0].reason));

    if (results[1].status === "fulfilled") setRates(results[1].value);
    else failed.push("Rates: " + errorText(results[1].reason));

    if (results[2].status === "fulfilled") setInventory(results[2].value);
    else failed.push("Inventory: " + errorText(results[2].reason));

    if (results[3].status === "fulfilled") setTransactions(results[3].value);
    else failed.push("Transactions: " + errorText(results[3].reason));

    if (failed.length) setError(failed.join(" • "));

    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const productMap = useMemo(
    () => new Map(products.map(product => [product.id, product])),
    [products]
  );

  const activeRates = rates.filter(rate => rate.active !== false);
  const goldRate = activeRates.find(rate => rate.metal.toLowerCase() === "gold");
  const silverRate = activeRates.find(rate => rate.metal.toLowerCase() === "silver");

  const stockGrams = inventory.reduce(
    (sum, row) => sum + Number(row.balance_grams || 0), 0
  );

  const purchases = transactions.filter(t => t.kind === "purchase");
  const sales = transactions.filter(t => t.kind === "sale");

  const totalDue = transactions.reduce(
    (sum, t) => sum + Math.max(0, Number(t.total_amount) - Number(t.amount_paid)),
    0
  );

  const totalSales = sales.reduce((sum, t) => sum + Number(t.total_amount || 0), 0);
  const totalPurchases = purchases.reduce((sum, t) => sum + Number(t.total_amount || 0), 0);

  const filteredProducts = products.filter(p =>
    `${p.name} ${p.sku} ${p.metal}`.toLowerCase().includes(search.toLowerCase())
  );

  const filteredRates = rates.filter(r =>
    `${r.metal} ${r.source_note || ""} ${r.verified_by || ""}`
      .toLowerCase().includes(search.toLowerCase())
  );

  const filteredInventory = inventory.filter(row =>
    `${productMap.get(row.product_id)?.name || ""} ${row.location}`
      .toLowerCase().includes(search.toLowerCase())
  );

  const filteredTransactions = transactions.filter(t =>
    `${t.reference} ${t.party_name} ${t.kind}`
      .toLowerCase().includes(search.toLowerCase())
  );

  function go(next: Page) {
    setPage(next);
    setSearch("");
    setError("");
    setNotice("");
  }

  function saveApiKey(event: FormEvent) {
    event.preventDefault();
    setApiKey(keyDraft);
    setKey(keyDraft);
    setShowKey(false);
    setNotice("API key current browser session ke liye save ho gayi.");
    void load();
  }

  async function saveProduct(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");

    try {
      await api("/api/products", {
        method: "POST",
        body: JSON.stringify({
          ...productForm,
          purity: Number(productForm.purity)
        })
      });

      setNotice("Product successfully save ho gaya.");
      setShowProductForm(false);
      setProductForm(blankProduct);
      await load(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function saveRate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");

    try {
      await api("/api/rates", {
        method: "POST",
        body: JSON.stringify({
          ...rateForm,
          purity: Number(rateForm.purity),
          rate_per_gram: Number(rateForm.rate_per_gram) / GRAMS_PER_TOLA
        })
      });

      setNotice("Metal rate save ho gaya.");
      setShowRateForm(false);
      setRateForm(blankRate);
      await load(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function saveTransaction(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");

    const kind = page === "Purchases" ? "purchase" : "sale";
    const net = Number(txForm.net_weight_grams);
    const gross = Number(txForm.gross_weight_grams);

    if (net <= 0 || gross <= 0) {
      setError("Gross aur net weight zero se zyada honi chahiye.");
      return;
    }

    if (net + Number(txForm.deduction_grams || 0) > gross + 0.0001) {
      setError("Net weight aur deduction ka total gross weight se zyada nahi ho sakta.");
      return;
    }

    const payload = {
      product_id: Number(txForm.product_id),
      quantity_grams: net,
      gross_weight_grams: gross,
      net_weight_grams: net,
      deduction_grams: Number(txForm.deduction_grams || 0),
      purity: Number(txForm.purity),
      ...(txForm.rate_per_gram
        ? { rate_per_gram: Number(txForm.rate_per_gram) / GRAMS_PER_TOLA }
        : {}),
      charges: Number(txForm.charges || 0),
      amount_paid: Number(txForm.amount_paid || 0),
      payment_method: txForm.payment_method,
      party_name: txForm.party_name,
      location: txForm.location,
      destination: txForm.destination || null,
      notes: txForm.notes,
      created_by: txForm.created_by
    };

    try {
      await api(`/api/${kind === "purchase" ? "purchases" : "sales"}`, {
        method: "POST",
        body: JSON.stringify(payload)
      });

      setNotice(`${kind === "purchase" ? "Purchase" : "Sale"} save ho gayi.`);
      setTxForm(blankTransaction);
      await load(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  const title = page === "Dashboard" ? "Business overview" : page;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Coins size={23} /></div>
          <div><b>HisabPro</b><small>METALS MANAGEMENT</small></div>
        </div>

        <div className="workspace">
          <div className="workspace-avatar">HP</div>
          <div><b>My Business</b><small>Inventory workspace</small></div>
        </div>

        <p className="nav-label">WORKSPACE</p>
        <nav>
          {nav.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                className={`nav-item ${page === item.label ? "active" : ""}`}
                onClick={() => go(item.label)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {item.label === "Transactions" && <small>{transactions.length}</small>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="secure-card">
            <ShieldCheck size={19} />
            <div>
              <b>Backend connection</b>
              <small>{apiKey ? "Session key configured" : "API key required for writes"}</small>
            </div>
          </div>
          <button className="nav-item" onClick={() => { setKeyDraft(apiKey); setShowKey(true); }}>
            <LockKeyhole size={17} /><span>API settings</span>
          </button>
          <p className="sidebar-footer">HisabPro · Inventory & Accounts</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs">Workspace <span>/</span> <b>{page}</b></div>
          <div className="top-actions">
            <span className="date-label">
              {new Date().toLocaleDateString("en-PK", {
                day: "2-digit", month: "short", year: "numeric"
              })}
            </span>
            <button className="icon-button" title="Refresh" onClick={() => void load(true)}>
              <RefreshCw size={17} className={refreshing ? "spin" : ""} />
            </button>
            <button className="admin-chip" onClick={() => { setKeyDraft(apiKey); setShowKey(true); }}>
              <span>AD</span> Administrator
            </button>
          </div>
        </header>

        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">HISABPRO / {page.toUpperCase()}</div>
              <h1>{title}</h1>
              <p>
                {page === "Dashboard"
                  ? "Gold, silver, stock aur transactions ka overview."
                  : `Manage your ${page.toLowerCase()} records.`}
              </p>
            </div>

            {page === "Products" && (
              <button className="primary-button" onClick={() => setShowProductForm(true)}>
                <Plus size={16} /> Add product
              </button>
            )}
            {page === "Metal Rates" && (
              <button className="primary-button" onClick={() => setShowRateForm(true)}>
                <Plus size={16} /> Add verified rate
              </button>
            )}
          </div>

          {error && (
            <div className="alert error">
              <Activity size={18} />
              <span>{error}</span>
              <button onClick={() => setError("")}><X size={16} /></button>
            </div>
          )}

          {notice && (
            <div className="alert success">
              <ShieldCheck size={18} />
              <span>{notice}</span>
              <button onClick={() => setNotice("")}><X size={16} /></button>
            </div>
          )}

          {loading && <div className="loading">Loading records from FastAPI…</div>}

          {page === "Dashboard" && (
            <>
              <section className="hero">
                <div>
                  <span className="hero-label">BUSINESS SNAPSHOT</span>
                  <h2>Welcome to HisabPro.</h2>
                  <p>Keep your metal inventory and transactions in control.</p>
                  <div className="hero-actions">
                    <button className="light-button" onClick={() => go("Purchases")}>
                      <Plus size={16} /> Record purchase
                    </button>
                    <button className="outline-button" onClick={() => go("Inventory")}>
                      View inventory
                    </button>
                  </div>
                </div>
                <div className="hero-coin">Au</div>
              </section>

              <div className="section-heading">
                <div><h2>Key metrics</h2><p>Based on records returned by your backend</p></div>
                <span className="live-badge">● LIVE DATA</span>
              </div>

              <section className="metrics">
                <Metric icon={<Boxes size={19}/>} label="Total stock" value={`${qty(stockGrams)} g`} foot={`${products.length} products`} />
                <Metric icon={<Wallet size={19}/>} label="Outstanding due" value={money(totalDue)} foot="Unpaid transaction balance" />
                <Metric icon={<ArrowUpRight size={19}/>} label="Total sales" value={money(totalSales)} foot={`${sales.length} sale records`} />
                <Metric icon={<ArrowDownLeft size={19}/>} label="Total purchases" value={money(totalPurchases)} foot={`${purchases.length} purchase records`} />
              </section>

              <section className="rate-strip">
                <div><b>Verified metal rates</b><small>Latest active rates</small></div>
                <RateMini label="Gold / tola" rate={goldRate} />
                <RateMini label="Silver / tola" rate={silverRate} />
                <button className="text-button" onClick={() => go("Metal Rates")}>Manage rates →</button>
              </section>

              <section className="panel dashboard-panel">
                <PanelHeading title="Recent transactions" subtitle="Latest movements in your ledger"
                  action={<button className="text-button" onClick={() => go("Transactions")}>View all →</button>} />
                <TransactionTable transactions={[...transactions].sort((a,b)=>b.id-a.id).slice(0,6)} productMap={productMap} />
              </section>
            </>
          )}

          {page === "Products" && (
            <section className="panel">
              <PanelHeading title="Product catalogue" subtitle={`${products.length} registered products`}
                search={search} setSearch={setSearch} />
              <div className="table-scroll">
                <table><thead><tr><th>Product</th><th>SKU</th><th>Category</th><th>Metal</th><th>Purity</th><th>Status</th></tr></thead>
                  <tbody>
                    {filteredProducts.map(p => (
                      <tr key={p.id}>
                        <td><b>{p.name}</b></td><td>{p.sku}</td><td>{pretty(p.category)}</td>
                        <td><MetalTag metal={p.metal}/></td><td>{qty(p.purity)}%</td>
                        <td><Status active={p.active}/></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!filteredProducts.length && <Empty text="No products found. Add a product to begin."/>}
              </div>
            </section>
          )}

          {page === "Metal Rates" && (
            <>
              <section className="rate-cards">
                <RateCard title="Gold rate" rate={goldRate}/>
                <RateCard title="Silver rate" rate={silverRate}/>
              </section>
              <section className="panel">
                <PanelHeading title="Metal rate records" subtitle="Manually verified rates" search={search} setSearch={setSearch}/>
                <div className="table-scroll">
                  <table><thead><tr><th>Metal</th><th>Purity</th><th>Rate / tola</th><th>Source note</th><th>Verified by</th><th>Status</th></tr></thead>
                    <tbody>{filteredRates.map(r => (
                      <tr key={r.id}><td><MetalTag metal={r.metal}/></td><td>{qty(r.purity)}%</td>
                        <td><b>{money(Number(r.rate_per_gram) * GRAMS_PER_TOLA)}</b></td><td>{r.source_note || "—"}</td>
                        <td>{r.verified_by || "—"}</td><td><Status active={r.active}/></td>
                      </tr>
                    ))}</tbody>
                  </table>
                  {!filteredRates.length && <Empty text="No rates found. Add a verified rate."/>}
                </div>
              </section>
            </>
          )}

          {page === "Inventory" && (
            <section className="panel">
              <PanelHeading title="Stock on hand" subtitle="Current balance by product and location" search={search} setSearch={setSearch}/>
              <div className="table-scroll">
                <table><thead><tr><th>Product</th><th>SKU</th><th>Location</th><th>Balance</th><th>Metal</th><th>Purity</th></tr></thead>
                  <tbody>{filteredInventory.map((row,i) => {
                    const p = productMap.get(row.product_id);
                    return <tr key={`${row.product_id}-${row.location}-${i}`}>
                      <td><b>{p?.name || `Product #${row.product_id}`}</b></td>
                      <td>{p?.sku || "—"}</td><td>{row.location}</td>
                      <td><b>{qty(row.balance_grams)} g</b></td>
                      <td><MetalTag metal={p?.metal || "other"}/></td>
                      <td>{p ? `${qty(p.purity)}%` : "—"}</td>
                    </tr>;
                  })}</tbody>
                </table>
                {!filteredInventory.length && <Empty text="No inventory rows found. Record a purchase to add stock."/>}
              </div>
            </section>
          )}

          {(page === "Purchases" || page === "Sales") && (
            <section className="panel">
              <PanelHeading title={page === "Purchases" ? "Record purchase" : "Record sale"}
                subtitle={page === "Purchases" ? "A successful purchase adds stock." : "The backend validates available stock."}/>
              {!products.length && <p className="hint">Pehle Products page se product create karein.</p>}
              <form className="form-grid" onSubmit={saveTransaction}>
                <Field label="Product">
                  <select required value={txForm.product_id} onChange={e => {
                    const p = products.find(x => x.id === Number(e.target.value));
                    setTxForm({...txForm, product_id:e.target.value, purity:p ? String(p.purity) : txForm.purity});
                  }}>
                    <option value="">Select product</option>
                    {products.filter(p=>p.active).map(p=><option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                  </select>
                </Field>
                <Field label="Party / supplier / customer">
                  <input required value={txForm.party_name} onChange={e=>setTxForm({...txForm,party_name:e.target.value})} placeholder="Party name"/>
                </Field>
                <Field label="Gross weight (g)">
                  <input required type="number" min="0.001" step="0.001" value={txForm.gross_weight_grams}
                    onChange={e=>setTxForm({...txForm,gross_weight_grams:e.target.value,
                      net_weight_grams:txForm.net_weight_grams || e.target.value})}/>
                </Field>
                <Field label="Deduction (g)">
                  <input type="number" min="0" step="0.001" value={txForm.deduction_grams}
                    onChange={e=>{
                      const deduction=Number(e.target.value || 0);
                      const gross=Number(txForm.gross_weight_grams || 0);
                      setTxForm({...txForm,deduction_grams:e.target.value,
                        net_weight_grams:String(Math.max(0,gross-deduction))});
                    }}/>
                </Field>
                <Field label="Net weight (g)">
                  <input required type="number" min="0.001" step="0.001" value={txForm.net_weight_grams}
                    onChange={e=>setTxForm({...txForm,net_weight_grams:e.target.value})}/>
                </Field>
                <Field label="Purity (%)">
                  <input required type="number" min="0.01" max="100" step="0.01" value={txForm.purity}
                    onChange={e=>setTxForm({...txForm,purity:e.target.value})}/>
                </Field>
                <Field label="Rate per tola (PKR, optional override)">
                  <input type="number" min="0.01" step="0.01" value={txForm.rate_per_gram}
                    onChange={e=>setTxForm({...txForm,rate_per_gram:e.target.value})} placeholder="Use matching active rate"/>
                </Field>
                <Field label="Charges (PKR)">
                  <input type="number" min="0" step="0.01" value={txForm.charges}
                    onChange={e=>setTxForm({...txForm,charges:e.target.value})}/>
                </Field>
                <Field label="Amount paid now (PKR)">
                  <input type="number" min="0" step="0.01" value={txForm.amount_paid}
                    onChange={e=>setTxForm({...txForm,amount_paid:e.target.value})}/>
                </Field>
                <Field label="Payment method">
                  <select value={txForm.payment_method} onChange={e=>setTxForm({...txForm,payment_method:e.target.value})}>
                    <option value="cash">Cash</option>
                    <option value="bank_transfer">Bank transfer</option>
                    <option value="other">Other</option>
                  </select>
                </Field>
                <Field label="Stock location">
                  <input required value={txForm.location} onChange={e=>setTxForm({...txForm,location:e.target.value})}/>
                </Field>
                <Field label="Destination (optional)">
                  <input value={txForm.destination} onChange={e=>setTxForm({...txForm,destination:e.target.value})}/>
                </Field>
                <Field label="Recorded by">
                  <input required value={txForm.created_by} onChange={e=>setTxForm({...txForm,created_by:e.target.value})}/>
                </Field>
                <Field label="Notes">
                  <textarea rows={3} value={txForm.notes} onChange={e=>setTxForm({...txForm,notes:e.target.value})}/>
                </Field>
                <div className="form-actions">
                  <button type="button" className="secondary-button" onClick={()=>setTxForm(blankTransaction)}>Clear</button>
                  <button type="submit" className="primary-button" disabled={!products.some(p=>p.active)}>
                    <Plus size={16}/> Save {page === "Purchases" ? "purchase" : "sale"}
                  </button>
                </div>
              </form>
            </section>
          )}

          {page === "Transactions" && (
            <section className="panel">
              <PanelHeading title="Transaction ledger" subtitle={`${transactions.length} recorded movements`} search={search} setSearch={setSearch}/>
              <TransactionTable transactions={filteredTransactions} productMap={productMap} showDue/>
            </section>
          )}

          <footer className="footer"><span>HisabPro · Inventory & Transactions</span><span>FastAPI backend · PostgreSQL</span></footer>
        </div>
      </main>

      {showKey && (
        <Modal title="Backend connection" subtitle="HISABPRO_API_KEY apni backend .env file se enter karein." onClose={()=>setShowKey(false)}>
          <form className="form-grid modal-form" onSubmit={saveApiKey}>
            <Field label="API key">
              <input type="password" autoComplete="current-password" value={keyDraft}
                onChange={e=>setKeyDraft(e.target.value)} placeholder="Enter backend API key"/>
            </Field>
            <div className="form-actions">
              <button type="button" className="secondary-button" onClick={()=>setShowKey(false)}>Cancel</button>
              <button className="primary-button" type="submit">Save & connect</button>
            </div>
            <p className="security-note">Key sirf current browser session mein rakhi jayegi. Isay public code ya chat mein share na karein. Production ke liye proper login/authentication zaroori hai.</p>
          </form>
        </Modal>
      )}

      {showProductForm && (
        <Modal title="Add product" subtitle="Register metal, biscuit, jewellery or lab material." onClose={()=>setShowProductForm(false)}>
          <form className="form-grid modal-form" onSubmit={saveProduct}>
            <Field label="Product name"><input required value={productForm.name} onChange={e=>setProductForm({...productForm,name:e.target.value})}/></Field>
            <Field label="SKU / code"><input required value={productForm.sku} onChange={e=>setProductForm({...productForm,sku:e.target.value})}/></Field>
            <Field label="Category"><select value={productForm.category} onChange={e=>setProductForm({...productForm,category:e.target.value})}>
              <option value="loose_metal">Loose metal</option><option value="biscuit">Biscuit</option>
              <option value="jewellery">Jewellery</option><option value="laboratory_material">Laboratory material</option>
            </select></Field>
            <Field label="Metal"><select value={productForm.metal} onChange={e=>setProductForm({...productForm,metal:e.target.value})}>
              <option value="gold">Gold</option><option value="silver">Silver</option><option value="other">Other</option>
            </select></Field>
            <Field label="Purity (%)"><input required type="number" min="0" max="100" step="0.01" value={productForm.purity} onChange={e=>setProductForm({...productForm,purity:e.target.value})}/></Field>
            <div className="form-actions">
              <button type="button" className="secondary-button" onClick={()=>setShowProductForm(false)}>Cancel</button>
              <button type="submit" className="primary-button">Save product</button>
            </div>
          </form>
        </Modal>
      )}

      {showRateForm && (
        <Modal title="Add verified metal rate" subtitle="Enter the rate checked by your business." onClose={()=>setShowRateForm(false)}>
          <form className="form-grid modal-form" onSubmit={saveRate}>
            <Field label="Metal"><select value={rateForm.metal} onChange={e=>setRateForm({...rateForm,metal:e.target.value})}>
              <option value="gold">Gold</option><option value="silver">Silver</option>
            </select></Field>
            <Field label="Purity (%)"><input required type="number" min="0.01" max="100" step="0.01" value={rateForm.purity} onChange={e=>setRateForm({...rateForm,purity:e.target.value})}/></Field>
            <Field label="Rate per tola (PKR)"><input required type="number" min="0.01" step="0.01" value={rateForm.rate_per_gram} onChange={e=>setRateForm({...rateForm,rate_per_gram:e.target.value})}/></Field>
            <Field label="Verified by"><input required value={rateForm.verified_by} onChange={e=>setRateForm({...rateForm,verified_by:e.target.value})}/></Field>
            <Field label="Source / note"><input value={rateForm.source_note} onChange={e=>setRateForm({...rateForm,source_note:e.target.value})}/></Field>
            <div className="form-actions">
              <button type="button" className="secondary-button" onClick={()=>setShowRateForm(false)}>Cancel</button>
              <button type="submit" className="primary-button">Save rate</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

function Metric({icon,label,value,foot}:{icon:ReactNode;label:string;value:string;foot:string}) {
  return <article className="metric-card"><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong><small>{foot}</small></article>;
}

function RateMini({label,rate}:{label:string;rate?:MetalRate}) {
  return <div className="rate-mini"><small>{label}</small><b>{rate ? money(Number(rate.rate_per_gram) * GRAMS_PER_TOLA) : "Not set"}</b></div>;
}

function RateCard({title,rate}:{title:string;rate?:MetalRate}) {
  return <article className="rate-card"><span>{title}</span><strong>{rate ? money(Number(rate.rate_per_gram) * GRAMS_PER_TOLA) : "No active rate"}</strong><small>{rate ? `${qty(rate.purity)}% purity · per tola` : "Add a verified rate to begin"}</small></article>;
}

function PanelHeading({title,subtitle,search,setSearch,action}:{title:string;subtitle?:string;search?:string;setSearch?:(v:string)=>void;action?:ReactNode}) {
  return <div className="panel-heading"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>
    <div className="panel-tools">{setSearch&&<label className="search"><Search size={15}/><input placeholder="Search…" value={search||""} onChange={e=>setSearch(e.target.value)}/></label>}{action}</div>
  </div>;
}

function TransactionTable({transactions,productMap,showDue=false}:{transactions:Transaction[];productMap:Map<number,Product>;showDue?:boolean}) {
  return <div className="table-scroll"><table><thead><tr>
    <th>Reference</th><th>Type</th><th>Party</th><th>Product</th><th>Weight</th><th>Total</th><th>Paid</th>{showDue&&<th>Due</th>}
  </tr></thead><tbody>
    {transactions.map(t=><tr key={t.id}>
      <td>{t.reference || `TX-${t.id}`}</td>
      <td><span className={`kind ${t.kind}`}>{t.kind}</span></td>
      <td>{t.party_name || "—"}</td><td>{productMap.get(t.product_id)?.name || `Product #${t.product_id}`}</td>
      <td>{qty(t.quantity_grams)} g</td><td><b>{money(t.total_amount)}</b></td><td>{money(t.amount_paid)}</td>
      {showDue&&<td className="due">{money(Math.max(0,Number(t.total_amount)-Number(t.amount_paid)))}</td>}
    </tr>)}
  </tbody></table>{!transactions.length&&<Empty text="No transactions to display yet."/>}</div>;
}

function Field({label,children}:{label:string;children:ReactNode}) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function Modal({title,subtitle,children,onClose}:{title:string;subtitle:string;children:ReactNode;onClose:()=>void}) {
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <section className="modal"><div className="modal-heading"><div><h2>{title}</h2><p>{subtitle}</p></div><button className="icon-button" onClick={onClose}><X size={18}/></button></div>{children}</section>
  </div>;
}

function Empty({text}:{text:string}) {
  return <div className="empty"><Boxes size={24}/><b>No records found</b><p>{text}</p></div>;
}

function MetalTag({metal}:{metal:string}) {
  return <span className={`metal-tag ${metal.toLowerCase()}`}>{metal}</span>;
}

function Status({active}:{active:boolean}) {
  return <span className={`status ${active?"active":"inactive"}`}>{active?"Active":"Inactive"}</span>;
}

function pretty(value:string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
}

function errorText(error:unknown) {
  return error instanceof Error ? error.message : "Unknown error";
}
