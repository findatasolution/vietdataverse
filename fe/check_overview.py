#!/usr/bin/env python3
"""Structural invariant checks for the Open Data overview feature.

No JS test runner exists in this repo (zero-dep static FE). This script
verifies what CAN be checked without a browser: that the built index.html and
the registry in app.overview.js stay internally consistent. It does not
replace visually checking Chart.js rendering — see the plan's manual QA pass
for that.

Run: python3 fe/check_overview.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
errors = []


def fail(msg):
    errors.append(msg)


def main():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    overview_js = (ROOT / 'app.overview.js').read_text(encoding='utf-8')

    # ── Registry structure ──────────────────────────────────────────────
    ids = re.findall(r"id: '(\w+)'", overview_js)
    reg_ids = [i for i in ids if i in (
        'gold', 'silver', 'termdepo', 'interbank', 'policy',
        'fxrate', 'global', 'cpi', 'gdp', 'trade', 'vnindex')]
    if len(reg_ids) != 11:
        fail(f'CHART_REGISTRY: expected 11 entries, found {len(reg_ids)}: {reg_ids}')
    if len(set(reg_ids)) != len(reg_ids):
        fail(f'CHART_REGISTRY: duplicate ids present: {reg_ids}')

    # ── Every static-file registry entry points at a real file with the
    #    right field, exactly as generate_static_data.py produces it ──────
    blocks = re.findall(r"id: '(\w+)'.*?mini: \{([^}]*)\}", overview_js, re.S)
    for cid, mini in blocks:
        m_file = re.search(r"file: 'data/([^']+)'", mini)
        m_series = re.search(r"series: '([^']+)'", mini)
        m_records = 'recordsMode: true' in mini
        m_datefield = re.search(r"dateField: '([^']+)'", mini)
        m_live = re.search(r"live: '([^']+)'", mini)
        if m_live:
            continue  # fetched live (GDP) — no static file to check
        if not m_file or not m_series:
            fail(f'{cid}: mini config missing file or series'); continue
        f = m_file.group(1)
        p = ROOT / 'data' / f
        if not p.exists():
            fail(f'{cid}: data/{f} does not exist'); continue
        raw = json.loads(p.read_text(encoding='utf-8'))
        payload = raw.get('data', raw) if isinstance(raw, dict) else raw
        if m_records:
            if not isinstance(payload, list) or not payload:
                fail(f'{cid}: recordsMode but data/{f} is not a non-empty list'); continue
            rec = payload[0]
            if m_datefield.group(1) not in rec or m_series.group(1) not in rec:
                fail(f'{cid}: record missing dateField/series in data/{f}: {rec}')
        else:
            if not isinstance(payload, dict) or 'dates' not in payload:
                fail(f'{cid}: expected {{dates: [...]}} shape in data/{f}'); continue
            if not isinstance(payload.get(m_series.group(1)), list):
                fail(f'{cid}: field "{m_series.group(1)}" missing/not a list in data/{f}')

    # ── HTML: exactly one visible overview root + detail bar + 10 chart-cards
    #    tagged with data-chart-id (interbank/policy share one) ───────────
    if html.count('id="data-charts"') != 1:
        fail('index.html: expected exactly one #data-charts element')
    if html.count('id="ov-detail-bar"') != 1:
        fail('index.html: expected exactly one #ov-detail-bar element')

    dom_ids = re.findall(r'data-chart-id="(\w+)"', html)
    # data-chart-id appears on: 10 .chart-card wrappers + 11 mini-tile <button>
    # markup is JS-generated so won't be in the static HTML — only the 10 cards.
    if sorted(dom_ids) != sorted(['gold', 'silver', 'termdepo', 'interbank',
                                  'fxrate', 'global', 'cpi', 'gdp', 'trade', 'vnindex']):
        fail(f'index.html: chart-card data-chart-id set is wrong: {sorted(dom_ids)}')

    if html.count('id="sbv-policy-anchor"') != 1:
        fail('index.html: expected exactly one #sbv-policy-anchor (policy scroll target)')

    # The 5 sections must start hidden in the STATIC markup — this is the
    # safe-default the whole routing design leans on.
    for sec in ['gold-silver', 'currency', 'global', 'macro', 'stock']:
        pat = f'class="chart-section-group ov-section-hidden" data-lazy-section="{sec}"'
        if pat not in html:
            fail(f'index.html: section "{sec}" is not statically hidden by default')

    # Every registry id must resolve to a domCardId that actually exists in
    # the DOM (interbank/policy both resolve to "interbank").
    dom_card_map = dict(re.findall(r"id: '(\w+)'.*?domCardId: '(\w+)'", overview_js, re.S))
    for cid in reg_ids:
        dom_id = dom_card_map.get(cid)
        if not dom_id:
            fail(f'{cid}: no domCardId found in registry'); continue
        if dom_id not in dom_ids:
            fail(f'{cid}: domCardId "{dom_id}" has no matching .chart-card in index.html')

    # ── Script load order: app.overview.js must load, chart.js + date adapter
    #    present (registry uses type:'time' for mini charts) ──────────────
    if 'app.overview.js' not in html:
        fail('index.html: app.overview.js script tag missing')
    if 'chartjs-adapter-date-fns' not in html:
        fail('index.html: chartjs-adapter-date-fns missing (mini charts use type: "time")')

    if errors:
        print(f'FAILED — {len(errors)} issue(s):')
        for e in errors:
            print(f'  ✗ {e}')
        sys.exit(1)
    print(f'OK — registry has {len(reg_ids)} charts, all static sources verified, '
          f'DOM tags consistent.')


if __name__ == '__main__':
    main()
