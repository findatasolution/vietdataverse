#!/usr/bin/env bash
#
# Box-side fallback crawler for gold & silver (see deploy/crawl-fallback.timer).
#
# WHY THIS EXISTS
#   GitHub's scheduled workflows are best-effort: they run at low priority on
#   shared runners and are delayed or dropped under load. Measured 2026-08-09 on
#   gold-silver-crawl.yml's old '30 …' schedule:
#     - the 01:30 UTC primary slot never fired at all; the first scheduled run of
#       the day landed 03:04–04:38 UTC
#     - only 4–8 of the 9 declared runs per day materialised
#     - runs that did fire started 32 min late on average (max 58)
#   Net effect: the day's gold data reached the DB at 10:00–12:40 VN instead of
#   the intended 08:30 VN, every day, with GitHub perfectly healthy.
#
#   This script closes that gap from the box, which has no scheduling queue. It
#   is a NET, not a replacement: GitHub Actions stays the primary path, and this
#   only acts when the day's data is still missing by the time the timer fires.
#
# SUCCESS IS MEASURED AGAINST THE DB, NOT THE EXIT CODE
#   crawl_gold_silver.py exits 1 when the Yahoo Finance (global macro) section
#   fails, and Yahoo blocks index tickers from datacenter IPs — which this box
#   has. So a non-zero exit is expected here and does NOT mean the domestic
#   gold/silver crawl failed. We re-probe the DB afterwards and judge on that.
#
set -uo pipefail

APP_DIR=${APP_DIR:-/root/vietdataverse}
IMAGE=${IMAGE:-vdv-crawler:latest}
ENV_FILE="$APP_DIR/.env"

log() { printf '%s  %s\n' "$(date -u '+%F %T')" "$*"; }

if [ ! -f "$ENV_FILE" ]; then
    log "FATAL: env file not found at $ENV_FILE"
    exit 1
fi

# Hand the container ONLY the two vars the crawler reads, via a private temp file.
#
# Two reasons not to point --env-file at the app's env file directly:
#   1. Least privilege. That file also holds Auth0, PayOS, R2 and every DB URL;
#      a price crawler has no business seeing them.
#   2. `docker run --env-file` is stricter than compose's env_file parser and
#      rejects the whole file over cosmetics — the box's file has `USER_DB = …`
#      with spaces around the `=`, which compose accepts and docker run does not.
#      Parsing the keys we need tolerantly sidesteps that class of breakage.
CRAWL_ENV=$(mktemp) || { log "FATAL: mktemp failed"; exit 1; }
chmod 600 "$CRAWL_ENV"
trap 'rm -f "$CRAWL_ENV"' EXIT

for key in CRAWLING_BOT_DB GLOBAL_INDICATOR_DB; do
    # Tolerates leading spaces, spaces around '=', trailing spaces/CR and
    # surrounding quotes. Keeps any '=' inside the value (sslmode=require).
    value=$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" \
            | head -1 | sed -E 's/[[:space:]]*$//; s/\r$//; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/')
    if [ -z "$value" ]; then
        log "FATAL: $key not found in $ENV_FILE"
        exit 1
    fi
    printf '%s=%s\n' "$key" "$value" >> "$CRAWL_ENV"
done

# Build on first run, or after deploy/crawler.Dockerfile changes upstream.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    log "image $IMAGE not present — building from deploy/crawler.Dockerfile"
    # Context is crawl_tools/, not the repo root — the root .dockerignore excludes
    # crawl_tools, so requirements.txt is invisible from a root context.
    if ! docker build -q -f "$APP_DIR/deploy/crawler.Dockerfile" -t "$IMAGE" "$APP_DIR/crawl_tools" >/dev/null; then
        log "FATAL: image build failed"
        exit 1
    fi
    log "image built"
fi

# Same query as the workflow guard in gold-silver-crawl.yml — keep them in sync.
# Prints "gold=<n> silver=<n>"; exits 0 when both are present for today.
probe() {
    docker run --rm --env-file "$CRAWL_ENV" "$IMAGE" python -c '
import os, datetime, sys, psycopg2
today = datetime.date.today().isoformat()
conn = psycopg2.connect(os.environ["CRAWLING_BOT_DB"])
cur = conn.cursor()
cur.execute(
    "SELECT (SELECT COUNT(*) FROM vn_macro_gold_daily   WHERE date = %s),"
    "       (SELECT COUNT(*) FROM vn_macro_silver_daily WHERE date = %s)",
    (today, today),
)
gold, silver = cur.fetchone()
conn.close()
print(f"gold={gold} silver={silver}")
sys.exit(0 if (gold and silver) else 1)
'
}

before=$(probe)
probe_rc=$?

if [ $probe_rc -eq 0 ]; then
    log "today's data already present ($before) — GitHub Actions got there first, nothing to do"
    exit 0
fi

log "today's data incomplete ($before) — running fallback crawl"

# --network default + --env-file: the crawler reads CRAWLING_BOT_DB and
# GLOBAL_INDICATOR_DB from the environment. It also calls load_dotenv() on a path
# three levels above itself, which resolves to a non-existent /.env inside the
# container; load_dotenv does not override real env vars, so that is harmless.
docker run --rm \
    --env-file "$CRAWL_ENV" \
    -v "$APP_DIR:/repo:ro" \
    -w /repo/crawl_tools \
    --memory 1g \
    "$IMAGE" python crawl_gold_silver.py 2>&1 | sed 's/^/    /'
crawl_rc=${PIPESTATUS[0]}

after=$(probe)
after_rc=$?

if [ $after_rc -eq 0 ]; then
    log "OK: fallback landed today's data ($after); crawler exit=$crawl_rc (non-zero is expected when Yahoo blocks this IP)"
    exit 0
fi

log "FAILED: data still incomplete after fallback ($after); crawler exit=$crawl_rc"
exit 1
