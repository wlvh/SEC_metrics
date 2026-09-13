"""Real native records to public schemas; no freezing or publication."""

import copy
import csv
import io
import json
import unittest

from tests.vnext.test_financial_candidates import no_answers_or_network
from tests.vnext.test_financial_duration import ROOT
from vnext.b06_guarded_result_v3 import prepare_guarded_b06_result
from vnext.calculator import _result_and_trace, withheld_metric_result
from vnext.canonical import sha256_file
from vnext.financial_results import resolve_ordinary_financial_metric
from vnext.normal_candidates import _structured_preparation
from vnext.normal_numeric_projection import NumericProjectionError, project_normal_numeric_records
from vnext.publication import METRIC_FIELDS, EVIDENCE_FIELDS
from vnext.specs import compile_spec_file


class NormalNumericProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {}
        with no_answers_or_network():
            for metric in ("A03", "A04", "A09", "A11", "A12", "A13"):
                item = resolve_ordinary_financial_metric(repo_root=ROOT, company_id="jpmorgan_chase", metric_id=metric)
                cls.cases[metric] = cls.case(item["company_id"], item["spec_path"], item["records"], item["result"],
                    item["filing_period"], item["input_binding"], {**item["selection"], "source_fact": item["source_fact"]})
            structural = resolve_ordinary_financial_metric(repo_root=ROOT, company_id="salesforce", metric_id="A03")
            cls.cases["STRUCTURAL"] = cls.case(structural["company_id"], structural["spec_path"], structural["records"],
                structural["result"], structural["filing_period"], structural["input_binding"], {})
            guard = prepare_guarded_b06_result(repo_root=ROOT, company_id="marriott_international")
            records = [*guard["source_records"], *guard["observations"], guard["trace"], guard["result"]]
            cls.cases["B06"] = cls.case("marriott_international", guard["spec_path"], records,
                guard["result"], guard["filing_period"], guard["input_binding"], {})
            for metric in ("C03", "C04"):
                prepared, path, resolution, _ = _structured_preparation(data_root=ROOT, company_id="marriott_international", metric_id=metric)
                obs = resolution.get("observations", [resolution["observation"]] if resolution.get("observation") else [])
                records = [*prepared["records"], *resolution.get("derived_assets", []), *obs, resolution["trace"], resolution["result"]]
                cls.cases[metric] = cls.case("marriott_international", path, records, resolution["result"],
                    prepared["input_binding"]["prepared_annual_input"]["table_input"]["target_period"], prepared["input_binding"], resolution["selection"])
                if metric == "C04":
                    cls.c04_arguments = prepared["resolver_inputs"]["c04"]["arguments"]

    @staticmethod
    def case(company, path, records, result, annual, binding, selection):
        return {"repo_root": ROOT, "manifest": {"run_id": "TEST_ONLY_unfrozen_native_records", "status": "OPEN",
                    "company_id": company, "source_references": [r for r in records if r["record_type"] == "SOURCE_REFERENCE"],
                    "spec_file_hashes": {path: sha256_file(path=ROOT / path)},
                    "target_period": {"fiscal_year": annual["fiscal_year"], "period_start": result["period_start"], "period_end": result["period_end"]}},
                "records": records, "compiled_spec": compile_spec_file(path=ROOT / path, dependency_specs={}),
                "input_binding": binding, "selection": selection}

    def render(self, name):
        with no_answers_or_network():
            return project_normal_numeric_records(**self.cases[name])

    def test_canonical_units_exact_values_and_measurement_periods_survive_csv(self):
        expected = {"A03": ("1.11", "ratio", "QUARTER"), "A04": ("0.025", "ratio", "ANNUAL"),
                    "A09": ("0.0066", "ratio", "INSTANT"), "A11": ("4791000000000", "USD", "INSTANT"),
                    "A12": ("40000000", "USD", "ANNUAL"), "A13": ("42758000000", "USD", "ANNUAL")}
        for metric, values in expected.items():
            with self.subTest(metric=metric):
                rendered = self.render(metric)
                row = rendered["row"]
                self.assertEqual(values, (row["value"], row["unit"], row["fiscal_period"]))
                self.assertEqual("", row["confidence"])
                self.assertEqual(set(METRIC_FIELDS), set(row))
                self.assertEqual([row], list(csv.DictReader(io.StringIO(rendered["files"]["metrics_matrix.csv"].decode()))))
                self.assertEqual(rendered["evidence"], list(csv.DictReader(io.StringIO(rendered["files"]["metric_evidence.csv"].decode()))))
                self.assertTrue(all(set(e) == set(EVIDENCE_FIELDS) for e in rendered["evidence"]))
                self.assertTrue(rendered["receipt"]["observation_ids"])
                self.assertTrue(rendered["receipt"]["supporting_source_references"])
                self.assertIn("selected_source_cells", rendered["evidence"][0]["context_or_dimension"])
        q = self.render("A03")["row"]
        self.assertEqual(("2025-10-01", "2025-12-31", "2025"), (q["period_start"], q["period_end"], q["fiscal_year"]))

    def test_compensation_dollars_and_auditor_flag_have_explicit_meaning_and_source_filing(self):
        comp, audit = self.render("C03"), self.render("C04")
        self.assertEqual(("22970926", "USD", "DEF 14A", "2026-03-27"), tuple(comp["row"][k] for k in ("value", "unit", "form", "filed_date")))
        self.assertIn("not compensation actually paid", comp["row"]["notes"])
        self.assertEqual(("0", "flag"), (audit["row"]["value"], audit["row"]["unit"]))
        self.assertIn("Neither is a probability", audit["row"]["notes"])
        self.assertEqual("", audit["evidence"][0]["value_raw"])

    def test_original_source_cells_and_fact_locators_remain_recoverable(self):
        from vnext.deterministic_router import parse_accession_xbrl_source
        from vnext.table_grid import _AllTablesParser, _expanded_table
        from vnext.resource_limits import RESOURCE_LIMITS
        from tests.vnext.test_financial_duration import JPM
        parser = _AllTablesParser()
        parser.feed(JPM.read_text())
        parser.close()
        tables = {}
        for metric in ("A03", "A04", "A09", "A11", "A12", "A13"):
            evidence = self.render(metric)["evidence"][0]
            self.assertEqual(sha256_file(path=ROOT / evidence["repo_relative_path"]), evidence["content_sha256"])
            cells = json.loads(evidence["context_or_dimension"])["selected_source_cells"]
            self.assertTrue(cells)
            self.assertTrue(evidence["value_raw"])
            for locator in cells:
                table_id = locator["table_id"]
                if table_id not in tables:
                    index = int(table_id.split("_")[-1])
                    tables[table_id], _ = _expanded_table(builder=parser.tables[index - 1],
                        remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                        remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
                table = tables[table_id]
                cell = table["rows"][locator["row_index"]]["cells"][locator["column_index"]]
                self.assertEqual(cell["raw_text"], locator["raw_text"])
                self.assertEqual(table["grid_sha256"], locator["grid_sha256"])
        for metric in ("C03", "B06"):
            evidence = self.render(metric)["evidence"][0]
            binding = json.loads(evidence["context_or_dimension"])["source_binding"]
            parsed = parse_accession_xbrl_source(raw_bytes=(ROOT / evidence["repo_relative_path"]).read_bytes())
            if metric == "C03":
                for locator in binding["fact_locators"]:
                    fact = parsed.facts[locator["ordinal"] - 1]
                    self.assertEqual(locator["context_ref"], fact["context_ref"])
                    self.assertEqual(evidence["value_raw"], fact["text"])
            else:
                fact = parsed.facts[binding["xbrl_fact_ordinal"] - 1]
                self.assertEqual(binding["xbrl_context_ref"], fact["context_ref"])
                self.assertEqual(evidence["value_normalized"], fact["text"])

    def test_nonmeaningful_ratio_retains_only_real_equity_evidence(self):
        rendered = self.render("B06")
        self.assertEqual(("", "ratio", "NOT_MEANINGFUL", "INSTANT"), tuple(rendered["row"][k] for k in ("value", "unit", "status", "fiscal_period")))
        self.assertIn("DENOMINATOR_NONPOSITIVE", rendered["row"]["notes"])
        self.assertIn("Debt completeness: NOT_EVALUATED", rendered["row"]["notes"])
        self.assertEqual(1, len(rendered["evidence"]))
        self.assertEqual("USD", rendered["evidence"][0]["unit"])
        self.assertTrue(rendered["evidence"][0]["value_normalized"].startswith("-"))
        self.assertIn('"semantic_role": "equity"', rendered["evidence"][0]["context_or_dimension"])

    def test_nonmeaningful_note_cannot_be_assigned_to_another_spec_or_trace(self):
        case = copy.deepcopy(self.cases["B06"])
        target = next(r for r in case["records"] if r["record_type"] == "EXECUTION_TRACE")["calculation_target"]
        observation = next(r for r in case["records"] if r["record_type"] == "VERIFIED_OBSERVATION")
        path = "catalog/r5/B06_new_source_v2.md"
        case["compiled_spec"] = compile_spec_file(path=ROOT / path, dependency_specs={})
        case["manifest"]["spec_file_hashes"] = {path: sha256_file(path=ROOT / path)}
        result, trace = _result_and_trace(compiled_spec=case["compiled_spec"], target=target,
            applicability="APPLICABLE", quality="NOT_MEANINGFUL", publication="PUBLISHED",
            reason_code="DENOMINATOR_NONPOSITIVE", value=None, result_unit=None,
            trace_steps=[], input_ids=[observation["observation_id"]])
        case["records"] = [r for r in case["records"] if r["record_type"] not in {"METRIC_RESULT", "EXECUTION_TRACE"}] + [result, trace]
        with self.assertRaisesRegex(NumericProjectionError, "NOT_MEANINGFUL_GUARD_UNSUPPORTED"):
            project_normal_numeric_records(**case)

    def test_c04_missing_coverage_retains_reason_and_source_scope_without_observation(self):
        from vnext.governance_signals import resolve_c04
        case = copy.deepcopy(self.cases["C04"])
        # TEST_ONLY source omission reuses actual reports; it is not a claim
        # that the installed ordinary input lacks its event coverage.
        args = {**self.c04_arguments, "event_input": None, "compiled_spec": case["compiled_spec"]}
        with no_answers_or_network():
            withheld = resolve_c04(**args)
        self.assertIsNone(withheld["observation"])
        self.assertEqual("C04_EVENT_COVERAGE_REQUIRED", withheld["result"]["reason_code"])
        case["records"] = [r for r in case["records"] if r["record_type"] in {"RAW_BLOB", "SOURCE_REFERENCE"}] + [withheld["trace"], withheld["result"]]
        case["selection"] = withheld["selection"]
        rendered = project_normal_numeric_records(**case)
        self.assertEqual(("", "WITHHELD"), (rendered["row"]["value"], rendered["row"]["status"]))
        self.assertEqual([], rendered["evidence"])
        self.assertIn("C04_EVENT_COVERAGE_REQUIRED", rendered["row"]["notes"])
        context = json.loads(rendered["row"]["context_or_dimension"])
        self.assertEqual(withheld["selection"], context["resolution_details"])
        self.assertEqual([], context["resolution_details"]["event_source_sets"])
        self.assertTrue(context["resolution_details"]["current_filing_checks"])
        self.assertTrue(context["source_scope"])
        self.assertEqual(context["source_scope"], rendered["receipt"]["source_scope"])
        self.assertTrue(all(item["repo_relative_path"] and item["content_sha256"] for item in context["source_scope"]))

    def test_structural_and_withheld_states_never_gain_a_value(self):
        structural = self.render("STRUCTURAL")
        self.assertEqual(("", "N_A_STRUCTURAL", "STRUCTURAL"), tuple(structural["row"][k] for k in ("value", "status", "fiscal_period")))
        self.assertEqual([], structural["evidence"])
        # TEST_ONLY withholding uses the actual Spec/company/source records;
        # it is a rendering case, not a falsely claimed missing disclosure.
        case = copy.deepcopy(self.cases["A03"])
        old = next(r for r in case["records"] if r["record_type"] == "METRIC_RESULT")
        trace = next(r for r in case["records"] if r["record_type"] == "EXECUTION_TRACE")
        target = {k: trace["calculation_target"][k] for k in ("company_id", "period_start", "period_end", "scope", "scope_key")}
        result, trace = withheld_metric_result(compiled_spec=case["compiled_spec"], target=target, reason_code="TEST_ONLY_UNRESOLVED_SCOPE")
        case["records"] = [r for r in case["records"] if r["record_type"] in {"RAW_BLOB", "SOURCE_REFERENCE"}] + [trace, result]
        rendered = project_normal_numeric_records(**case)
        self.assertEqual(("", "WITHHELD", "TARGET_PERIOD"), tuple(rendered["row"][k] for k in ("value", "status", "fiscal_period")))
        self.assertIn("TEST_ONLY_UNRESOLVED_SCOPE", rendered["row"]["notes"])
        self.assertEqual([], rendered["evidence"])
        self.assertEqual(old["period_start"], rendered["row"]["period_start"])

    def test_presentation_does_not_mutate_executed_specs_or_claim_frozen_credit(self):
        case = copy.deepcopy(self.cases["A03"])
        before = copy.deepcopy(case["compiled_spec"])
        first = project_normal_numeric_records(**case)
        self.assertEqual(before, case["compiled_spec"])
        self.assertEqual(first, project_normal_numeric_records(**case))
        self.assertEqual("RECORDS_ONLY_RENDERING", first["receipt"]["status"])
        self.assertEqual("NOT_ASSERTED_BY_PURE_RENDERER", first["receipt"]["source_validation"])
        self.assertFalse(first["receipt"]["production_authorized"])
        case["manifest"]["status"] = "FROZEN"
        self.assertEqual("NOT_ASSERTED_BY_PURE_RENDERER", project_normal_numeric_records(**case)["receipt"]["source_validation"])
        case["compiled_spec"]["compiled"]["canonical_unit"] = "unknown_business_unit"
        with self.assertRaisesRegex(NumericProjectionError, "NUMERIC_UNIT_UNKNOWN_OR_CHANGED"):
            project_normal_numeric_records(**case)


if __name__ == "__main__":
    unittest.main()
