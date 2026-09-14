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
# SUCCESS = EVERY WRITER'S crawl_time MOVED (see `probe` below)
#   Two separate reasons this is not judged on the exit code alone:
#   - crawl_gold_silver.py exits 1 whenever its Yahoo Finance section fails, and
#     Yahoo blocks index tickers from datacenter IPs — which this box has. That
#     non-zero exit is routine and says nothing about the domestic crawl.
#   - A crawler can exit 0 having written nothing new.
#   So the DB is re-probed, per writer, and compared against the same probe taken
#   before the run. "Today has a row" is explicitly NOT the test: that was the
#   old check, and it reported green all afternoon on a source that died at 08:00.
#
set -uo pipefail

APP_DIR=${APP_DIR:-/root/vietdataverse}
IMAGE=${IMAGE:-vdv-crawler:latest}
ENV_FILE="$APP_DIR/.env"

log() { printf '%s  %s\n' "$(date -u '+%F %T')" "$*"; }

# Pull one "key=value" field out of a probe line.
field() { printf '%s\n' "$1" | tr ' ' '\n' | grep -F "$2=" | cut -d= -f2-; }

# judge <before-probe-line> <after-probe-line>
#
# Sets $fresh (how many writers advanced) and $stale (a human-readable list of
# those that did not). Kept as a function with no I/O of its own so `--self-test`
# can exercise the real thing rather than a copy that drifts from it.
WRITERS="24h.com.vn giavang.org silver"
judge() {
    stale=""
    fresh=0
    local b a writer
    for writer in $WRITERS; do
        b=$(field "$1" "$writer")
        a=$(field "$2" "$writer")
        if [ "$a" = "-" ]; then
            stale="$stale $writer(no row today)"
        elif [ "$a" = "$b" ]; then
            stale="$stale $writer(stuck at $a)"
        else
            fresh=$((fresh + 1))
        fi
    done
}

# `crawl-fallback.sh --self-test` checks the freshness judgement against canned
# probe output. No DB, no docker, no .env — so it runs anywhere, including on the
# box, and does not need a source to be broken on purpose to prove that a broken
# source is detected.
if [ "${1:-}" = "--self-test" ]; then
    t=0; fail=0
    check() {  # check <label> <before> <after> <want-fresh> <want-stale-substring>
        t=$((t + 1))
        judge "$2" "$3"
        if [ "$fresh" != "$4" ]; then
            printf 'FAIL %s: fresh=%s want %s\n' "$1" "$fresh" "$4"; fail=$((fail + 1)); return
        fi
        case "$stale" in
            *"$5"*) printf 'ok   %s (fresh=%s stale=%s)\n' "$1" "$fresh" "${stale:-none}" ;;
            *) printf 'FAIL %s: stale="%s" lacks "%s"\n' "$1" "$stale" "$5"; fail=$((fail + 1)) ;;
        esac
    }
    T0="24h.com.vn=2026-09-14T06:00:00 giavang.org=2026-09-14T06:00:04 silver=2026-09-14T06:00:09"
    T1="24h.com.vn=2026-09-14T07:00:01 giavang.org=2026-09-14T07:00:05 silver=2026-09-14T07:00:10"
    NONE="24h.com.vn=- giavang.org=- silver=-"

    check "every writer advanced"        "$T0" "$T1" 3 ""
    check "first run of the day"         "$NONE" "$T1" 3 ""
    check "nothing ran at all"           "$T0" "$T0" 0 "24h.com.vn(stuck at 2026-09-14T06:00:00)"
    check "one SJC source died"          "$T0" \
        "24h.com.vn=2026-09-14T06:00:00 giavang.org=2026-09-14T07:00:05 silver=2026-09-14T07:00:10" \
        2 "24h.com.vn(stuck at"
    check "silver died, gold fine"       "$T0" \
        "24h.com.vn=2026-09-14T07:00:01 giavang.org=2026-09-14T07:00:05 silver=2026-09-14T06:00:09" \
        2 "silver(stuck at"
    check "no rows exist for today"      "$NONE" "$NONE" 0 "24h.com.vn(no row today)"

    printf '\n%s checks, %s failed\n' "$t" "$fail"
    exit $((fail > 0))
fi

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

# WHAT "SUCCESS" MEANS HERE — and why it is not "does today have a row"
#
# This used to count rows for today and call the run green if the count was
# non-zero. That is the wrong question. A row written at 08:00 satisfies it just
# as well at 16:00, so a crawler that had silently stopped working kept
# reporting green for the rest of the day. With two SJC sources writing every
# hour that matters more, not less: one source dying is precisely the failure
# the second source exists to expose, and a row-count check hides it.
#
# So the probe reports the newest crawl_time per writer, and the run is judged
# on whether that timestamp MOVED. No clock comparison is involved — `before`
# and `after` come from the same query against the same DB, so box/container
# timezone drift cannot make a stale writer look fresh.
#
# Prints one line: "24h.com.vn=<iso|-> giavang.org=<iso|-> silver=<iso|->".
probe() {
    docker run --rm --env-file "$CRAWL_ENV" "$IMAGE" python -c '
import os, datetime, psycopg2
today = datetime.date.today().isoformat()
conn = psycopg2.connect(os.environ["CRAWLING_BOT_DB"])
cur = conn.cursor()
cur.execute(
    "SELECT source, MAX(crawl_time) FROM vn_macro_gold_daily"
    " WHERE date = %s AND type = %s GROUP BY source",
    (today, "SJC"),
)
seen = dict(cur.fetchall())
cur.execute("SELECT MAX(crawl_time) FROM vn_macro_silver_daily WHERE date = %s", (today,))
seen["silver"] = cur.fetchone()[0]
conn.close()
fmt = lambda v: v.isoformat(timespec="seconds") if v else "-"
print(" ".join(f"{k}={fmt(seen.get(k))}" for k in ("24h.com.vn", "giavang.org", "silver")))
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
# Three scripts, run independently so one failing source cannot hide the others.
# The two SJC crawlers read the same number from unrelated sites and cross-check
# each other (crawl_tools/sjc_store.py); crawl_gold_silver.py now covers silver
# and global macro only.
# Two exit codes, not one. crawl_gold_silver.py exits 1 on any Yahoo Finance
# failure and Yahoo blocks this box's datacenter IP, so its non-zero exit is
# routine noise. The SJC crawlers' is not: they only exit non-zero on an
# implausible quote or a cross-source disagreement (crawl_tools/sjc_store.py),
# both of which are exactly what this pipeline was rebuilt to surface. Folding
# them into one number would let Yahoo's daily failure explain away a real one.
crawl_rc=0
sjc_rc=0
for script in crawl_sjc_24h.py crawl_sjc_giavang.py crawl_gold_silver.py; do
    log "running $script"
    docker run --rm \
        --env-file "$CRAWL_ENV" \
        -v "$APP_DIR:/repo:ro" \
        -w /repo/crawl_tools \
        --memory 1g \
        "$IMAGE" python "$script" 2>&1 | sed 's/^/    /'
    rc=${PIPESTATUS[0]}
    [ "$rc" -ne 0 ] && log "$script exited $rc"
    case "$script" in
        crawl_sjc_*) [ "$rc" -gt "$sjc_rc" ] && sjc_rc=$rc ;;
    esac
    # Keep the worst exit code, but carry on: a Yahoo outage inside
    # crawl_gold_silver.py must not stop the SJC crawlers from having run.
    [ "$rc" -gt "$crawl_rc" ] && crawl_rc=$rc
done

after=$(probe)

# A writer is healthy only if its newest crawl_time for today MOVED during this
# run. "-" (no row at all) and "unchanged" both mean this run wrote nothing for
# it, and both used to read as green.
judge "$before" "$after"

log "before: $before"
log "after : $after"

if [ "$fresh" -eq 0 ]; then
    log "FAILED: no writer advanced this run —$stale (sjc exit=$sjc_rc, other exit=$crawl_rc)"
    exit 1
fi

# At least one writer advanced, so the DB moved and the published files should
# follow even if another writer is sick. Regenerate before deciding the exit
# code: a degraded run still has fresher data than no run.
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
# reverts these files to whatever is committed; the next run, at most an hour
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

# Three separate ways this run can still be wrong, each with its own line so the
# journal says which one happened rather than just "exit 1".
rc=0
if [ -n "$stale" ]; then
    log "DEGRADED: writer(s) did not advance —$stale"
    rc=1
fi
if [ "$sjc_rc" -ne 0 ]; then
    log "DEGRADED: an SJC crawler exited $sjc_rc — implausible quote or the two sources disagree (see above)"
    rc=1
fi
[ "$rc" -eq 0 ] && log "OK: every writer advanced; other exit=$crawl_rc (non-zero is expected when Yahoo blocks this IP)"
exit $rc
