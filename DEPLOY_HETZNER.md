# Deploy Viet Dataverse to the shared Hetzner box (replace Render)

Follows **`box-multi-app-deploy.md`** (the box already runs mythreel.studio behind a
single shared Caddy). VDV is one stateless container that serves the FastAPI **API**
+ static **FE** (`/fe`); DBs stay external on Neon. Both `vietdataverse.online` and
`api.vietdataverse.online` hit the same container (routed by path, not host).

Box IP: `62.238.25.95`. App lives in its **own dir** `~/vietdataverse` with its **own
compose**, joins the shared **`edge`** network, and does **NOT** open 80/443.

Artifacts in repo: `Dockerfile`, `.dockerignore`, `docker-compose.yml`,
`deploy/vietdataverse.caddy`, `.github/workflows/deploy-hetzner.yml`.

---

## 0. One-time box prep — SKIP if a 2nd app was already added before
Per `box-multi-app-deploy.md` §1: restore **4G swap** (box has 0B — mandatory),
`docker network create edge`, and make the shared Caddy join `edge` + `import
/etc/caddy/conf.d/*.caddy`. Verify: `swapon --show` shows 4G, `docker network ls | grep edge`.

### 0.1 The shared Caddy needs TWO declarations in `~/automated_video/docker-compose.yml`
Both must live **in the compose file**. Doing either one imperatively (`docker network
connect`, or hand-copying a file into the running container) works until the next
`docker compose up -d` recreates Caddy — then it silently vanishes and VDV goes dark.
This exact failure took prod down for 31h on 2026-07-27 (see Status).

```yaml
  caddy:
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy-conf.d:/etc/caddy/conf.d:ro   # ← without this, `import` matches 0 files
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - default
      - edge                                   # ← without this, Caddy → 502 to vietdataverse:8000

networks:
  edge:
    external: true
```

Verify both after **any** change to that stack:
```bash
docker exec automated_video-caddy-1 ls /etc/caddy/conf.d/          # vietdataverse.caddy
docker inspect automated_video-caddy-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'   # must include `edge`
docker exec automated_video-caddy-1 curl -s localhost:2019/config/apps/http/servers | grep -c vietdataverse    # > 0
```

## 1. DNS (Cloudflare) → point at the box
`vietdataverse.online`, `api.vietdataverse.online`, `www.vietdataverse.online`
→ **A → 62.238.25.95**. Caddy auto-issues certs once DNS resolves + 80/443 reachable.
If keeping Cloudflare proxy (orange), set SSL mode **Full (strict)**.

## 2. Bring the app up (on the box)
```bash
mkdir -p ~/vietdataverse && cd ~/vietdataverse
git clone https://github.com/findatasolution/vietdataverse.git .
cp/scp your local .env  ->  ~/vietdataverse/.env     # 23 vars; NEVER commit
docker network create edge 2>/dev/null || true       # idempotent
docker compose up -d --build
curl -fsS http://127.0.0.1:8000/health               # from inside a container that shares edge, or:
docker compose exec vietdataverse curl -fsS http://localhost:8000/health   # -> OK
```

## 3. Route it through the shared Caddy
Prerequisite: §0.1 (conf.d mount + `edge` network declared in that stack's compose).
```bash
cp ~/vietdataverse/deploy/vietdataverse.caddy ~/automated_video/caddy-conf.d/
cd ~/automated_video && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
curl -sI https://vietdataverse.online/health          # HTTP/2 200, valid cert
curl -sI https://mythreel.studio                      # confirm mythreel still 200
docker stats --no-stream                              # vietdataverse ≤ 640m; total RAM safe
```

## 4. Auto-deploy (ends "prod stale until manual redeploy" forever)
Add GitHub repo secrets (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `HETZNER_HOST` | `62.238.25.95` |
| `HETZNER_USER` | `root` (or your deploy user) |
| `HETZNER_SSH_KEY` | a **private** key whose pubkey is in the box's `authorized_keys` |
| `HETZNER_PORT` | `22` |
| `HETZNER_APP_DIR` | `/root/vietdataverse` (or `~/vietdataverse` resolved) |

Then `deploy-hetzner.yml` runs on every push to `main` **and** after each "Generate
Static Chart Data" run → the box `git reset --hard origin/main` + `docker compose up
-d --build`. Fresh data/code reaches prod automatically. (Guarded: no-ops until the
secrets exist.) Caddy needs no reload on redeploy — the service name/port don't change.

## 4b. Box-side crawl fallback (gold/silver)

GitHub's scheduled runs are best-effort. Measured 2026-08-09: the gold/silver
primary cron slot never fired at all, 1–5 of 9 daily runs were dropped, and the
runs that fired started 32 min late on average — so the day's data landed
10:00–12:40 VN instead of 08:30. A systemd timer on the box crawls **only when
that day's rows are still missing**, which bounds the lateness without touching
GitHub Actions (still the primary path).

One-time install on the box, after the code has deployed:

```bash
cd /root/vietdataverse
# context is crawl_tools/ — the root .dockerignore excludes it, so a root context
# cannot see requirements.txt
docker build -f deploy/crawler.Dockerfile -t vdv-crawler:latest crawl_tools
cp deploy/crawl-fallback.service deploy/crawl-fallback.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now crawl-fallback.timer
```

Verify:

```bash
systemctl list-timers crawl-fallback.timer      # next fire 01:45 / 03:00 UTC
systemctl start crawl-fallback.service          # run once by hand
journalctl -u crawl-fallback.service -n 30 --no-pager
```

A healthy day logs `today's data already present (gold=9 silver=2) — GitHub
Actions got there first, nothing to do` and exits 0.

Two invariants — do not "fix" these into bugs:

- **Judge success by the DB probe, not the crawler's exit code.**
  `crawl_gold_silver.py` exits 1 when its Yahoo Finance section fails, and Yahoo
  blocks index tickers from datacenter IPs like this box. Non-zero there is
  normal; the script re-probes the DB and reports on that.
- **The crawler runs in `python:3.11-slim`, not the box Python.** The box has
  Python 3.14 and no `python3-venv`, while `crawl_tools/requirements.txt` pins
  3.11-era versions. `deploy/crawler.Dockerfile` installs only the subset the
  crawler imports, pinned via that same requirements file used as a pip
  *constraint* file. The repo is bind-mounted at `/repo`, so ordinary deploys
  refresh crawler code with **no image rebuild**. Rebuild only when
  `deploy/crawler.Dockerfile` or the pinned versions change.

- **The container gets only `CRAWLING_BOT_DB` and `GLOBAL_INDICATOR_DB`,** copied
  into a mode-600 temp file that is deleted on exit — not the box `.env`, which
  also holds Auth0, PayOS, R2 and every other DB URL. Beyond least privilege this
  dodges a real trap: `docker run --env-file` is stricter than compose's
  `env_file` parser and rejects the entire file on cosmetics. The box `.env` has
  `USER_DB = …` with spaces around the `=`; compose accepts it, `docker run`
  fails with *"variable 'USER_DB ' contains whitespaces"*. Leave the file as is —
  the app depends on it working under compose — and keep the tolerant parsing.

This does not weaken the rule that `uptime-check.yml` stays **off**-box: a
watchdog must outlive the machine it watches, while a crawler net need not.

## 5. Cutover order
1. §2 + §3 while DNS still points at Render → test via
   `curl --resolve vietdataverse.online:443:62.238.25.95 https://vietdataverse.online/health`.
2. Flip DNS (§1).
3. Add secrets (§4) → confirm next deploy is green.
4. After a few days stable → delete the Render service.

## Status (2026-07-10) — LIVE
- ✅ Box built: 4G swap restored, `edge` network created, shared Caddy joined `edge` +
  `import /etc/caddy/conf.d/*.caddy`; `mythreel.studio` verified still 200 throughout.
- ✅ `vietdataverse.online` + `www` → `62.238.25.95` (box), served by the VDV container
  (`server: uvicorn`), valid **production** Let's Encrypt cert. RAM ~68MB / 640MB.
- ✅ Auto-deploy live: all 5 `HETZNER_*` secrets set, dedicated `vdv-github-deploy`
  key in the box's `authorized_keys`, `deploy-hetzner.yml` ran green (real SSH deploy).
- ✅ `api.vietdataverse.online` — **DNS A → `62.238.25.95` added (2026-07-11)**. Caddy
  auto-issued a valid Let's Encrypt cert (`CN=api.vietdataverse.online`) on first resolve;
  verified `https://api.vietdataverse.online/pages/admin.html` → 200, `/api/v1/gold` → 401
  (auth gate), `/excel-addin/taskpane.html` → 200. This revived every absolute `api.*` URL
  in the docs/code samples, the Excel add-in (`manifest.xml` + `taskpane.js`), the CI smoke
  test + crawl webhook, and the SEO JSON-LD / sitemap — no code change needed.
  The FE itself still calls the API same-origin (`location.origin + '/api/v1'` in `app.js`
  and the account/developer/admin/takedown/verify-email pages), so it works on
  `vietdataverse.online` / `www` / `api.*` alike. The Auth0 `audience` stays the literal
  `api.vietdataverse.online` identifier.
  - ✅ Fixed `/api/docs` path (2026-07-11): Swagger is `/docs`, spec is `/openapi.json`
    (FastAPI defaults; `/api/docs` never existed → 404). Updated `sitemap.xml`,
    `_layout_head.html` (contentUrl→`/openapi.json`, link→`/docs`), `fe/llms.txt`, and the
    `be/middleware.py` public allowlist. No `/api/docs` remains in the repo.
- ⏳ Render still running — delete after a few days stable.

### Incident 2026-07-27 → 2026-07-28: HTTPS down 31h (`ERR_SSL_PROTOCOL_ERROR`)
**Symptom:** `vietdataverse.online` (and `www`, `api`) → TLS alert 80, no certificate
presented. `mythreel.studio` on the same Caddy stayed 200 the whole time.

**Root cause:** `~/automated_video/docker-compose.yml` was edited 2026-07-27 06:41 and
Caddy was recreated at 10:34. The new compose declared **neither** the `caddy-conf.d`
bind mount **nor** the `edge` network — both had only ever been applied imperatively.
So `import /etc/caddy/conf.d/*.caddy` matched 0 files → the three `vietdataverse.online`
site blocks were absent from the running config → Caddy had no cert to serve for that
SNI. Certs themselves were fine and still in `/data` the whole time; the VDV container
was up and healthy. Nothing in this repo changed.

**Red herring:** `http://vietdataverse.online/` returned `308 → https://…`, which looks
like a live site. It is not — Caddy's HTTP→HTTPS redirect is a **catch-all**; a made-up
host (`nonexistent-xyz.invalid`) gets the same 308. Only
`localhost:2019/config/apps/http/servers` proves which hosts are actually loaded.

**Fix:** declared both in that compose (§0.1), `docker compose up -d --no-deps caddy`.
Verified durable with `--force-recreate`: conf.d + `edge` + all 5 hosts survive. No new
ACME issuance was needed (existing certs reused → no rate-limit exposure).

**Follow-up:** the outage ran 31h because nothing was watching. `.github/workflows/uptime-check.yml`
now probes prod daily at 11:00 VN from a GitHub runner (off-box on purpose — an on-box
cron dies with the box). It fails the workflow, and GitHub emails the owner, on: TLS
handshake refused (exit 35 — this incident), expired/untrusted cert (60), DNS gone (6),
box unreachable (7/28), a 200 whose body is too small to be the real page, anonymous
`/api/v1/gold` no longer returning 401, any SEO root file 404ing, or a cert with under
14 days left. Both the pass and fail paths were tested before merge.

**Security note:** `HETZNER_SSH_KEY` authenticates as **root** on a box that also runs
mythreel.studio. Consider hardening later: a dedicated non-root deploy user with a
`command="…"`-restricted key, so a compromised Action can't take the whole box.

## Constraints (from box-multi-app-deploy.md — do not violate)
- **Never** `docker system prune -a` (wipes mythreel images). Deploy uses `docker image prune -f` (dangling only). ✅
- Keep `mem_limit` (640m) — no swap headroom; VDV must never OOM the box.
- Don't touch `~/automated_video/docker-compose.yml` **services** (app/worker/ollama/queuedb).
  Its `caddy` service is the one exception: it must keep the conf.d mount + `edge` network
  from §0.1, or VDV drops off the internet on the next recreate. Back the file up before editing.
- Crawlers keep running on **GitHub Actions** (unchanged) — they only write to Neon.
