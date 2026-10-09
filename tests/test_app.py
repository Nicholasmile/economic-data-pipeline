"""Streamlit flow tests using fake World Bank responses, with no network."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.platform_service import Catalog, WorldBankClient
from test_backend import CODE, META, FakeSession, observation, response


class AppTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.client = WorldBankClient(Path(self.folder.name), FakeSession(response([
            observation(2020), observation(2022, None)])))
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)

    def catalogs(self):
        self.app.session_state["catalogs"] = (
            Catalog([{"id": "NGA", "name": "Nigeria"}, {"id": "GHA", "name": "Ghana"}], "test catalogue", "2026-10-09"),
            Catalog([META], "test catalogue", "2026-10-09"),
        )

    def button(self, label):
        return next(button for button in self.app.button if button.label == label)

    def test_landing_page_does_not_call_api(self):
        with patch("src.platform_service.WorldBankClient", return_value=self.client):
            self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.client.session.calls, [])
        self.assertIn("Economic data", self.app.title[0].value)

    def test_build_downloads_and_changed_selection_notice(self):
        self.catalogs()
        with patch("src.platform_service.WorldBankClient", return_value=self.client):
            self.app.run()
            self.app.number_input[0].set_value(2020)
            self.app.number_input[1].set_value(2022)
            self.button("Build research dataset").click().run()
            self.assertFalse(self.app.exception)
            self.assertEqual(len(self.app.segmented_control[0].options), 5)
            self.assertEqual(len(self.app.get("download_button")), 4)
            self.assertEqual(self.app.session_state["result"].quality["Missing"].iloc[0], 2)
            self.app.number_input[0].set_value(2021).run()
            self.assertTrue(any("Selections changed" in item.value for item in self.app.info))
            self.assertEqual(len(self.client.session.calls), 1)

    def test_invalid_year_range_is_friendly_error(self):
        self.catalogs()
        with patch("src.platform_service.WorldBankClient", return_value=self.client):
            self.app.run()
            self.app.number_input[0].set_value(2025)
            self.app.number_input[1].set_value(2020)
            self.button("Build research dataset").click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertEqual(self.client.session.calls, [])

    def test_search_retains_selection(self):
        self.catalogs()
        self.app.run()
        self.app.text_input[0].set_value("unmatched query").run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.multiselect(key="chosen_indicators").value, [CODE])

    def test_api_failure_is_friendly(self):
        from src.platform_service import ResearchError
        with patch("src.platform_service.WorldBankClient", return_value=self.client):
            self.app.run()
            with patch.object(self.client, "catalog", side_effect=ResearchError("Connect and retry.")):
                self.button("Load World Bank catalogues").click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any("Connect and retry" in error.value for error in self.app.error))

    def test_multi_country_build_and_empty_selection(self):
        self.catalogs()
        self.client.session.bodies.append(response([observation(2020, country="GHA")]))
        with patch("src.platform_service.WorldBankClient", return_value=self.client):
            self.app.run()
            self.app.multiselect(key="chosen_countries").set_value(["NGA", "GHA"])
            self.app.number_input[0].set_value(2020)
            self.app.number_input[1].set_value(2022)
            self.button("Build research dataset").click().run()
            self.assertFalse(self.app.exception)
            result = self.app.session_state["result"]
            self.assertEqual(result.data["Country code"].unique().tolist(), ["NGA", "GHA"])
            self.app.multiselect(key="chosen_indicators").set_value([])
            self.button("Build research dataset").click().run()
            self.assertFalse(self.app.exception)
            self.assertTrue(self.app.error)

    def test_preset_and_period_shortcut(self):
        self.catalogs()
        self.app.run()
        self.app.selectbox(key="preset").set_value("Employment").run()
        self.assertEqual(self.app.multiselect(key="chosen_indicators").value, [])
        self.app.selectbox(key="preset").set_value("Growth and inflation").run()
        self.assertEqual(self.app.multiselect(key="chosen_indicators").value, [CODE])
        self.app.selectbox(key="period_shortcut").set_value("Last 10 completed years").run()
        from src.platform_service import current_year
        self.assertEqual(self.app.number_input(key="start_year").value, current_year() - 10)
        self.assertEqual(self.app.number_input(key="end_year").value, current_year() - 1)
        self.assertFalse(self.app.exception)

    def test_chart_controls_and_readable_headers_reuse_exports(self):
        self.catalogs()
        from src.platform_service import excel_bytes
        with patch("src.platform_service.WorldBankClient", return_value=self.client), \
             patch("src.platform_service.excel_bytes", wraps=excel_bytes) as export:
            self.app.run()
            self.app.number_input(key="start_year").set_value(2020)
            self.app.number_input(key="end_year").set_value(2022)
            self.button("Build research dataset").click().run()
            workbook = self.app.session_state["excel_export"]
            self.app.toggle[0].set_value(True).run()
            self.assertEqual(self.app.session_state["excel_export"], workbook)
            self.app.segmented_control(key="result_view").set_value("Charts").run()
            self.assertFalse(self.app.exception)
            self.assertEqual(self.app.selectbox(key="chart_indicator").value, CODE)
            self.app.selectbox(key="chart_highlight").set_value("NGA").run()
            self.app.segmented_control(key="result_view").set_value("Coverage").run()
            self.assertFalse(self.app.exception)
            self.assertEqual(len(self.client.session.calls), 1)

            self.assertEqual(export.call_count, 1)

    def test_retry_only_failed_country_and_preserve_previous(self):
        import requests
        self.catalogs()
        self.client.session.bodies += [requests.Timeout(), response([observation(2020, country="GHA", value=5)])]
        with patch("src.platform_service.WorldBankClient", return_value=self.client):
            self.app.run()
            self.app.multiselect(key="chosen_countries").set_value(["NGA", "GHA"])
            self.app.number_input(key="start_year").set_value(2020)
            self.app.number_input(key="end_year").set_value(2022)
            self.button("Build research dataset").click().run()
            before = self.app.session_state["result"]
            self.button("Retry failed series").click().run()
            self.assertFalse(self.app.exception)
            self.assertEqual(self.app.session_state["result"].errors, [])
            self.assertEqual(len(before.errors), 1)
            self.assertEqual(len(self.client.session.calls), 3)

    def test_existing_mvp_session_is_upgraded_without_new_requests(self):
        from src.platform_service import build_research
        self.catalogs()
        result = build_research(self.client, [{"id": "NGA", "name": "Nigeria"}], [META], 2020, 2022)
        self.app.session_state["result"] = result
        self.app.session_state["result_settings"] = (["NGA"], [CODE], 2020, 2022)
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state["result_selections"][0][0]["id"], "NGA")
        self.assertEqual(len(self.client.session.calls), 1)
        self.assertEqual(self.app.session_state["result"].data[CODE].iloc[0], 1.5)


if __name__ == "__main__":
    unittest.main()
