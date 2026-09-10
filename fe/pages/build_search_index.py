#!/usr/bin/env python3
"""Build fe/pages/docs-search-index.json from the docs pages' own headings.

Stdlib only (matches fe/build.py's "no external deps" rule for fe/). Walks
each page's h1/h2/h3, and for h2/h3 resolves the nearest ancestor element that
carries an `id` (usually the wrapping <section id="...">, since headings in
these pages rarely carry their own id) so a search hit can link straight to
`page.html#id`. Consumed by docs-sidebar.js's search box.

Run after editing any heading/section id in fe/pages/*.html:
    python fe/pages/build_search_index.py
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

PAGES_DIR = Path(__file__).resolve().parent

# (file, nav label) — mirrors NAV in docs-sidebar.js. Only pages using the
# shared docs template (loads docs-sidebar.js) belong here.
PAGES = [
    ("docs.html", "Tổng quan"),
    ("api-docs.html", "API Reference"),
    ("google-sheets.html", "Google Sheets"),
    ("google-sheets-appscript.html", "Sheets — hàm VDV"),
    ("excel.html", "Excel (Power Query)"),
    ("guide-seller.html", "Seller Guide"),
    ("guide-buyer.html", "Buyer Guide"),
    ("knowledge-pack-spec.html", "Tạo Knowledge Pack"),
    ("terms.html", "Điều khoản dịch vụ"),
    ("privacy.html", "Chính sách bảo mật"),
    ("takedown.html", "DMCA / Takedown"),
    ("about-us.html", "Giới thiệu"),
    ("cookie-policy.html", "Cookie Policy"),
]

# Void elements never get handle_endtag — must not be pushed onto the id
# stack or every later pop desyncs from its matching push.
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class HeadingExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.id_stack = [None]
        self.heading_tag = None
        self.heading_buf = []
        self.entries = []  # (anchor_id, tag, text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in VOID_ELEMENTS:
            return
        self.id_stack.append(attrs.get("id") or self.id_stack[-1])
        if tag in ("h1", "h2", "h3"):
            self.heading_tag = tag
            self.heading_buf = []
            if attrs.get("id"):
                self.id_stack[-1] = attrs["id"]

    def handle_startendtag(self, tag, attrs):
        pass  # self-closed (e.g. <br/>) — no push, matches handle_starttag's void skip

    def handle_endtag(self, tag):
        if tag == self.heading_tag:
            text = re.sub(r"\s+", " ", "".join(self.heading_buf)).strip()
            if text:
                self.entries.append((self.id_stack[-1], tag, text))
            self.heading_tag = None
        if tag not in VOID_ELEMENTS and len(self.id_stack) > 1:
            self.id_stack.pop()

    def handle_data(self, data):
        if self.heading_tag:
            self.heading_buf.append(data)


def build():
    index = []
    for filename, nav_label in PAGES:
        path = PAGES_DIR / filename
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        parser = HeadingExtractor()
        parser.feed(html)
        for anchor_id, tag, text in parser.entries:
            if tag == "h1":
                continue  # page title already carried by nav_label/page entry
            index.append({
                "page": filename,
                "pageTitle": nav_label,
                "heading": text,
                "anchor": anchor_id,
            })
        # always index the page itself so a title-only match still works
        index.append({
            "page": filename,
            "pageTitle": nav_label,
            "heading": nav_label,
            "anchor": None,
            "isPage": True,
        })

    out_path = PAGES_DIR / "docs-search-index.json"
    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(index)} entries to {out_path}")


if __name__ == "__main__":
    build()
