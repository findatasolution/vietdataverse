"""
Build script for fe/index.html.
Concatenates partials in order and writes fe/index.html.

Usage:
    python fe/build.py

Requirements: Python 3.8+, stdlib only (pathlib).
Idempotent — running multiple times produces identical output.
"""

from pathlib import Path

GENERATED_COMMENT = "<!-- GENERATED FILE — edit fe/partials/ instead. Run: python fe/build.py -->\n"

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

    output_path.write_text(combined, encoding="utf-8")

    line_count = combined.count("\n") + (1 if combined and not combined.endswith("\n") else 0)
    print(f"Build complete: {output_path}")
    print(f"  Partials merged : {len(PARTIALS)}")
    print(f"  Output lines    : {line_count}")

if __name__ == "__main__":
    main()
