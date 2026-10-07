"""Historical state controls over the one public updater, not business results.

Source selection and saving are explicit small substitutes. Real Marriott
company/CSV checks are kept in the closeout's single verification record.
"""
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from tests.vnext import test_ordinary_current_update as control

ROOT = control.ROOT
update = control.update


class SelectedHistoryResultStateTest(TestCase):
    def setUp(self):
        control.CurrentUpdateTest.setUp(self)
        self.factory_calls = []
        self.outcomes = {}
        self.missing_years = set()
        self.forbid_factory = False

    def factory(self, *, repo_root, company_id, metric_id, fiscal_year):
        self.factory_calls.append((fiscal_year, metric_id))
        if self.forbid_factory:
            raise AssertionError("CONSTRUCTED_CONTROL_UNCHANGED_INPUT_MUST_NOT_CALCULATE")
        if fiscal_year in self.missing_years:
            class MissingYear(ValueError):
                category = "SOURCE_UNAVAILABLE"
            raise MissingYear("CONSTRUCTED_CONTROL_MISSING_YEAR")
        return {"target_period": {"fiscal_year": fiscal_year},
                "publication": self.outcomes.get((fiscal_year, metric_id), "PUBLISHED"),
                "constructed_state_control": True}

    def save_control(self, **kwargs):
        case = kwargs["case"]
        year = case["target_period"]["fiscal_year"]
        metric = kwargs["metric_id"]
        path = kwargs["output_root"]
        path.mkdir(parents=True)
        publication = case["publication"]
        value = {"manifest": {"company_id": "marriott_international",
                    "metric_id": metric, "source_proofs": [dict(self.proof)]},
                 "result": {"company_id": "marriott_international", "metric_id": metric,
                    "publication": publication, "period_end": str(year) + "-12-31",
                    "result_id": "CONSTRUCTED-CONTROL-" + path.name,
                    "value": "0.698" if publication == "PUBLISHED" else None,
                    "reason_code": "PASS" if publication == "PUBLISHED"
                        else "CONSTRUCTED_CONTROL_BUSINESS_WITHHELD"}}
        self.records[str(path)] = value
        return value

    def run_control(self, year, metric="B10"):
        with patch.object(update, "save_calculated_case", side_effect=self.save_control):
            return update.run_once(state_root=self.root / metric, source_root=ROOT,
                company_id="marriott_international", metric_id=metric,
                fiscal_year=year, case_factory=self.factory)

    def period_root(self, year, metric="B10"):
        return self.root.resolve() / metric / "periods" / ("FY" + str(year))

    def test_success_and_stable_withheld_reuse_in_distinct_historical_coordinates(self):
        self.outcomes[2025, "B11"] = "WITHHELD"
        first = self.run_control(2024)
        held = self.run_control(2025, "B11")
        self.assertEqual("CANDIDATE_READY", first["status"])
        self.assertEqual("CANDIDATE_WITHHELD", held["status"])
        counts = len(self.factory_calls)
        directories = sorted(str(p) for p in self.root.rglob("results/*") if p.is_dir())
        self.forbid_factory = True
        again = [self.run_control(2024), self.run_control(2025, "B11")]
        self.assertEqual(["NO_SOURCE_CONTENT_CHANGE", "PREVIOUS_INPUT_WITHHELD"],
                         [r["status"] for r in again])
        self.assertEqual("CONSTRUCTED_CONTROL_BUSINESS_WITHHELD", again[1]["result_reason_code"])
        self.assertEqual(counts, len(self.factory_calls))
        self.assertEqual(directories, sorted(str(p) for p in self.root.rglob("results/*") if p.is_dir()))

    def test_current_withheld_replaces_same_year_success_but_retains_old_version(self):
        first = self.run_control(2024)
        self.config["processing_version"] = "two"
        self.outcomes[2024, "B10"] = "WITHHELD"
        held = self.run_control(2024)
        self.assertEqual("CANDIDATE_WITHHELD", held["status"])
        pointer = json.loads((self.period_root(2024) / "completed-check.json").read_text())
        self.assertEqual(held["version"], pointer["version"])
        self.assertIsNone(self.records[str(self.period_root(2024) / "results" / pointer["version"])]["result"]["value"])
        self.assertEqual("0.698", self.records[str(self.period_root(2024) / "results" / first["version"])]["result"]["value"])
        self.assertEqual(first["version"], json.loads(
            (self.period_root(2024) / "current-result.json").read_text())["version"])
        count = len(self.factory_calls)
        self.assertEqual("PREVIOUS_INPUT_WITHHELD", self.run_control(2024)["status"])
        self.assertEqual(count, len(self.factory_calls))

    def test_dependency_source_and_processing_changes_reprocess_withheld_once(self):
        self.outcomes[2024, "B10"] = "WITHHELD"
        first = self.run_control(2024)
        self.census.append({"source_url": "constructed-new-dependency", "content_sha256": "b",
                            "status_code": "200", "error": ""})
        source_change = self.run_control(2024)
        self.assertNotEqual(first["version"], source_change["version"])
        count = len(self.factory_calls)
        self.assertEqual("PREVIOUS_INPUT_WITHHELD", self.run_control(2024)["status"])
        self.assertEqual(count, len(self.factory_calls))
        self.config["processing_version"] = "two"
        config_change = self.run_control(2024)
        self.assertNotEqual(source_change["version"], config_change["version"])
        count = len(self.factory_calls)
        self.assertEqual("PREVIOUS_INPUT_WITHHELD", self.run_control(2024)["status"])
        self.assertEqual(count, len(self.factory_calls))

    def test_missing_year_and_one_metric_failure_preserve_other_periods(self):
        self.run_control(2024)
        self.run_control(2025, "B11")
        pointers = {p: p.read_bytes() for p in self.root.rglob("current-result.json")}
        self.missing_years.add(2026)
        missing = self.run_control(2026)
        self.assertEqual("INPUT_OR_EXECUTION_FAILED", missing["status"])
        self.assertEqual("SOURCE_UNAVAILABLE", missing["error_category"])
        self.assertEqual(2026, missing["requested_fiscal_year"])
        with patch.object(update, "_current_sources", side_effect=ValueError("CONSTRUCTED_LOCAL_SOURCE_FAILURE")):
            failed = self.run_control(2024)
        self.assertEqual("INPUT_OR_EXECUTION_FAILED", failed["status"])
        self.assertTrue(all(p.read_bytes() == raw for p, raw in pointers.items()))

    def test_completed_withheld_recovers_pointer_without_recalculation(self):
        self.outcomes[2024, "B10"] = "WITHHELD"
        first = self.run_control(2024)
        pointer = self.period_root(2024) / "completed-check.json"
        self.assertTrue(pointer.is_file())
        pointer.unlink()  # Own tiny temporary state only; emulate interrupted commit.
        count = len(self.factory_calls)
        again = self.run_control(2024)
        self.assertEqual("PREVIOUS_INPUT_WITHHELD", again["status"])
        self.assertEqual(first["version"], json.loads(pointer.read_text())["version"])
        self.assertEqual(count, len(self.factory_calls))
