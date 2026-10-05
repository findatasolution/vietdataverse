"""The indexable dataset pages must render from the committed fe/data files.

They are the only data URLs Google can index (the SPA's charts are hash
routes), so a page that 503s because a generator renamed a field silently
drops out of search. These tests render every page against the real files.
"""
import asyncio
import pathlib
import re
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "be"))

from routers import seo_pages  # noqa: E402


def _body(slug):
    resp = asyncio.run(seo_pages._make(slug, seo_pages.PAGES[slug])())
    assert resp.status_code == 200, slug
    return resp.body.decode()


def test_every_page_renders_with_core_seo_tags():
    for slug in seo_pages.PAGES:
        html = _body(slug)
        assert f'<link rel="canonical" href="https://vietdataverse.online/{slug}">' in html
        assert re.search(r'<meta name="description" content="[^"]{60,}"', html), slug
        assert '"@type": "Dataset"' in html and '"@type": "FAQPage"' in html, slug
        assert "<tbody><tr>" in html, f"{slug}: empty history table"


def test_nav_and_sitemap_cover_every_page():
    sitemap = (ROOT / "fe" / "sitemap.xml").read_text()
    footer = (ROOT / "fe" / "partials" / "_layout_footer.html").read_text()
    assert {s for s, _ in seo_pages.NAV} == set(seo_pages.PAGES)
    for slug in seo_pages.PAGES:
        assert f"https://vietdataverse.online/{slug}</loc>" in sitemap, slug
        assert f'href="/{slug}"' in footer, slug


def test_hom_nay_only_for_fresh_data():
    today = date.today().isoformat()
    assert seo_pages._fresh(today) == "hôm nay"
    assert seo_pages._fresh("2020-01-01") == "mới nhất"


def test_vietnamese_number_format():
    assert seo_pages._num(143500000) == "143.500.000"
    assert seo_pages._pct(4.5) == "4,50%"


def test_missing_data_file_is_503_not_500(monkeypatch):
    monkeypatch.setattr(seo_pages, "_DATA", "/nonexistent")
    resp = asyncio.run(seo_pages._make("gia-vang-sjc", seo_pages.PAGES["gia-vang-sjc"])())
    assert resp.status_code == 503
