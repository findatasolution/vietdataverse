"""Bulletin discovery for crawl_tools/crawl_moit_fuel.py — no network."""
from datetime import date

from crawl_tools import crawl_moit_fuel as crawler

NOT_FOUND = ("", 302)


def _page(published: str) -> str:
    return (f'<meta property="article:published_time" itemprop="datePublished" '
            f'content="{published}T15:01:49+0700" /><p>bulletin</p>')


def _fake_fetch(pages: dict):
    def fetch(url):
        return (pages[url], 200) if url in pages else NOT_FOUND
    return fetch


YEARLESS_0903 = "https://moit.gov.vn/tin-tuc/thong-bao/mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-3-9.html"
YEARLESS_0910 = "https://moit.gov.vn/tin-tuc/thong-bao/mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-10-9.html"


def test_published_date_is_read_from_article_meta():
    assert crawler._published_date(_page("2026-09-10")) == date(2026, 9, 10)
    assert crawler._published_date("<p>no meta</p>") is None


def test_probe_finds_every_missed_yearless_cycle_in_order():
    # 2026-09: MOIT dropped the year from the slug and filed under /thong-bao/;
    # the crawler found neither cycle while CI stayed green.
    fetch = _fake_fetch({YEARLESS_0903: _page("2026-09-03"), YEARLESS_0910: _page("2026-09-10")})
    found = crawler.discover_new(date(2026, 8, 27), today=date(2026, 9, 17), fetch=fetch, indexes=())
    assert found == [(date(2026, 9, 3), YEARLESS_0903), (date(2026, 9, 10), YEARLESS_0910)]


def test_yearless_slug_from_a_previous_year_is_rejected():
    # Next September the same year-less URL still serves the 2026 article.
    fetch = _fake_fetch({YEARLESS_0910: _page("2026-09-10")})
    found = crawler.discover_new(date(2027, 9, 1), today=date(2027, 9, 12), fetch=fetch, indexes=())
    assert found == []


def test_category_listing_with_yearless_link_does_not_crash():
    index = "https://moit.gov.vn/tin-tuc/thong-bao"
    listing = '<a href="/tin-tuc/thong-bao/mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-10-9.html">x</a>'
    fetch = _fake_fetch({index: listing, YEARLESS_0910: _page("2026-09-10")})
    found = crawler.discover_new(date(2026, 9, 3), today=date(2026, 9, 3), fetch=fetch, indexes=(index,))
    assert found == [(date(2026, 9, 10), YEARLESS_0910)]


def test_nothing_newer_than_latest_known_is_returned():
    fetch = _fake_fetch({YEARLESS_0903: _page("2026-09-03")})
    assert crawler.discover_new(date(2026, 9, 3), today=date(2026, 9, 17), fetch=fetch, indexes=()) == []
