#!/usr/bin/env bash
#
# PRIMARY box-side crawler for gold & silver (see deploy/crawl-fallback.timer).
#
# The file name still says "fallback" for a boring reason: renaming the systemd
# units would need them disabled and re-enabled by hand on the box. It is not a
# fallback any more — it is the only scheduled path that crawls these sources.
#
# WHY THE BOX AND NOT GITHUB ACTIONS (promoted 2026-09-14)
#   1. Network. GitHub's runners sit outside Vietnam and cannot reach these
#      sources reliably: gold-silver-crawl.yml failed 2026-09-13 with a connect
#      timeout to www.24h.com.vn, and nso.gov.vn refuses foreign datacenter IPs
#      outright — the reason prod itself moved to this VN box on 2026-09-04.
#      This box talks to 24h.com.vn without trouble.
#   2. Scheduling. GitHub's cron is best-effort: measured 2026-08-09, the 01:30
#      UTC slot never fired at all, only 4–8 of 9 declared runs materialised, and
#      those that did started 32 min late on average (58 max). On 2026-09-14 it
#      dropped the day's runs entirely. systemd on this box fires on time.
#
#   gold-silver-crawl.yml keeps only a workflow_dispatch trigger, for a manual
#   run when the box is down. Its schedule is gone, so there is exactly one
#   writer on a normal day.
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

# ARGUS_FINTEL_DB is here for generate_static_data.py's market-pulse section, not
# for the crawler. It is optional there (the script skips that file when unset),
# so a box whose .env lacks it still produces every other chart.
for key in CRAWLING_BOT_DB GLOBAL_INDICATOR_DB ARGUS_FINTEL_DB; do
    # Tolerates leading spaces, spaces around '=', trailing spaces/CR and
    # surrounding quotes. Keeps any '=' inside the value (sslmode=require).
    value=$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" \
            | head -1 | sed -E 's/[[:space:]]*$//; s/\r$//; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/')
    if [ -z "$value" ]; then
        if [ "$key" = "ARGUS_FINTEL_DB" ]; then
            log "note: $key not in $ENV_FILE — market_pulse.json will be skipped"
            continue
        fi
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

# NO "skip if today's row exists" GUARD — deliberate, 2026-09-14.
#
# There used to be one here, and it was the third copy of the same mistake: the
# crawler had it, gold-silver-crawl.yml had it, and so did this script. Together
# they meant the first successful crawl of the day pinned the price and every
# later run no-oped, so the published chart sat at the ~08:45 VN quote while SJC
# moved several times during the day. Reported 2026-09-12 and again 2026-09-14
# (chart 142.7 vs source 143.2). The other two are fixed; this is the third.
#
# Every run now crawls and upserts. `probe` output is kept purely for the log, so
# a reader can see what the day looked like before and after this run.
log "pre-crawl state: $before — crawling (every run refreshes, by design)"

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
    log "OK: today's data present ($after); crawler exit=$crawl_rc (non-zero is expected when Yahoo blocks this IP)"

    # Regenerate the static JSON the FE charts actually read.
    #
    # The charts do not query the DB — they fetch fe/data/*.json, which used to be
    # produced only by generate-static-data.yml on GitHub (triggered by the crawl
    # workflow finishing, plus a 6-hourly backstop). With crawling moved onto this
    # box, nothing would trigger it, and a fresh DB row would sit invisible to
    # visitors for up to 6 hours. So the box regenerates them itself, straight into
    # the directory FastAPI serves.
    #
    # The repo is mounted read-only for the crawl above; this needs fe/data
    # writable, hence the second, narrower rw mount. A deploy (`git reset --hard`)
    # reverts these files to whatever is committed; the next run, at most 2 hours
    # later, regenerates them.
    log "regenerating static chart JSON"
    docker run --rm \
        --env-file "$CRAWL_ENV" \
        -v "$APP_DIR:/repo:ro" \
        -v "$APP_DIR/fe/data:/repo/fe/data" \
        -w /repo/be \
        --memory 1g \
        "$IMAGE" python generate_static_data.py 2>&1 | sed 's/^/    /'
    static_rc=${PIPESTATUS[0]}
    if [ $static_rc -ne 0 ]; then
        # The DB is correct either way; only the published files lag. Worth a loud
        # line in the journal, not worth failing the unit and paging over.
        log "WARNING: static JSON regeneration exited $static_rc — charts may lag until the next run"
    else
        log "static JSON regenerated"
    fi
    exit 0
fi

log "FAILED: data still incomplete after fallback ($after); crawler exit=$crawl_rc"
exit 1
