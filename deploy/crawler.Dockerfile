# Crawler image for the box-side fallback (deploy/crawl-fallback.sh).
#
# Why an image instead of a venv on the box: the box ships Python 3.14 and has no
# python3-venv package, while crawl_tools/requirements.txt pins 3.11-era versions.
# Running the fallback on python:3.11-slim keeps it byte-for-byte the interpreter
# and dependency set CI uses, so "green in Actions, broken on the box" cannot happen.
#
# The repo is bind-mounted at /repo at run time rather than COPYed, so a deploy
# refreshes the crawler code without rebuilding this image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Only the subset crawl_gold_silver.py imports — but version-pinned by feeding
# crawl_tools/requirements.txt to pip as a CONSTRAINT file, so versions stay in
# lockstep with CI without duplicating the list here.
COPY crawl_tools/requirements.txt /tmp/constraints.txt
RUN pip install --no-cache-dir -c /tmp/constraints.txt \
        pandas \
        requests \
        sqlalchemy \
        psycopg2-binary \
        beautifulsoup4 \
        python-dotenv \
        yfinance \
 && rm /tmp/constraints.txt

WORKDIR /repo/crawl_tools
