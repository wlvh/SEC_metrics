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
        self.actual_configuration = update._configuration
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

    def run_control(self, year, metric="B10", processing_files=()):
        with patch.object(update, "save_calculated_case", side_effect=self.save_control):
            return update.run_once(state_root=self.root / metric, source_root=ROOT,
                company_id="marriott_international", metric_id=metric,
                fiscal_year=year, case_factory=self.factory,
                processing_files=processing_files)

    def test_historical_d01_shared_dependency_changes_reprocess_then_reuse(self):
        from vnext.historical_risk_heading_case import PROCESSING_FILES
        actual_hash = update.sha256_file
        # Only the digest is changed in memory. The source/code tree is never
        # edited; these state substitutes are not financial source results.
        for year, name in enumerate(('scope_contract', 'states', 'text_results_v2'), 2021):
            with self.subTest(module=name):
                self.forbid_factory = False
                first = self.run_control(year, 'D01', PROCESSING_FILES)
                count = len(self.factory_calls)
                self.forbid_factory = True
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE',
                    self.run_control(year, 'D01', PROCESSING_FILES)['status'])
                self.assertEqual(count, len(self.factory_calls))
                target = ROOT / ('scripts/vnext/' + name + '.py')
                def changed_hash(*, path):
                    return 'constructed-d01-dependency-change' if path == target else actual_hash(path=path)
                self.forbid_factory = False
                with patch.object(update, 'sha256_file', side_effect=changed_hash):
                    changed = self.run_control(year, 'D01', PROCESSING_FILES)
                    self.assertEqual('CANDIDATE_READY', changed['status'])
                    self.assertTrue(changed['calculation_performed'])
                    self.assertEqual(count + 1, len(self.factory_calls))
                    self.assertNotEqual(first['version'], changed['version'])
                    self.forbid_factory = True
                    repeat = self.run_control(year, 'D01', PROCESSING_FILES)
                    self.assertEqual('NO_SOURCE_CONTENT_CHANGE', repeat['status'])
                    self.assertEqual(changed['version'], repeat['version'])
                self.assertEqual(count + 1, len(self.factory_calls))

    def period_root(self, year, metric="B10"):
        return self.root.resolve() / metric / "periods" / ("FY" + str(year))

    def test_range_requirement_version_reprocesses_only_income_consumers(self):
        from vnext import historical_statement_cases as statement
        target = ROOT / 'scripts/vnext/normal_source_requirements.py'
        original_hash = update.sha256_file
        def changed_hash(*, path):
            return 'CONSTRUCTED_RANGE_REQUIREMENT_VERSION_CHANGE' if path == target else original_hash(path=path)
        groups = (('B01', statement.INCOME_PROCESSING_FILES, True),
                  ('B02', statement.PAIRED_REVENUE_PROCESSING_FILES, True),
                  ('B04', statement.PROCESSING_FILES, False),
                  ('B05', statement.PROCESSING_FILES, False),
                  ('B07', statement.PROCESSING_FILES, False))
        # This is a constructed state control, not a financial amount or an
        # assertion that every metric uses the income-statement source rule.
        for metric, files, affected in groups:
            with self.subTest(metric=metric):
                # The company entry deduplicates income + range declarations.
                files = tuple(dict.fromkeys(files))
                self.forbid_factory = False
                first = self.run_control(2024, metric, files)
                count = len(self.factory_calls)
                self.forbid_factory = True
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE', self.run_control(2024, metric, files)['status'])
                with patch.object(update, 'sha256_file', side_effect=changed_hash):
                    self.forbid_factory = not affected
                    changed = self.run_control(2024, metric, files)
                    self.assertEqual(count + int(affected), len(self.factory_calls))
                    self.assertEqual(affected, changed['calculation_performed'])
                    self.assertEqual('CANDIDATE_READY' if affected else 'NO_SOURCE_CONTENT_CHANGE', changed['status'])
                    self.assertEqual(affected, changed['version'] != first['version'])
                    self.forbid_factory = True
                    again = self.run_control(2024, metric, files)
                    self.assertEqual('NO_SOURCE_CONTENT_CHANGE', again['status'])
                    self.assertEqual(changed['version'], again['version'])
                self.assertEqual(count + int(affected), len(self.factory_calls))

    def test_statement_property_version_reprocesses_only_explicit_income_metrics(self):
        from vnext.historical_statement_cases import processing_files_for_statement_metric
        original_hash = update.sha256_file
        target = ROOT / 'scripts/vnext/statement_metric_amendment.py'
        def changed_hash(*, path):
            return 'CONSTRUCTED_STATEMENT_PROPERTY_VERSION_CHANGE' if path == target else original_hash(path=path)
        for metric in ('B04','B07','B05','B01'):
            files = processing_files_for_statement_metric(metric)
            self.forbid_factory = False
            first = self.run_control(2024,metric,files)
            count = len(self.factory_calls)
            with self.subTest(metric=metric),patch.object(update,'sha256_file',side_effect=changed_hash):
                self.forbid_factory = metric == 'B01'
                after = self.run_control(2024,metric,files)
                expected = metric != 'B01'
                self.assertEqual(expected,after['calculation_performed'])
                self.assertEqual(count + int(expected),len(self.factory_calls))
                self.assertEqual(expected,after['version'] != first['version'])
                self.forbid_factory = True
                repeat = self.run_control(2024,metric,files)
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE',repeat['status'])
                self.assertEqual(after['version'],repeat['version'])
            self.assertEqual(count + int(metric != 'B01'),len(self.factory_calls))

    def test_private_historical_dependencies_reprocess_then_reuse(self):
        from vnext import historical_geography_cases as geography, historical_b03_case as b03
        from vnext.historical_lodging_results import HISTORICAL_LODGING_PROCESSING_FILES
        original_hash=update.sha256_file
        groups=(('A13',geography.PROCESSING_FILES,('zero_ai_r2',)),
                ('B03',b03.PROCESSING_FILES,('r5_b06_scope','b06_disclosure','r5_b06_structured')),
                ('B10',HISTORICAL_LODGING_PROCESSING_FILES,('composite_scope',)),
                ('B11',HISTORICAL_LODGING_PROCESSING_FILES,('composite_scope',)))
        for metric,files,names in groups:
            for year,name in enumerate(names,2021):
                with self.subTest(metric=metric,module=name):
                    self.forbid_factory=False
                    first=self.run_control(year,metric,files)
                    count=len(self.factory_calls)
                    self.forbid_factory=True
                    self.assertEqual('NO_SOURCE_CONTENT_CHANGE',self.run_control(year,metric,files)['status'])
                    target=ROOT/('scripts/vnext/'+name+'.py')
                    def changed_hash(*,path):
                        return 'CONSTRUCTED_PRIVATE_HISTORY_DEPENDENCY_CHANGE' if path==target else original_hash(path=path)
                    self.forbid_factory=False
                    with patch.object(update,'sha256_file',side_effect=changed_hash):
                        changed=self.run_control(year,metric,files)
                        self.assertTrue(changed['calculation_performed'])
                        self.assertEqual(count+1,len(self.factory_calls))
                        self.assertNotEqual(first['version'],changed['version'])
                        self.forbid_factory=True
                        repeat=self.run_control(year,metric,files)
                        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',repeat['status'])
                        self.assertEqual(changed['version'],repeat['version'])
                    self.assertEqual(count+1,len(self.factory_calls))

    def test_average_scope_dependency_change_processes_once_then_reuses(self):
        from vnext.historical_average_risk_cases import PROCESSING_FILES
        original_hash=update.sha256_file
        target=ROOT/'scripts/vnext/scope_contract.py'
        # The saver and values remain explicit state controls, not bank facts.
        for metric in ('A03','A12'):
            with self.subTest(metric=metric):
                self.forbid_factory=False
                first=self.run_control(2021,metric,PROCESSING_FILES)
                count=len(self.factory_calls)
                self.forbid_factory=True
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE',
                    self.run_control(2021,metric,PROCESSING_FILES)['status'])
                self.assertEqual(count,len(self.factory_calls))
                def changed_hash(*,path):
                    return 'CONSTRUCTED_AVERAGE_SCOPE_CHANGE' if path==target else original_hash(path=path)
                self.forbid_factory=False
                with patch.object(update,'sha256_file',side_effect=changed_hash):
                    changed=self.run_control(2021,metric,PROCESSING_FILES)
                    self.assertEqual('CANDIDATE_READY',changed['status'])
                    self.assertEqual(count+1,len(self.factory_calls))
                    self.assertNotEqual(first['version'],changed['version'])
                    self.forbid_factory=True
                    repeat=self.run_control(2021,metric,PROCESSING_FILES)
                    self.assertEqual('NO_SOURCE_CONTENT_CHANGE',repeat['status'])
                    self.assertEqual(changed['version'],repeat['version'])
                self.assertEqual(count+1,len(self.factory_calls))

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

    def test_actual_selected_year_dependencies_ignore_unused_admission_code(self):
        """Constructed state control with the actual processing configuration."""
        actual_hash = update.sha256_file
        self.outcomes[2025, "B11"] = "WITHHELD"
        with patch.object(update, "_configuration", side_effect=self.actual_configuration):
            initial = [self.run_control(2024), self.run_control(2025, "B11")]
            self.forbid_factory = True
            def unused_change(*, path):
                return "constructed-unused-admission-change" if path == ROOT / (
                    "scripts/vnext/normal_source_authority.py") else actual_hash(path=path)
            with patch.object(update, "sha256_file", side_effect=unused_change):
                unchanged = [self.run_control(2024), self.run_control(2025, "B11")]
            self.assertEqual(["NO_SOURCE_CONTENT_CHANGE", "PREVIOUS_INPUT_WITHHELD"],
                             [r["status"] for r in unchanged])
            self.assertEqual([r["version"] for r in initial],
                             [r["version"] for r in unchanged])
            self.forbid_factory = False
            def period_change(*, path):
                return "constructed-used-period-change" if path == ROOT / (
                    "scripts/vnext/normal_annual_input.py") else actual_hash(path=path)
            with patch.object(update, "sha256_file", side_effect=period_change):
                changed = [self.run_control(2024), self.run_control(2025, "B11")]
                self.assertEqual(["CANDIDATE_READY", "CANDIDATE_WITHHELD"],
                                 [r["status"] for r in changed])
                self.assertTrue(all(a["version"] != b["version"]
                                    for a, b in zip(initial, changed)))
                self.forbid_factory = True
                again = [self.run_control(2024), self.run_control(2025, "B11")]
                self.assertEqual([r["version"] for r in changed],
                                 [r["version"] for r in again])
            self.assertEqual(4, len(self.factory_calls))
