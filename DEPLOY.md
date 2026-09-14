# Deploy Viet Dataverse to production

**Current box (since 2026-09-04): BKHOST Cloud VPS B, `103.130.215.180` (Vietnam,
VNPT datacenter).** Standalone — VDV is the only app on this box, with its own
Caddy container for TLS. Previously ran on a Hetzner box (Germany) shared with
`mythreel.studio`; see "History" below for why and how that changed.

VDV is one stateless container that serves the FastAPI **API** + static **FE**
(`/fe`); DBs stay external on Neon. Both `vietdataverse.online` and
`api.vietdataverse.online` hit the same container (routed by path, not host).

Artifacts in repo: `Dockerfile`, `.dockerignore`, `docker-compose.yml`,
`deploy/vietdataverse.caddy` (routing rules — the box's actual Caddyfile is a
local, uncommitted copy of these same three site blocks),
`.github/workflows/deploy.yml`.

**The box's `docker-compose.override.yml` and `caddy-conf/Caddyfile` are NOT in
git** — they're standalone-deploy scaffolding created directly on the box
(merge automatically with the committed `docker-compose.yml` via Docker
Compose's default override behavior). If the box is ever rebuilt from scratch,
recreate them from the templates below before the first `docker compose up`.

---

## 1. DNS → point at the box
`vietdataverse.online`, `api.vietdataverse.online`, `www.vietdataverse.online`
→ **A → 103.130.215.180**. Caddy auto-issues Let's Encrypt certs once DNS
resolves and 80/443 are reachable — no manual cert step needed.

## 2. One-time box setup
```bash
curl -fsSL https://get.docker.com | sh && systemctl enable --now docker
mkdir -p ~/vietdataverse && cd ~/vietdataverse
git clone https://github.com/findatasolution/vietdataverse.git .
cp/scp your local .env  ->  ~/vietdataverse/.env     # NEVER commit; scp over SSH, don't paste into chat/terminal
```

Create `docker-compose.override.yml` (standalone port/network overrides — the
committed `docker-compose.yml` expects a shared external `edge` Caddy network
this box doesn't have):
```yaml
services:
  vietdataverse:
    ports:
      - "127.0.0.1:8000:8000"   # local debugging only, not public
    networks:
      - default
    mem_limit: 700m
    cpus: "1.5"

  caddy:
    image: caddy:2-alpine
    container_name: vdv-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./caddy-conf/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - default
    depends_on:
      - vietdataverse

networks:
  edge:
    external: false
    driver: bridge

volumes:
  caddy_data:
  caddy_config:
```

Create `caddy-conf/Caddyfile` (same three site blocks as
`deploy/vietdataverse.caddy`, just addressing the service by its
Compose name over the box's own `default` network instead of the old
shared `edge` network):
```
vietdataverse.online {
	encode gzip zstd
	reverse_proxy vietdataverse:8000
}

api.vietdataverse.online {
	encode gzip zstd
	reverse_proxy vietdataverse:8000
}

www.vietdataverse.online {
	redir https://vietdataverse.online{uri} permanent
}
```

```bash
docker compose up -d --build
curl -fsS http://localhost:8000/health                     # app healthy
curl -sI https://vietdataverse.online/                      # HTTP/2 307, valid cert (after DNS propagates)
```

## 3. Auto-deploy
GitHub repo secrets (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | `103.130.215.180` |
| `DEPLOY_USER` | `root` |
| `DEPLOY_SSH_KEY` | private key of a dedicated `vdv-github-deploy-bkhost` ed25519 pair, pubkey in the box's `authorized_keys` |
| `DEPLOY_PORT` | `22` |
| `DEPLOY_APP_DIR` | `/root/vietdataverse` |

`.github/workflows/deploy.yml` runs on every push to `main` **and** after each
"Generate Static Chart Data" run → the box `git reset --hard origin/main` +
`docker compose up -d --build`. `git reset --hard` only touches tracked
files, so it never disturbs the box-local `docker-compose.override.yml` /
`caddy-conf/Caddyfile`. Caddy needs no reload on redeploy.

## 4. Box-side gold/silver crawl — PRIMARY path (promoted 2026-09-14)
`deploy/crawl-fallback.*` (systemd timer + unit) is **the** scheduled crawler
for gold/silver. `gold-silver-crawl.yml` on GitHub has no schedule any more,
only `workflow_dispatch` for when this box is down.

**This section used to say the timer was not provisioned on this box. That was
wrong** — corrected 2026-09-14 after the DB showed gold and silver rows written
at `01:45:25`/`01:45:32` UTC on a day GitHub ran nothing at all, exactly
matching the timer's old `OnCalendar=01:45 UTC`. Don't trust this file over the
box: `systemctl list-timers 'crawl-fallback*'` settles it in one command.

Why the box rather than Actions:
- **Network.** The 2026-09-13 Actions run failed with a connect timeout to
  `www.24h.com.vn`; `nso.gov.vn` refuses foreign datacenter IPs outright, which
  is why prod moved here on 2026-09-04. This box reaches both fine.
- **Scheduling.** GitHub dropped every gold slot on 2026-09-14; measured
  2026-08-09 it fired 4–8 of 9 declared daily runs, 32 min late on average.

The timer fires **every 2 hours across VN office hours** (01:00–09:00 UTC =
08:00–16:00 VN) and every run upserts — it does *not* skip when the day already
has a row. That guard is what froze the published price at the morning quote for
75 days; see `crawl-fallback.sh`'s header. Each successful run also regenerates
`fe/data/*.json` into the directory FastAPI serves, because the charts read
those files rather than the DB.

Install / update on the box (needed whenever `crawl-fallback.timer` or
`.service` changes — a plain deploy only refreshes the files):

```bash
cd /root/vietdataverse && git pull          # or let deploy.yml land the files
cp deploy/crawl-fallback.service deploy/crawl-fallback.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now crawl-fallback.timer
systemctl list-timers 'crawl-fallback*'     # verify the 5 slots are scheduled
systemctl start crawl-fallback.service      # optional: run once now
journalctl -u crawl-fallback.service -n 50 --no-pager
```

`crawl_gold_silver.py` exits non-zero whenever its Yahoo Finance section fails,
and Yahoo blocks index tickers from datacenter IPs — so a non-zero exit here is
expected and does **not** mean the domestic crawl failed. The script re-probes
the DB and judges on that, not on the exit code.

---

## History

### 2026-09-04: migrated Hetzner (Germany) → BKHOST (Vietnam)
**Root cause:** `nso.gov.vn` (source for the GSO CPI/GDP/IIP/Trade crawlers)
resets TCP connections from foreign/EU datacenter IPs. Verified directly: both
GitHub Actions runners *and* the Hetzner box itself (tested via SSH) got
`ConnectionResetError` hitting NSO's API — this wasn't a GitHub-specific block,
so no proxy-only fix on Hetzner could have solved it. A VN-datacenter VPS was
required. `mythreel.studio`, which shared the Hetzner box, was discontinued in
the same move — its real data lived on Neon (`DATABASE_URL`) and Cloudflare R2
(rendered video output), both external to the box, so nothing was lost when
the box was deleted. The on-box Postgres (`queuedb`) held only an ephemeral
pg-boss job queue, confirmed via the compose file's own comments before
deletion — not app/business data.

Migration verified in order before the Hetzner box was deleted: app healthy
+ DB-connected via the new box's IP directly → NSO reachable (200, not reset)
from that IP → DNS cut over (all three A records) → Let's Encrypt issued a
real production cert (confirmed via `openssl s_client`, not staging) → every
route (root, `www` redirect, `api.*`, a real DB-backed endpoint) returned the
expected status over HTTPS on the real domain → only then was Hetzner deleted.

Renamed accordingly: `deploy-hetzner.yml` → `deploy.yml`, `HETZNER_*` secrets
→ `DEPLOY_*`, this file `DEPLOY_HETZNER.md` → `DEPLOY.md`.

### 2026-07-10: migrated Render → Hetzner (Germany)
Render's free/low tier caused the single most recurring problem across
several sessions: "why isn't the chart updating" was almost always "Render
only redeploys on a manual trigger." Moving to a VPS with GitHub Actions
auto-deploy solved that permanently — see the auto-deploy step above, which
is the same mechanism (just a different box) as what was set up then.

### Incident 2026-07-27 → 2026-07-28: 31h HTTPS outage (Hetzner era, historical)
**Symptom:** `vietdataverse.online` (and `www`, `api`) → TLS alert, no
certificate presented, while `mythreel.studio` on the same shared Caddy
stayed up. **Root cause:** the *neighbour's* compose file
(`~/automated_video/docker-compose.yml`) was edited and its Caddy service
recreated without the bind mount that made `import /etc/caddy/conf.d/*.caddy`
find VDV's site blocks, and without the shared `edge` network — both had only
ever been declared imperatively, not in that compose file, so they silently
vanished on the next recreate. Certs were fine and still on disk; the VDV
container itself was healthy the whole time — Caddy simply had no site block
loaded for that SNI. Not applicable to the current standalone setup (this box
runs its own dedicated Caddy, no neighbour to depend on), but the general
lesson generalizes: **anything a shared/neighbouring service needs from you
must be declared in that service's own persistent config, not applied by
hand** — a one-off `docker network connect` or copied-in file survives only
until the next recreate.

**Follow-up that's still relevant:** `.github/workflows/uptime-check.yml`
probes prod daily at 11:00 VN from a GitHub runner (deliberately off-box — an
on-box cron dies with the box it's watching). It still runs today against the
current box and fails on: TLS handshake refused, expired/near-expiry cert
(<14 days), DNS gone, box unreachable, a suspiciously small 200 response,
anonymous `/api/v1/gold` no longer returning 401, or any SEO root file 404ing.

### Security note (carried over, still applicable)
The deploy SSH key authenticates as **root**. Consider hardening later: a
dedicated non-root deploy user with a `command="…"`-restricted key, so a
compromised Action can't take the whole box. This box no longer has a
neighbour app to endanger, which lowers the blast radius versus the Hetzner
era, but the principle still holds.
