# SNJ Gold Lab

Inventory and transaction management for gold, silver, jewellery, biscuit and
laboratory materials. Built with **FastAPI + SQLAlchemy + PostgreSQL** on the
backend and **React + TypeScript + Vite** on the frontend.

## Features

- **Products** — loose metal, biscuits, jewellery, lab materials with metal,
  purity (SKU) and activate/deactivate control.
- **Verified metal rates** — manually verified rates with full history
  (never overwritten). Rates can be entered per **gram, tola or kilogram**;
  the backend normalizes everything to a per-gram rate before calculating.
- **Point of sale** — cashier screen with product search, live stock,
  auto-filled rates, multi-item cart and cash-change calculation;
  checkout records each line as its own sale, all-or-nothing.
- **Purchases & sales** — gross weight, deduction, net weight, purity, rate,
  charges and initial payment. Totals are always calculated by the backend.
- **Stock control** — movements per location (Main Store, Vault, …), oversell
  protection, negative-stock guard (configurable via settings).
- **Returns, adjustments & transfers** — sales return restores stock and
  reduces the customer's receivable; transfers move stock between locations
  without changing the total; adjustments require a reason.
- **Party ledger** — customers and suppliers with receivable / payable / net
  balances computed from active transactions.
- **Payments** — partial payments per transaction, full payment history.
- **Cancellation with reversal** — cancelling never deletes a record: the
  backend posts compensating stock movements, optionally a refund payment,
  and an audit entry. Cancelled rows stay in the ledger but are excluded
  from reports.
- **Reports** — financial summary, outstanding amounts, party ledger,
  cashflow (money received / paid / net), and a best-effort profit
  estimate (sales minus returns minus purchases — clearly labelled as
  an estimate, not a precise cost-of-goods-sold calculation). Reports
  can be filtered by date range and printed or saved as PDF via the
  browser's print dialog.
- **Transaction dates** — every purchase/sale carries an editable
  `transaction_date` (defaults to today); date filters on lists and
  reports use this business date, not the row-creation timestamp.
- **Users & roles** — `admin`, `manager`, `operator`, `viewer` with JWT
  login. Role changes are audit-logged.
- **Audit log** — every important action records who did what (admin only).
- **Settings & backups** — business name, currency, default location,
  negative-stock switch; pg_dump backups plus portable JSON
  backup/restore with a guarded confirm step.

## Requirements

- Python 3.12+ (tested on 3.14)
- Node.js 18+
- PostgreSQL 14+ (tested on 17)

## 1. Database setup

```bash
sudo -u postgres psql
```

```sql
CREATE ROLE hisabpro WITH LOGIN PASSWORD 'your-strong-password';
CREATE DATABASE hisabpro OWNER hisabpro;
\q
```

## 2. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create `backend/.env` (see `.env.example` for every variable):

```bash
cp .env.example .env   # then edit the values
```

Run the migrations:

```bash
.venv/bin/alembic upgrade head
```

Create the first admin account (interactive):

```bash
.venv/bin/python scripts/create_admin.py
```

Optional demo data (users `manager` / `operator` / `viewer` with password
`DemoPass!1234`, plus products, rates, parties and sample transactions):

```bash
.venv/bin/python scripts/seed_demo.py
```

Start the API:

```bash
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: <http://127.0.0.1:8000/docs>
- Health check: `GET /api/auth/me` (with a Bearer token)

### Production notes

- Run several workers: `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4`
- Put a TLS reverse proxy (nginx/Caddy) in front; set `CORS_ORIGINS` to the
  exact frontend origin.
- `lifespan` runs `create_all` as a dev convenience — in production run
  `alembic upgrade head` and treat migrations as the source of truth.
- Failed logins are limited per client+username
  (`HISABPRO_LOGIN_RATE_LIMIT`, default 10/min, `0` disables).
- Never commit `.env` or database dumps; backups live in `backups/`
  (gitignored).

### Backups, encryption and retention

Backups are created from **Settings → Database backups** (admin only).
Two kinds exist: **JSON data** (portable, all business tables) and
**pg_dump** (full database, PostgreSQL only).

**Encryption at rest.** Set `HISABPRO_BACKUP_KEY` in `.env` to enable
AES-256-GCM encryption. New backups are then written as `*.json.enc` /
`*.dump.enc`; old plaintext backups stay restorable. The key is never
committed — generate and store it separately (password manager, printed
copy in a safe):

```bash
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

**Retention.** After each backup, files older than
`HISABPRO_BACKUP_RETENTION_DAYS` (default 30) are pruned, but the newest
`HISABPRO_BACKUP_KEEP_MIN` (default 5) backups are always kept. Every
pruned file is written to the audit log.

**Scheduled backups (cron).** The app does not run a scheduler. For a
daily automated backup, add a cron job on the server (adjust the token
or use a service account):

```cron
# Every day at 02:00 — JSON backup via the API
0 2 * * * TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"REDACTED"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])") && curl -s -X POST http://127.0.0.1:8000/api/backups/json -H "Authorization: Bearer $TOKEN"
```

**Restore drill.** Before trusting a backup, test it: create a backup,
then restore it on a staging copy (never over production without an
explicit confirmation). The automated test suite includes a full
restore-drill that verifies row counts and decimal amounts survive the
round trip.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Production build:

```bash
npm run build      # type-checks with tsc, bundles with vite
npm run preview
```

Point the frontend at a non-default backend with `frontend/.env`:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 4. Tests

Backend (SQLite by default):

```bash
cd backend
.venv/bin/python -m pytest tests -q
```

Backend against PostgreSQL (uses an isolated `hisabpro_test` schema):

```bash
HISABPRO_PG_TESTS=1 .venv/bin/python -m pytest tests -q
```

Frontend unit tests (vitest) and type-check / build:

```bash
cd frontend
npm test
npm run build
```

Browser end-to-end test (Playwright drives a real Chromium through
login → dashboard → sale → cancel → role limits; starts uvicorn and
`vite preview` itself):

```bash
cd frontend && npm run build && cd ../backend
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
.venv/bin/python scripts/e2e_browser.py
```

CI runs the SQLite tests, the PostgreSQL integration tests, the frontend
unit tests and the frontend build on every push
(`.github/workflows/ci.yml`).

## 5. Docker / Podman (portable deployment)

With Docker or Podman installed, the whole stack runs with one command
(values come from the project `.env` file next to `docker-compose.yml`):

```bash
docker compose up --build -d          # or: podman-compose up -d
```

- Frontend: <http://localhost:8080> (nginx serves the build and proxies
  `/api` to the backend)
- Backend: <http://127.0.0.1:8000/docs>
- PostgreSQL: **internal only** — no host port is published; the
  database is reachable solely inside the compose network (data lives
  in the `hisabpro_data` volume)
- Backups land encrypted (`.enc`) in the `hisabpro_backups` volume

First run on a fresh machine — create the admin account:

```bash
docker compose exec -it backend python scripts/create_admin.py
# (podman: podman-compose exec backend python scripts/create_admin.py)
```

### Moving to another laptop / server

Everything (database + encrypted backups) lives in two named Docker
volumes, so the whole system moves with these steps:

```bash
# 1) On the OLD machine — dump the database and copy the backups volume out
docker compose exec -db pg_dump -U hisabpro -Fc hisabpro > hisabpro.dump
docker run --rm -v hisabpro_hisabpro_backups:/b -v "$PWD":/out alpine \
  tar czf /out/backups-volume.tgz -C /b .
# (podman: replace the volume name shown by `podman volume ls`)

# 2) Copy the project folder + the two files to the NEW machine
scp -r ./ hisabpro-new:~/hisabpro/
scp hisabpro.dump backups-volume.tgz hisabpro-new:~/hisabpro/

# 3) On the NEW machine — start the stack, load data, create admin
cd ~/hisabpro
cp backend/.env.example .env   # then edit: strong POSTGRES_PASSWORD,
                               # JWT_SECRET_KEY (>=32 chars), HISABPRO_BACKUP_KEY
docker compose up --build -d
docker compose exec -T db psql -U hisabpro -d hisabpro -c 'CREATE DATABASE hisabpro;'
docker compose exec -T db pg_restore -U hisabpro -d hisabpro --clean --if-exists < hisabpro.dump
docker run --rm -v hisabpro_hisabpro_backups:/b -v "$PWD":/out alpine \
  tar xzf /out/backups-volume.tgz -C /b
```

The JWT secret stays the same only if you copy the old `.env`; otherwise
everyone simply logs in again with their existing username/password
(passwords are stored as hashes, not in `.env`).

### Offsite backups with rclone (opt-in)

Encrypted backups are copied to cloud storage on an interval so a disk
failure cannot take data *and* backups together:

```bash
rclone config                     # e.g. create remote "gdrive" (Google Drive)
cp rclone.conf.example rclone.conf  # paste your remote's section into it
# in .env add:
#   RCLONE_REMOTE=gdrive:snj-gold-lab-backups
#   RCLONE_INTERVAL=86400         # seconds between syncs (default 1 day)
docker compose --profile offsite up -d
```

`rclone.conf` is gitignored (it can contain OAuth tokens). The sync
container idles harmlessly until `RCLONE_REMOTE` is set.

## 6. Backup & restore

Backups are **encrypted at rest** (AES-256-GCM, key from
`HISABPRO_BACKUP_KEY`) and pruned automatically after
`HISABPRO_BACKUP_RETENTION_DAYS` (default 30, never below
`HISABPRO_BACKUP_KEEP_MIN` = 5 newest). Enable offsite rclone sync as
described in section 5.

Two backup formats, both admin-only (**Settings → Database backups**):

- **pg_dump backup** (`Create backup`) — full PostgreSQL dump
  (`pg_dump --format=custom`). Restores the entire database.
- **JSON backup** (`Create JSON backup`) — portable export of every
  business table (users, settings, products, parties, rates,
  transactions, payments, stock movements) as a single readable JSON
  file. Restoring it **replaces all business data** with the file's
  contents in one transaction (the audit log is kept). JSON files can
  also be **downloaded** from the server for safekeeping elsewhere.

Both restore flows require typing the exact backup filename to confirm
and are written to the audit log. Files are stored in
`~/hisabpro/backups` (override with `HISABPRO_BACKUP_DIR`).

CLI equivalent for pg_dump:

```bash
pg_dump -Fc -h 127.0.0.1 -U hisabpro -d hisabpro -f backups/my-backup.dump
pg_restore --clean --if-exists -h 127.0.0.1 -U hisabpro -d hisabpro backups/my-backup.dump
```

## 7. Accounting rules

- Sale totals = net weight × rate per gram × purity / 100 + charges.
- A **sales return** reduces the customer's receivable.
- A **payment** on a transaction reduces its outstanding balance.
- **Cancelling** a transaction posts reversal movements; if money was already
  paid, cancellation is blocked unless `include_payments: true` is sent,
  which posts a negative refund payment.
- Cancelled transactions are excluded from summaries and outstanding reports,
  but their payments (including refunds) still appear in cashflow.

## 8. Project layout

```
backend/
  alembic/            # migrations
  app/
    api/              # routers (products, rates, purchases, sales, movements,
                      # transactions, payments, parties, reports, users, audit,
                      # settings, backups, dashboard)
    core/             # config, auth (JWT), permissions (roles), security
    db/               # engine / session
    models/           # SQLAlchemy models
    schemas/          # Pydantic request/response models
    services/         # business logic (transactions, movements, reversals,
                      # payments, parties, pricing, backup, …)
  scripts/            # create_admin.py
  tests/              # pytest suite (SQLite + optional PostgreSQL tests)
frontend/
  src/
    api.ts            # fetch client with JWT + role helpers
    types.ts          # shared TypeScript types
    ui.tsx            # shared components (Modal, Field, tables, …)
    pages/            # one component per screen
    App.tsx           # shell: login, sidebar, routing
```

## 9. Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | backend `.env` | SQLAlchemy connection string (required) |
| `POSTGRES_PASSWORD` | backend `.env` | interpolated into `DATABASE_URL` |
| `JWT_SECRET_KEY` | backend `.env` | signing key for access tokens (required) |
| `HISABPRO_API_KEY` | backend `.env` | legacy shared key (routers use JWT) |
| `HISABPRO_BACKUP_DIR` | backend env | backup folder (default `~/hisabpro/backups`) |
| `CORS_ORIGINS` | backend `.env` | comma-separated browser origins (default Vite dev) |
| `HISABPRO_LOGIN_RATE_LIMIT` | backend `.env` | failed logins per client+username per minute (default 10, `0` off) |
| `VITE_API_BASE_URL` | frontend `.env` | backend origin (default `http://127.0.0.1:8000`) |
