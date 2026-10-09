"""Backend regression tests; all API calls use deterministic local fakes."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import requests

from src.platform_service import (
    ResearchError, SOURCE, WorldBankClient,
    build_research, csv_bytes, excel_bytes, retry_failed_series, validate_request,
)

CODE = "NY.GDP.MKTP.KD.ZG"
META = {"id": CODE, "name": "GDP growth (annual %)", "unit": "",
        "source": {"id": "2", "value": "World Development Indicators"},
        "sourceNote": "Annual percentage growth.", "sourceOrganization": "World Bank"}


def observation(year=2020, value=1.5, country="NGA", code=CODE):
    return {"date": str(year), "value": value, "countryiso3code": country,
            "indicator": {"id": code, "value": META["name"]}}


def response(rows, page=1, pages=1, total=None):
    return [{"page": page, "pages": pages, "total": len(rows) if total is None else total,
             "lastupdated": "2026-10-01"}, rows]


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class FakeSession:
    def __init__(self, *bodies):
        self.bodies = list(bodies)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.bodies:
            raise AssertionError("Unexpected API call")
        body = self.bodies.pop(0)
        if isinstance(body, requests.RequestException):
            raise body
        return FakeResponse(body)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def client(self, *bodies):
        return WorldBankClient(self.folder, FakeSession(*bodies))

    def test_validate_inputs(self):
        validate_request("NGA", CODE, 1990, 2025)
        for args in [("NG", CODE, 1990, 2020), ("../", CODE, 1990, 2020),
                     ("NGA", "../evil", 1990, 2020), ("NGA", CODE, 2021, 2020),
                     ("NGA", CODE, 1959, 2020), ("NGA", CODE, True, 2020),
                     ("NGA", CODE, 2000, 9999)]:
            with self.subTest(args=args), self.assertRaises(ResearchError):
                validate_request(*args)

    def test_series_cache_and_missing_years(self):
        client = self.client(response([observation(2020), observation(2022, None)]))
        series = client.series("NGA", CODE, 2020, 2022, META)
        self.assertEqual(series.values["Year"].tolist(), [2020, 2021, 2022])
        self.assertEqual(series.values[CODE].isna().tolist(), [False, True, True])
        self.assertEqual(series.metadata, META)
        second = client.series("NGA", CODE, 2020, 2022, META)
        self.assertEqual(second.status, "validated cache")
        self.assertEqual(len(client.session.calls), 1)
        self.assertEqual(client.session.calls[0][1]["timeout"], (5, 25))
        self.assertEqual(client.session.calls[0][1]["params"]["source"], SOURCE)

    def test_country_period_indicator_isolation(self):
        other = {**META, "id": "FP.CPI.TOTL.ZG"}
        client = self.client(response([observation()]), response([observation(country="GHA")]),
                             response([observation(2021)]), response([observation(code=other["id"])]))
        client.series("NGA", CODE, 2020, 2020, META)
        client.series("GHA", CODE, 2020, 2020, META)
        client.series("NGA", CODE, 2021, 2021, META)
        client.series("NGA", other["id"], 2020, 2020, other)
        self.assertEqual(len(list(self.folder.glob("*.json"))), 4)

    def test_corrupt_cache_is_not_reused(self):
        client = self.client(response([observation()]), response([observation(value=9)]))
        client.series("NGA", CODE, 2020, 2020, META)
        path = next(self.folder.glob("*.json"))
        envelope = json.loads(path.read_text())
        envelope["payload"]["rows"][0]["value"] = 999
        path.write_text(json.dumps(envelope))
        series = client.series("NGA", CODE, 2020, 2020, META)
        self.assertEqual(series.values[CODE].iloc[0], 9)

    def test_semantically_invalid_cache_rejected_even_with_checksum(self):
        client = self.client(response([observation()]), response([observation(value=7)]))
        client.series("NGA", CODE, 2020, 2020, META)
        path = next(self.folder.glob("*.json"))
        envelope = json.loads(path.read_text())
        envelope["payload"]["rows"][0]["country"] = "GHA"
        client.cache.write(envelope["identity"], envelope["payload"])
        self.assertEqual(client.series("NGA", CODE, 2020, 2020, META).values[CODE].iloc[0], 7)

    def test_pagination(self):
        client = self.client(response([observation(2020)], pages=2, total=2),
                             response([observation(2021)], page=2, pages=2, total=2))
        result = client.series("NGA", CODE, 2020, 2021, META)
        self.assertEqual(len(result.values), 2)
        self.assertEqual(client.session.calls[1][1]["params"]["page"], 2)

    def test_malformed_or_mismatched_observations_not_cached(self):
        for body in [[{"message": [{"value": "Invalid value"}]}],
                     response([observation(country="GHA")]),
                     response([observation(code="BAD")]),
                     response([observation(2019)]),
                     response([observation(), observation()]),
                     response([observation(value="invalid")]),
                     response([observation(value=float("inf"))]),
                     response([observation()], total=2),
                     ValueError("bad json")]:
            with self.subTest(body=body):
                client = self.client(body)
                with self.assertRaises(ResearchError):
                    client.series("NGA", CODE, 2020, 2020, META)
                self.assertEqual(list(self.folder.glob("*.json")), [])

    def test_timeout_and_stale_cache_fallback(self):
        client = self.client(response([observation()]), requests.Timeout())
        first = client.series("NGA", CODE, 2020, 2020, META)
        client.cache.ttl = -1
        result = client.series("NGA", CODE, 2020, 2020, META)
        self.assertIn("stale cache", result.status)
        self.assertEqual(result.retrieved_at, first.retrieved_at)
        with self.assertRaises(ResearchError):
            self.client(requests.Timeout()).series("GHA", CODE, 2020, 2020, META)

    def test_refresh_bypasses_fresh_cache(self):
        client = self.client(response([observation()]), response([observation(value=3)]))
        client.series("NGA", CODE, 2020, 2020, META)
        self.assertEqual(client.series("NGA", CODE, 2020, 2020, META, refresh=True).values[CODE].iloc[0], 3)

    def test_catalog_filters_aggregates_and_search_metadata(self):
        client = self.client(response([
            {"id": "NGA", "name": "Nigeria", "region": {"id": "SSF"}},
            {"id": "WLD", "name": "World", "region": {"id": "NA"}},
        ]), response([META]))
        self.assertEqual(client.catalog("countries").items[0]["id"], "NGA")
        self.assertEqual(len(client.catalog("countries").items), 1)
        self.assertEqual(client.catalog("indicators").items[0]["sourceNote"], META["sourceNote"])
        self.assertEqual(len(client.session.calls), 2)

    def test_empty_catalog_and_wrong_source_rejected(self):
        for body in [response([]), response([{**META, "source": {"id": "1"}}])]:
            with self.assertRaises(ResearchError):
                self.client(body).catalog("indicators")

    def test_null_and_empty_data_are_missing_not_zero(self):
        for body in [response([]), [{"page": 1, "pages": 1, "total": 0}, None],
                     [{"page": 1, "pages": 0, "total": 0}, []]]:
            series = self.client(body).series("NGA", CODE, 2020, 2022, META)
            self.assertTrue(series.values[CODE].isna().all())

    def test_original_lowercase_indicator_code_is_preserved(self):
        code = "per_allsp.cov_pop_tot"
        meta = {**META, "id": code}
        client = self.client(response([meta]), response([observation(code=code)]))
        self.assertEqual(client.catalog("indicators").items[0]["id"], code)
        self.assertIn(code, client.series("NGA", code, 2020, 2020, meta).values.columns)

    def test_wrong_metadata_does_not_cache_observations(self):
        client = self.client(response([observation()]))
        with self.assertRaises(ResearchError):
            client.series("NGA", CODE, 2020, 2020, {**META, "id": "BAD"})
        self.assertEqual(list(self.folder.glob("*.json")), [])

    def test_readonly_cache_still_returns_live_series(self):
        client = self.client(response([observation()]))
        with patch("src.platform_service.tempfile.NamedTemporaryFile", side_effect=PermissionError()):
            result = client.series("NGA", CODE, 2020, 2020, META)
        self.assertIn("cache unavailable", result.status)
        self.assertEqual(result.values[CODE].iloc[0], 1.5)

    def test_catalog_stale_fallback_retains_timestamp(self):
        client = self.client(response([META]), requests.Timeout())
        first = client.catalog("indicators")
        client.cache.ttl = -1
        stale = client.catalog("indicators")
        self.assertIn("stale cache", stale.status)
        self.assertEqual(stale.retrieved_at, first.retrieved_at)

    def test_partial_failure_is_explicit_in_report_and_exports(self):
        client = self.client(response([observation(2020, 0)]), requests.Timeout())
        countries = [{"id": "NGA", "name": "Nigeria"}, {"id": "GHA", "name": "Ghana"}]
        result = build_research(client, countries, [META], 2020, 2021)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.quality["Missing"].tolist(), [1, 2])
        self.assertIn("retrieval failed", result.quality.iloc[1]["Retrieval status"])
        data = pd.read_csv(BytesIO(csv_bytes(result.data)))
        pd.testing.assert_frame_equal(data, result.data)
        workbook = pd.read_excel(BytesIO(excel_bytes(result)), sheet_name=None)
        self.assertEqual(set(workbook), {"Data", "Missing values", "Indicator metadata", "Sources"})
        self.assertEqual(workbook["Data"][CODE].iloc[0], 0)

    def test_limits_and_empty_selections(self):
        client = self.client()
        for countries, indicators in [([], [META]), ([{"id": "NGA", "name": "Nigeria"}], []),
                                      ([{"id": "NGA", "name": "Nigeria"}] * 6, [META])]:
            with self.assertRaises(ResearchError):
                build_research(client, countries, indicators, 2020, 2021)
        self.assertEqual(client.session.calls, [])

    def test_progress_counts_success_failure_and_coverage_years(self):
        events = []
        client = self.client(response([observation(2020, 0), observation(2022, 2)]), requests.Timeout())
        result = build_research(client, [{"id": "NGA", "name": "Nigeria"}, {"id": "GHA", "name": "Ghana"}],
                                [META], 2020, 2022, on_progress=lambda *event: events.append(event))
        self.assertEqual([event[:2] for event in events], [(1, 2), (2, 2)])
        self.assertEqual(result.quality["Coverage (%)"].tolist(), [66.67, 0])
        self.assertEqual(result.quality["First available year"].iloc[0], 2020)
        self.assertEqual(result.quality["Last available year"].iloc[0], 2022)
        self.assertTrue(pd.isna(result.quality["First available year"].iloc[1]))

    def test_retry_preserves_success_and_identity(self):
        countries = [{"id": "NGA", "name": "Nigeria"}, {"id": "GHA", "name": "Ghana"}]
        client = self.client(response([observation()]), requests.Timeout(),
                             response([observation(country="GHA", value=4)]))
        original = build_research(client, countries, [META], 2020, 2021)
        events = []
        recovered = retry_failed_series(client, original, countries, [META], 2020, 2021,
                                        on_progress=lambda *event: events.append(event))
        self.assertEqual(len(client.session.calls), 3)
        self.assertEqual(recovered.errors, [])
        pd.testing.assert_frame_equal(recovered.data.iloc[:2], original.data.iloc[:2])
        pd.testing.assert_series_equal(recovered.provenance.iloc[0], original.provenance.iloc[0])
        self.assertTrue(original.data.loc[original.data["Country code"] == "GHA", CODE].isna().all())
        self.assertEqual(events[0][:2], (1, 1))
        with self.assertRaises(ResearchError):
            retry_failed_series(client, original, countries, [META], 2020, 2022)

    def test_failed_retry_keeps_partial_dataset(self):
        client = self.client(requests.Timeout(), requests.Timeout())
        countries = [{"id": "NGA", "name": "Nigeria"}]
        original = build_research(client, countries, [META], 2020, 2021)
        recovered = retry_failed_series(client, original, countries, [META], 2020, 2021)
        self.assertEqual(len(recovered.errors), 1)
        pd.testing.assert_frame_equal(recovered.data, original.data)


if __name__ == "__main__":
    unittest.main()
