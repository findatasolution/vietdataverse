"""Pytest bootstrap: put the repo root and be/ on sys.path so tests can import
`be.core.*`, `be.fuel.*`, and `crawl_tools.*` regardless of the invocation CWD.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, os.path.join(ROOT, "be")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
