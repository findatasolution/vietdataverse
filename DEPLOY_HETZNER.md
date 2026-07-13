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

**Security note:** `HETZNER_SSH_KEY` authenticates as **root** on a box that also runs
mythreel.studio. Consider hardening later: a dedicated non-root deploy user with a
`command="…"`-restricted key, so a compromised Action can't take the whole box.

## Constraints (from box-multi-app-deploy.md — do not violate)
- **Never** `docker system prune -a` (wipes mythreel images). Deploy uses `docker image prune -f` (dangling only). ✅
- Keep `mem_limit` (640m) — no swap headroom; VDV must never OOM the box.
- Don't touch `~/automated_video/docker-compose.yml` services (only drop the `.caddy` file).
- Crawlers keep running on **GitHub Actions** (unchanged) — they only write to Neon.
