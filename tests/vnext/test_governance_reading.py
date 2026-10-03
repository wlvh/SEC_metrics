"""The governance reading behind C03 and C04, held to the saved documents.

tools/read_governance_facts.py replaces a reading whose code was never
committed and which parsed numbers with int(), skipping what failed. Parsing
the SEC's fixed-zero dash as zero is right, and it turned up something the old
skip had hidden by accident: the pay-versus-performance table's placeholder
for a year a person was not PEO.
"""
import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_governance_facts as reader

READING = "docs/evidence/issue47_history/content-acceptance/governance-read.json"
SOUTHWEST_PROXY = ("evidence/accession_materials/southwest_airlines_92380_000119312526127237/"
                   "d121727ddef14a.htm")
YEAR_2025 = ("2025-01-01", "2025-12-31")


def _committed():
    return json.loads((ROOT / READING).read_text(encoding="utf-8"))["per_position"]


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_governance_modules(self):
        tree = ast.parse((ROOT / "tools/read_governance_facts.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                # "from vnext import x" names the module in its alias.
                imported.add(node.module)
                imported.update(node.module + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("governance_signals", "historical_governance_results",
                             "historical_governance_input", "normal_governance_input"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class ThePlaceholderIsReadAsWhatTheTableSaysItIsTest(unittest.TestCase):

    def setUp(self):
        raw = (ROOT / SOUTHWEST_PROXY).read_text(encoding="utf-8-sig", errors="replace")
        self.totals = reader.peo_totals(raw, reader.contexts_of(raw))

    def test_the_dash_is_zero_and_it_is_there(self):
        dashes = [t for t in self.totals if t["key"] == YEAR_2025 and t["placeholder"]]
        self.assertTrue(dashes)
        self.assertEqual({0}, {t["value"] for t in dashes})

    def test_a_dash_for_a_person_paid_as_peo_in_other_years_is_set_aside(self):
        kept, set_aside = reader.peo_totals_for(self.totals, YEAR_2025)
        self.assertEqual([16587882], sorted({int(t["value"]) for t in kept}))
        self.assertEqual([{"members": ["luv:GaryC.KellyMember"], "shown": "—",
                           "same_person_paid_as_peo_in": ["2021", "2022"]}], set_aside)

    def test_a_dash_for_a_person_the_table_never_pays_still_counts(self):
        never_paid = [{**t, "members": ["x:NeverPaidMember"]} for t in self.totals
                      if t["key"] == YEAR_2025 and t["placeholder"]]
        others = [t for t in self.totals if t["members"] != ["luv:GaryC.KellyMember"]]
        kept, set_aside = reader.peo_totals_for(others + never_paid, YEAR_2025)
        self.assertEqual([], set_aside)
        self.assertEqual({0, 16587882}, {int(t["value"]) for t in kept})


class TheCommittedReadingRederivesTest(unittest.TestCase):

    def test_every_position(self):
        for label, row in _committed().items():
            read_by = row["C04"]["eight_k_window_read_by"]
            items = None if read_by is None else json.loads((ROOT / read_by[0]).read_text(
                encoding="utf-8"))["per_position"][label]["filings"]["filing_date"]
            entry = reader.read_case(
                company_id=row["company_id"], label=label,
                period={"period_start": row["period"][0], "period_end": row["period"][1]},
                cik=row["cik"], source_document=row["target_document"],
                selection={"prior_filing": row["prior_filing"]},
                published={"C03": row["C03"]["published"], "C04": row["C04"]["published"]},
                event_items=items)
            with self.subTest(label):
                for metric in ("C03", "C04"):
                    self.assertEqual({k: v for k, v in row[metric].items()
                                      if k not in ("checked_identity", "eight_k_window_read_by")},
                                     entry[metric])

    def test_a_window_no_reading_read_is_not_a_window_without_item_4_01(self):
        """Salesforce FY2026's window is read only by the batch's event reading."""
        default = json.loads((ROOT / reader.EVENTS).read_text(encoding="utf-8"))["per_position"]
        self.assertNotIn("salesforce-2026", default)
        self.assertEqual((None, None), reader.window_items(events={reader.EVENTS: default},
                                                           label="salesforce-2026"))
        row = _committed()["salesforce-2026"]
        entry = reader.read_case(
            company_id=row["company_id"], label="salesforce-2026",
            period={"period_start": row["period"][0], "period_end": row["period"][1]},
            cik=row["cik"], source_document=row["target_document"],
            selection={"prior_filing": row["prior_filing"]},
            published={"C03": None, "C04": "0"}, event_items=None)
        self.assertEqual((None, "THE_8K_WINDOW_WAS_NOT_READ", "NOT_READ"),
                         (entry["C04"]["read"], entry["C04"]["why_not_read"],
                          entry["C04"]["verdict"]))
        # The same firm in both years is not enough on its own.
        self.assertEqual(entry["C04"]["auditor_named_in_the_target_filing"],
                         entry["C04"]["auditor_named_in_the_previous_years_filing"])

    def test_two_readings_of_one_window_must_name_the_same_filings(self):
        rows = {"x": {"filings": {"filing_date": [{"accession": "a", "items": ["2.02"]}]}}}
        other = {"x": {"filings": {"filing_date": [{"accession": "a", "items": ["4.01"]}]}}}
        self.assertEqual((["one.json", "two.json"], rows["x"]["filings"]["filing_date"]),
                         reader.window_items(events={"one.json": rows, "two.json": rows},
                                             label="x"))
        with self.assertRaisesRegex(SystemExit, "EVENT_READINGS_DISAGREE_ON_A_WINDOW"):
            reader.window_items(events={"one.json": rows, "two.json": other}, label="x")

    def test_a_restored_root_reading_rederives_from_the_bytes_it_recorded(self):
        """C04 over the export: this year's 10-K and last year's instance, by path.

        Every restored-root reading, each with the metrics it says it read; C03
        is read in one of them, from the checkout's proxy the result names.
        """
        from tools.acceptance_readings import GOVERNANCE_RESTORED_ROOT_READINGS
        read_from = 0
        metrics_read = {}
        for path in GOVERNANCE_RESTORED_ROOT_READINGS:
            body = json.loads((ROOT / path).read_text(encoding="utf-8"))
            metrics_read[path] = tuple(body["metrics_read"])
            read_from += self._rederive(body)
        self.assertEqual({("C04",), ("C03", "C04")}, set(metrics_read.values()))
        # Most previous years were saved only by the acquisition.
        self.assertGreater(read_from, 0)

    def _rederive(self, body):
        from tools.acceptance_readings import saved_bytes
        metrics = tuple(body["metrics_read"])
        read_from = 0
        for label, row in body["per_position"].items():
            read_by = row["C04"]["eight_k_window_read_by"]
            items = None if read_by is None else json.loads((ROOT / read_by[0]).read_text(
                encoding="utf-8"))["per_position"][label]["filings"]["filing_date"]
            recorded = row["C04"]["previous_year_read_from"]

            def text(relative):
                return saved_bytes(repo_root=ROOT, relative=relative).decode(
                    "utf-8-sig", errors="replace")

            def names(**_):
                return ((reader.text_fact(text(recorded), "dei:AuditorName"), recorded)
                        if recorded else ([], None))
            read_from += bool(recorded and recorded.startswith("evidence/request_attempts/"))
            entry = reader.read_case(
                company_id=row["company_id"], label=label,
                period={"period_start": row["period"][0], "period_end": row["period"][1]},
                cik=row["cik"], source_document=row["target_document"],
                selection={"prior_filing": row["prior_filing"]},
                published={"C03": row["C03"]["published"], "C04": row["C04"]["published"]},
                event_items=items, metrics=metrics, read_text=text, auditor_names=names)
            if "C03" in metrics:
                bound = row["C03"].get("checked_identity", {}).get("filings", [])
                reader.limit_c03_to_the_proxies_the_result_names(
                    row=entry["C03"], result_filings=set(bound))
            with self.subTest(label):
                for metric in ("C03", "C04"):
                    self.assertEqual({k: v for k, v in row[metric].items()
                                      if k not in ("checked_identity", "eight_k_window_read_by")},
                                     entry[metric])
        return read_from

    def test_c03_over_a_restored_root_stands_only_on_the_proxies_the_result_names(self):
        """A later proxy reporting an older year is not this reading's to give."""
        from tools.acceptance_readings import GOVERNANCE_JPMORGAN_2025
        row = json.loads((ROOT / GOVERNANCE_JPMORGAN_2025).read_text(encoding="utf-8"))[
            "per_position"]["jpmorgan-2025"]["C03"]
        self.assertEqual(("MATCH", []), (row["verdict"], row["proxies_the_result_does_not_name"]))
        limited = reader.limit_c03_to_the_proxies_the_result_names(
            row={k: v for k, v in row.items() if k != "checked_identity"}, result_filings=set())
        self.assertEqual((None, "NOT_READ", "A_PROXY_THE_RESULT_DOES_NOT_NAME_REPORTS_THE_PERIOD"),
                         (limited["read"], limited["verdict"], limited["why_not_read"]))

    def test_the_ledger_s_latest_copy_must_have_its_recorded_digest(self):
        import csv
        import hashlib
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence").mkdir()
            body = b'<dei:AuditorName contextRef="c">FIRM LLP</dei:AuditorName>'
            (root / "evidence/x_htm.xml").write_bytes(body)
            url = "https://www.sec.gov/Archives/edgar/data/1/000000000122000001/x_htm.xml"
            row = {"method": "GET", "source_url": url, "status_code": "200", "error": "",
                   "repo_relative_path": "evidence/x_htm.xml",
                   "content_sha256": hashlib.sha256(body).hexdigest()}
            self.assertEqual((["FIRM LLP"], "evidence/x_htm.xml"),
                             reader._auditor_names_in_accession(
                                 cik="1", accession="0000000001-22-000001", primary="x.htm",
                                 root=root, rows=[row]))
            # A failed latest request is not read around.
            self.assertEqual(([], None), reader._auditor_names_in_accession(
                cik="1", accession="0000000001-22-000001", primary="x.htm", root=root,
                rows=[row, {**row, "status_code": "503"}]))
            with self.assertRaisesRegex(SystemExit, "SAVED_BYTES_DIFFER_FROM_THE_LEDGER"):
                reader._auditor_names_in_accession(
                    cik="1", accession="0000000001-22-000001", primary="x.htm", root=root,
                    rows=[{**row, "content_sha256": "0" * 64}])

    def test_every_recorded_identity_was_recorded_when_the_reading_was_made(self):
        for label, row in _committed().items():
            for metric in ("C03", "C04"):
                if row[metric]["published"] is None:
                    continue
                with self.subTest(label=label, metric=metric):
                    self.assertEqual("RECORDED_AT_READING_TIME",
                                     row[metric]["checked_identity"]["established_by"])


if __name__ == "__main__":
    unittest.main()
