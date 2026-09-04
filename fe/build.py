"""
Build script for fe/index.html.
Concatenates partials in order and writes fe/index.html.

Usage:
    python fe/build.py

Requirements: Python 3.8+, stdlib only (pathlib).
Idempotent — running multiple times produces identical output.
"""

import hashlib
import re
from pathlib import Path

GENERATED_COMMENT = "<!-- GENERATED FILE — edit fe/partials/ instead. Run: python fe/build.py -->\n"

# Cache-busted per-file, not with one shared version string. That string
# (?v=YYYYMMDDNN) used to be hand-maintained across 4 <link>/<script> tags
# in the partials and was forgotten more than once — real CSS/JS changes
# shipped to prod while browsers kept serving a stale cached copy under the
# unchanged URL, so a "deployed" fix stayed invisible until a manual hard
# refresh. A hash of the file's own bytes can't go stale like that: it only
# changes when the file's content does, automatically, on every build.
CACHE_BUSTED_ASSETS = ("style.css", "app.js", "app.overview.js")

# Ordered list of partials to concatenate
PARTIALS = [
    "_layout_head.html",
    "_tab_data_portal.html",
    "_tab_market_pulse.html",
    "_tab_knowledge_market.html",
    "_page_about.html",
    "_page_privacy.html",
    "_page_contact.html",
    "_layout_footer.html",
]

def main():
    fe_dir = Path(__file__).resolve().parent
    partials_dir = fe_dir / "partials"
    output_path = fe_dir / "index.html"

    chunks = [GENERATED_COMMENT]

    for partial_name in PARTIALS:
        partial_path = partials_dir / partial_name
        if not partial_path.exists():
            raise FileNotFoundError(f"Missing partial: {partial_path}")
        content = partial_path.read_text(encoding="utf-8")
        chunks.append(content)

    combined = "".join(chunks)

    for asset in CACHE_BUSTED_ASSETS:
        asset_path = fe_dir / asset
        if not asset_path.exists():
            raise FileNotFoundError(f"Missing cache-busted asset: {asset_path}")
        digest = hashlib.sha256(asset_path.read_bytes()).hexdigest()[:10]
        combined, n = re.subn(
            rf"{re.escape(asset)}\?v=[A-Za-z0-9]+",
            f"{asset}?v={digest}",
            combined,
        )
        if n == 0:
            raise ValueError(
                f"No '{asset}?v=...' reference found in the partials to "
                f"cache-bust — check the <link>/<script> tag still exists."
            )

    output_path.write_text(combined, encoding="utf-8")

    line_count = combined.count("\n") + (1 if combined and not combined.endswith("\n") else 0)
    print(f"Build complete: {output_path}")
    print(f"  Partials merged : {len(PARTIALS)}")
    print(f"  Output lines    : {line_count}")

if __name__ == "__main__":
    main()
