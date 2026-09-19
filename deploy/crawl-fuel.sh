#!/usr/bin/env bash
#
# Box-side MOIT fuel-cycle crawl + model refresh (see deploy/crawl-fuel.timer).
#
# WHY THE BOX AND NOT GITHUB ACTIONS (moved 2026-09-19)
#   moit.gov.vn does not answer GitHub's runners. Three consecutive
#   fuel-pipeline.yml runs on 2026-09-19 logged, from a US runner IP:
#     - search endpoint: RemoteDisconnected('Remote end closed connection')
#     - /tin-tuc/thi-truong-trong-nuoc: SSLEOFError, UNEXPECTED_EOF_WHILE_READING
#     - /tin-tuc/phat-trien-nang-luong: [Errno 101] Network is unreachable
#   Same class of block as nso.gov.vn (which is why prod moved to a VN box on
#   2026-09-04) and as 24h.com.vn (why gold/silver moved here on 2026-09-14).
#   With the source unreachable, the Actions run can only ever conclude "no newer
#   cycle" — which is exactly how 2026-09-03, 09-10 and 09-17 were all missed
#   while CI stayed green. This box reaches moit.gov.vn fine.
#
#   fuel-pipeline.yml stays scheduled as a backstop for when the box is down: it
#   is harmless (it finds nothing and says so) and its staleness threshold still
#   turns red if this path stops writing.
#
# WHY DAILY AND NOT WEEKLY
#   The cycle has been weekly (Thursday, announced ~15:00 VN) since 2026-09-03,
#   but the cadence changed twice in 2026 already. A daily 16:30 VN pass costs
#   one discovery round and picks the cycle up the same afternoon whatever the
#   day, instead of needing a code change when the schedule shifts again.
#
# SUCCESS = fuel_price_cycle's newest period MOVED, or there was genuinely
# nothing new. The crawler itself exits non-zero past STALE_AFTER_DAYS, which is
# the loud signal; this script only adds the model refresh when data did change.
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

# Least privilege + tolerant parsing, same reasoning as deploy/crawl-fallback.sh:
# `docker run --env-file` rejects the box's whole .env over `KEY = value` spacing.
CRAWL_ENV=$(mktemp) || { log "FATAL: mktemp failed"; exit 1; }
chmod 600 "$CRAWL_ENV"
trap 'rm -f "$CRAWL_ENV"' EXIT

# R2_* land the raw bulletin HTML in the Bronze zone (crawl_tools/fuel_raw_store.py)
# so a parser change can be replayed without re-fetching. Optional: without them
# the crawl still stores Silver rows, it just keeps no raw copy.
for key in FUEL_FORECAST_DB R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_RAW; do
    value=$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" \
            | head -1 | sed -E 's/[[:space:]]*$//; s/\r$//; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/')
    if [ -z "$value" ]; then
        if [ "$key" = "FUEL_FORECAST_DB" ]; then
            log "FATAL: $key not found in $ENV_FILE"
            exit 1
        fi
        log "note: $key not in $ENV_FILE — raw bulletins will not be archived to R2"
        continue
    fi
    printf '%s=%s\n' "$key" "$value" >> "$CRAWL_ENV"
done

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    log "image $IMAGE not present — building from deploy/crawler.Dockerfile"
    if ! docker build -q -f "$APP_DIR/deploy/crawler.Dockerfile" -t "$IMAGE" "$APP_DIR/crawl_tools" >/dev/null; then
        log "FATAL: image build failed"
        exit 1
    fi
    log "image built"
fi

# Newest cycle in Silver, as "YYYY-MM-DD" or "-". Used before and after the
# crawl: the same query against the same DB, so no clock arithmetic is involved.
latest_period() {
    docker run --rm --env-file "$CRAWL_ENV" -v "$APP_DIR:/repo:ro" -w /repo/crawl_tools \
        "$IMAGE" python -c '
import os
from sqlalchemy import create_engine, text
with create_engine(os.environ["FUEL_FORECAST_DB"]).connect() as c:
    print(c.execute(text("SELECT coalesce(max(period)::text, \"-\") FROM fuel_price_cycle")).scalar())
' 2>/dev/null | tail -1
}

before=$(latest_period)
log "latest cycle before crawl: ${before:--}"

docker run --rm \
    --env-file "$CRAWL_ENV" \
    -v "$APP_DIR:/repo:ro" \
    -w /repo/crawl_tools \
    --memory 1g \
    "$IMAGE" python crawl_moit_fuel.py 2>&1 | sed 's/^/    /'
crawl_rc=${PIPESTATUS[0]}
[ "$crawl_rc" -ne 0 ] && log "crawl_moit_fuel.py exited $crawl_rc (past the staleness threshold, or a bad parse)"

after=$(latest_period)
log "latest cycle after crawl: ${after:--}"

if [ "$after" = "$before" ]; then
    log "no new cycle — leaving fuel_backtest/fuel_forecast untouched"
    exit "$crawl_rc"
fi

# Only refit when the data actually moved: a daily re-run on unchanged input
# would otherwise pile up identical forecast rows keyed by run_ts.
for script in backtest.py forecast.py; do
    log "running be/fuel/$script"
    docker run --rm \
        --env-file "$CRAWL_ENV" \
        -v "$APP_DIR:/repo:ro" \
        -w /repo \
        --memory 1g \
        "$IMAGE" python "be/fuel/$script" 2>&1 | sed 's/^/    /'
    rc=${PIPESTATUS[0]}
    [ "$rc" -ne 0 ] && log "be/fuel/$script exited $rc" && crawl_rc=$rc
done

log "done (new cycle $after)"
exit "$crawl_rc"
