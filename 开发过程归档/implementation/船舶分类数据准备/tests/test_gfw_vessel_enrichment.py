import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError


SCRIPT = Path(__file__).parents[1] / "gfw_vessel_enrichment.py"
SPEC = importlib.util.spec_from_file_location("gfw_vessel_enrichment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def row(mmsi, category, priority, positions=10, conflict=""):
    return {
        "mmsi": mmsi,
        "ais_rough_categories": category,
        "query_priority": priority,
        "query_value": "9074729" if priority == "imo" else mmsi,
        "preferred_imo": "9074729" if priority == "imo" else "",
        "valid_position_rows": str(positions),
        "identity_conflict": conflict,
    }


class FakeResponse:
    status = 200
    headers = {
        "x-ratelimit-daily-remaining-requests": "49999",
        "x-ratelimit-monthly-remaining-requests": "1499999",
    }

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class GfwPilotTests(unittest.TestCase):
    def test_selection_covers_categories_and_query_modes(self):
        rows = []
        counter = 100000000
        for category in MODULE.CATEGORY_ORDER:
            for priority in ("imo", "mmsi"):
                counter += 1
                rows.append(row(str(counter), category, priority, positions=counter % 20 + 1))
        rows.append(row("299999999", "cargo_unspecified", "imo", positions=1, conflict="vessel_name"))
        selected = MODULE.select_pilot(rows, 20)
        self.assertEqual(len(selected), len(rows))
        self.assertIn("299999999", {item["mmsi"] for item in selected})
        self.assertEqual({MODULE.row_category(item) for item in selected}, set(MODULE.CATEGORY_ORDER))
        self.assertEqual({item["query_priority"] for item in selected}, {"imo", "mmsi"})

    def test_fill_uses_category_round_robin(self):
        rows = []
        counter = 300000000
        for category in MODULE.CATEGORY_ORDER:
            for _ in range(6):
                counter += 1
                rows.append(row(str(counter), category, "mmsi", positions=counter % 30 + 1))
        selected = MODULE.select_pilot(rows, 18)
        counts = {category: sum(MODULE.row_category(item) == category for item in selected) for category in MODULE.CATEGORY_ORDER}
        self.assertEqual(set(counts.values()), {3})

    def test_success_is_cached_and_second_call_uses_cache(self):
        payload = {"entries": [{"dataset": "public-global-vessel-identity:v4.0"}]}
        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as directory:
            vessel = row("123456789", "cargo_unspecified", "imo")
            first = MODULE.fetch_one(vessel, "secret", Path(directory), 3, 5, opener=opener, sleeper=lambda _: None)
            second = MODULE.fetch_one(vessel, "secret", Path(directory), 3, 5, opener=opener, sleeper=lambda _: None)
            self.assertEqual(first["status"], "success")
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(first["dataset_versions"], "public-global-vessel-identity:v4.0")

    def test_no_result_is_distinct_from_request_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = MODULE.fetch_one(
                row("123456789", "unknown", "mmsi"),
                "secret",
                Path(directory),
                1,
                5,
                opener=lambda request, timeout: FakeResponse({"entries": []}),
                sleeper=lambda _: None,
            )
            self.assertEqual(result["status"], "no_result")
            self.assertEqual(result["http_status"], 200)

    def test_authentication_failure_stops_without_retry(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))

        with tempfile.TemporaryDirectory() as directory:
            result = MODULE.fetch_one(
                row("123456789", "unknown", "mmsi"),
                "bad-token",
                Path(directory),
                3,
                5,
                opener=opener,
                sleeper=lambda _: self.fail("401 must not retry"),
            )
            self.assertEqual(result["status"], "authentication_failed")
            self.assertEqual(result["attempts"], 1)

    def test_rate_limit_classification_is_retryable(self):
        self.assertEqual(MODULE.error_status(429), ("rate_limited", True))
        self.assertEqual(MODULE.error_status(403), ("permission_denied", False))


if __name__ == "__main__":
    unittest.main()
