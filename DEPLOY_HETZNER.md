# Deploy Viet Dataverse to Hetzner (replace Render)

One container serves everything: FastAPI **API** + static **FE** (`/fe`). DBs stay
external (Neon), so the box is stateless. Both `vietdataverse.online` and
`api.vietdataverse.online` point at the same container; the app routes `/fe/*` and
`/api/v1/*` itself.

Artifacts already in the repo: `Dockerfile`, `.dockerignore`, `docker-compose.yml`,
`.github/workflows/deploy-hetzner.yml`.

---

## 1. One-time server setup (SSH into the Hetzner box)

```bash
sudo mkdir -p /opt/vietdataverse && sudo chown "$USER" /opt/vietdataverse
git clone https://github.com/findatasolution/vietdataverse.git /opt/vietdataverse
cd /opt/vietdataverse
# Put the 23 env vars here (same file you use locally). NEVER commit it.
scp/nano .env        # copy your local .env → /opt/vietdataverse/.env
docker compose up -d --build
curl -fsS http://127.0.0.1:8000/health   # -> should return OK
```

The container binds to `127.0.0.1:8000` only (not public). Your existing reverse
proxy forwards the two hostnames to it.

## 2. Reverse proxy (use your EXISTING proxy — do not add a new one)

**Caddy** (`Caddyfile`):
```
vietdataverse.online, api.vietdataverse.online {
    reverse_proxy 127.0.0.1:8000
}
```

**nginx** (one server block, repeat for the api. host or use both in `server_name`):
```
server {
    server_name vietdataverse.online api.vietdataverse.online;
    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host;
                 proxy_set_header X-Forwarded-For $remote_addr;
                 proxy_set_header X-Forwarded-Proto $scheme; }
}
# then: certbot --nginx -d vietdataverse.online -d api.vietdataverse.online
```

## 3. DNS cutover (Cloudflare)

Point both A records to the Hetzner IP (currently → Render):
- `vietdataverse.online`  A → <HETZNER_IP>
- `api.vietdataverse.online` A → <HETZNER_IP>

Keep Cloudflare proxy (orange cloud) if you want its CDN/cache; make sure SSL mode
is **Full (strict)** so it talks HTTPS to your proxy.

## 4. Auto-deploy (kills the "prod is stale until I redeploy" problem for good)

Add these GitHub repo secrets (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `HETZNER_HOST` | server IP |
| `HETZNER_USER` | SSH user (e.g. `root` or your deploy user) |
| `HETZNER_SSH_KEY` | a **private** key whose public half is in the server's `~/.ssh/authorized_keys` |
| `HETZNER_PORT` | `22` |
| `HETZNER_APP_DIR` | `/opt/vietdataverse` |

Once set, `deploy-hetzner.yml` runs on every push to `main` **and** after each
"Generate Static Chart Data" run → the server `git reset --hard origin/main` +
`docker compose up -d --build`. Fresh data/code reaches prod automatically, no
manual redeploy. (Until the secrets exist the workflow no-ops via a guard.)

## 5. Cutover order (zero-downtime-ish)

1. Server setup (§1) + proxy (§2) while DNS still points at Render → test via
   `curl --resolve vietdataverse.online:443:<HETZNER_IP> https://vietdataverse.online/health`.
2. Flip DNS (§3).
3. Add GitHub secrets (§4) → confirm the next deploy runs green.
4. After a few days stable, delete the Render service.

## Notes
- No swap on the box → compose sets `mem_limit: 1g`. App idles well under; if you add
  workers or hit memory pressure, drop `--workers` to 1 in the Dockerfile CMD.
- Rebuild on data commits is fast (deps layer cached; only fe/ + be/ layers rebuild).
- Crawlers keep running on **GitHub Actions** (unchanged) — they only write to Neon.
