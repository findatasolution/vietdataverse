import unittest

from crawl_tools.global_market_sources import fetch_fred_history, fill_missing_indices


class FakeResponse:
    text = "observation_date,SP500\n2026-07-01,101.5\n2026-07-02,103.25\n"

    def raise_for_status(self):
        return None


class FakeSession:
    def get(self, *args, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class GlobalMarketSourcesTest(unittest.TestCase):
    def test_parses_fred_csv(self):
        session = FakeSession()
        result = fetch_fred_history("SP500", session=session)
        self.assertEqual(result["2026-07-02"], 103.25)
        self.assertEqual(session.kwargs["params"]["id"], "SP500")

    def test_fills_only_missing_indices(self):
        series = {
            "gold_price": {"2026-07-02": 2500.0},
            "nasdaq_price": {"2026-07-02": 25832.67},
            "sp500_price": {},
            "dowjones_price": {},
        }
        calls = []

        def fetcher(symbol):
            calls.append(symbol)
            return {"2026-07-02": 123.0}

        fallback = fill_missing_indices(series, fetcher=fetcher)
        self.assertEqual(calls, ["SP500", "DJIA"])
        self.assertEqual(
            fallback,
            {"sp500_price": {"2026-07-02"}, "dowjones_price": {"2026-07-02"}},
        )
        self.assertEqual(series["nasdaq_price"]["2026-07-02"], 25832.67)

    def test_fills_trailing_gap_in_nonempty_series(self):
        series = {
            "gold_price": {"2026-07-03": 2500.0},
            "nasdaq_price": {"2026-07-02": 25832.67},
            "sp500_price": {"2026-07-03": 7000.0},
            "dowjones_price": {"2026-07-03": 50000.0},
        }

        fallback = fill_missing_indices(
            series,
            fetcher=lambda symbol: {"2026-07-02": 100.0, "2026-07-03": 101.0},
        )
        self.assertEqual(fallback, {"nasdaq_price": {"2026-07-03"}})
        self.assertEqual(series["nasdaq_price"]["2026-07-03"], 101.0)


if __name__ == "__main__":
    unittest.main()
