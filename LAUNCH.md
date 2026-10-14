# SNJ Gold Lab — Production Launch Checklist

Work through this list top to bottom the first time the system is put
in front of real users. Items marked ✅ are already enforced by the
code and only need confirmation.

## Before launch

### Server
- [ ] A Linux server (VPS or a dedicated laptop/PC) with Docker or
      Podman installed and SSH key access
- [ ] Firewall: only SSH (22) and HTTP/HTTPS (80/443) open to the
      world; PostgreSQL (5432) and the backend (8000) are **never**
      exposed — the compose file already binds them to localhost
      only ✅
- [ ] Regular off-machine backups configured (see "Backups" below)

### Secrets (generate fresh ones; never reuse dev values)
```bash
# Run on the server, copy results into .env:
python3 -c "import secrets; print('JWT:', secrets.token_urlsafe(48))"
python3 -c "import base64,secrets; print('BACKUP:', base64.b64encode(secrets.token_bytes(32)).decode())"
openssl rand -hex 24   # API key and Postgres password
```
- [ ] `.env` exists next to `docker-compose.yml` with strong
      `POSTGRES_PASSWORD`, `JWT_SECRET_KEY` (≥32 chars),
      `HISABPRO_API_KEY`, `HISABPRO_BACKUP_KEY`
- [ ] `.env` permissions are private: `chmod 600 .env` ✅ gitignored ✅

### First run
```bash
git clone <repo-url> hisabpro && cd hisabpro
# create .env as above, then:
docker compose up --build -d          # or podman-compose
docker compose exec -it backend python scripts/create_admin.py
```
- [ ] `curl http://127.0.0.1:8080/health` returns `"status": "ok"`
- [ ] Log in at `http://<server>:8080` with the new admin account
- [ ] Change the admin password from Settings → Users & access if it
      was generated elsewhere
- [ ] Create real user accounts for staff; never share the admin login ✅
      (each person logs in with their own audited identity)

## Backups
- [ ] Backups are encrypted at rest (`.enc`, AES-256-GCM) whenever
      `HISABPRO_BACKUP_KEY` is set ✅ required by compose ✅
- [ ] Retention: pruned after 30 days, newest 5 always kept ✅
- [ ] Off-site copy configured so a disk failure cannot take data and
      backups together:
```bash
rclone config                      # e.g. remote "gdrive"
cp rclone.conf.example rclone.conf # paste your remote section
# in .env: RCLONE_REMOTE=gdrive:snj-gold-lab-backups
docker compose --profile offsite up -d
```
- [ ] **Restore drill done once** (Settings → Database backups → pick
      a backup → restore) and the app still works afterwards

## HTTPS / domain (when available)
Until a domain points at the server, plain HTTP on the LAN is fine.
For a public URL, put Caddy in front (auto-HTTPS via Let's Encrypt):
```bash
# On the server, alongside the compose stack:
sudo podman run -d --name caddy -p 80:80 -p 443:443 \
  -v $PWD/Caddyfile:/etc/caddy/Caddyfile:Z \
  -v caddy_data:/data docker.io/library/caddy:2-alpine
# Caddyfile: snjexample.com { reverse_proxy 127.0.0.1:8080 }
```
- [ ] DNS A record points at the server
- [ ] `https://` loads the app; login works
- [ ] Optional: set `CORS_ORIGINS=https://yourdomain` in `.env`

## Day-2 operations
- [ ] **Updates:** `git pull && docker compose up --build -d` —
      Alembic migrations run automatically on backend start ✅
- [ ] **Logs:** `docker logs -f hisabpro-backend`, or the rotating
      file in the `hisabpro_logs` volume
- [ ] **Health:** `GET /health` (version, uptime, DB latency);
      `GET /api/metrics` as admin for request/error counts
- [ ] **Disaster recovery:** restore the newest backup from off-site
      storage onto a fresh server (README section 5 has the exact
      laptop-to-laptop commands)

## Security posture (already built in ✅)
- Passwords hashed with Argon2; JWT secret ≥32 chars enforced at boot
- Role-based access (viewer / operator / manager / admin) on every route
- Login rate limiting; HSTS + nosniff + frame-deny headers
- Database reachable only inside the compose network
- All money-moving POSTs idempotent; oversell → 409, overpay → 422
- Backups encrypted at rest; restore requires typing the filename
- Full audit log of every create/change/cancel/restore, usernames only
  (passwords never logged or returned)

## Launch sign-off
- [ ] All CI checks green on the release commit (tests, lint, audits,
      container builds)
- [ ] Admin password known only to the owner
- [ ] At least one off-site backup verified readable
- [ ] Staff trained on: login with own account, POS sale, payment,
      cancel (with reason), daily backup existence check
