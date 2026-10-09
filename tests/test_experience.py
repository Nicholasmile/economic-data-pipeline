import json
from pathlib import Path
import tempfile
import unittest

from src.platform_service import WorldBankClient, build_research
from src.research_experience import coverage_table, research_chart, research_notes
from test_backend import CODE, META, FakeSession, observation, response


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        client = WorldBankClient(Path(self.temp.name), FakeSession(response([
            observation(2020, 0), observation(2022, 3)])))
        self.result = build_research(client, [{"id": "NGA", "name": "Nigeria"}], [META], 2020, 2022)

    def test_citation_and_settings_preserve_request_and_sources(self):
        citation, notes = research_notes(self.result, (["NGA"], [CODE], 2020, 2022))
        payload = json.loads(notes)
        self.assertIn("World Bank", citation)
        self.assertIn("2020–2022", citation)
        self.assertEqual(payload["indicator_codes"], [CODE])
        self.assertEqual(payload["sources"][0]["API URL"], self.result.provenance.iloc[0]["API URL"])

    def test_coverage_has_names_and_does_not_change_data(self):
        table = coverage_table(self.result)
        self.assertEqual(table.iloc[0]["Country"], "Nigeria")
        self.assertEqual(table.iloc[0]["Indicator"], META["name"])
        self.assertEqual(self.result.data.columns[-1], CODE)

    def test_chart_segments_leave_gap_and_escape_original_code(self):
        chart = research_chart(self.result.data, CODE, META["name"], "NGA")
        values = chart.data
        self.assertNotEqual(values["Segment"].iloc[0], values["Segment"].iloc[2])
        self.assertTrue(values[CODE].isna().iloc[1])
        spec = chart.to_dict()
        self.assertEqual(spec["encoding"]["y"]["field"], CODE.replace(".", "\\."))


if __name__ == "__main__":
    unittest.main()
