"""Exercise billing/quota facts without importing DB or payment credentials."""
import ast
import asyncio
from pathlib import Path
import unittest
from typing import Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]


def load_definitions(path, names, namespace):
    tree = ast.parse(path.read_text())
    selected = []
    for node in tree.body:
        name = getattr(node, "name", None)
        if isinstance(node, ast.Assign):
            name = getattr(node.targets[0], "id", None)
        if name in names:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node.decorator_list = []
            selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)


class PublicPlanTests(unittest.TestCase):
    def setUp(self):
        self.ns = {"Optional": Optional, "urlencode": urlencode, "urlsplit": urlsplit,
                   "urlunsplit": urlunsplit, "FRONTEND_URL": "https://example.test"}
        load_definitions(ROOT / "be/quota.py", {"QUOTA_BY_LEVEL", "QUOTA_BY_PLAN", "get_quota"}, self.ns)
        load_definitions(ROOT / "be/payment.py", {"SUBSCRIPTION_PLANS", "public_plans", "checkout_return_url"}, self.ns)

    def test_catalog_matches_billing_and_quota(self):
        result = asyncio.run(self.ns["public_plans"]())
        self.assertEqual(result["count"], 3)
        self.assertFalse(result["auto_renew"])
        for plan in result["data"]:
            key = plan["key"]
            if key == "free":
                self.assertEqual(plan["monthly"], self.ns["get_quota"]("free", None)["monthly"])
                continue
            actual = self.ns["SUBSCRIPTION_PLANS"][key]
            self.assertEqual(plan["amount"], actual["amount"])
            self.assertEqual(plan["days"], actual["days"])
            self.assertEqual(plan["monthly"], self.ns["get_quota"](actual["level"], key)["monthly"])
            self.assertNotIn("level", plan)

    def test_returns_to_verification_page(self):
        url = self.ns["checkout_return_url"](payment="success", order=123)
        self.assertEqual(url, "https://example.test/pages/pricing.html?payment=success&order=123")
        self.ns["FRONTEND_URL"] = "https://example.test/fe/pages/pricing.html?old=value"
        self.assertEqual(self.ns["checkout_return_url"](payment="cancelled"),
                         "https://example.test/fe/pages/pricing.html?payment=cancelled")


if __name__ == "__main__":
    unittest.main()
