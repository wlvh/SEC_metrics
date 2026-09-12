"""Real-source NIM relationships and same-value semantic counterexamples."""

import hashlib
import unittest

from tests.vnext.test_financial_candidates import no_answers_or_network
from tests.vnext.test_financial_duration import CITI, JPM, ROOT
from vnext.composite_scope import index_source_structure
from vnext.financial_candidates import inspect_nim_candidate_evidence
from vnext.financial_relationships import FinancialRelationshipError, inspect_nim_relationships, inspect_nonaccrual_loan_ratio
from vnext.normal_annual_input import NormalAnnualInputError


PERIOD = {"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"}


class FinancialRelationshipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {"primary": JPM.read_bytes(), "alternate": CITI.read_bytes()}
        cls.actual = {key: cls.evaluate(source, "19617" if key == "primary" else "831001")
                      for key, source in cls.sources.items()}
        cls.primary_relation = cls.actual["primary"]["relations"][0]
        cls.primary_index = index_source_structure(source_bytes=cls.sources["primary"])

    @staticmethod
    def evaluate(source, cik="19617", period=None):
        with no_answers_or_network():
            return inspect_nim_relationships(
                repo_root=ROOT, source_bytes=source,
                expected_source_sha256=hashlib.sha256(source).hexdigest(),
                expected_cik=cik, target_period=period or PERIOD,
            )

    def changed_table(self, transform):
        # Locate the test mutation from newly generated evidence, not an input
        # table number supplied to the discovery/runtime implementation.
        order = int(self.primary_relation["rate_locator"]["table_id"].split("_")[1]) - 1
        span = self.primary_index["tables"][order]
        source = self.sources["primary"]
        raw = source[span["start_byte"]:span["end_byte"]]
        changed = transform(raw)
        self.assertTrue(changed != raw, "TEST_ONLY transformation did not change source")
        return source[:span["start_byte"]] + changed + source[span["end_byte"]:]

    def test_two_original_sources_reconstruct_named_roles_and_keep_disclosed_rate(self):
        expected = {"primary": ("0.025", "95868000000", "3834359000000"),
                    "alternate": ("0.0247", "59898000000", "2426751000000")}
        for key, values in expected.items():
            with self.subTest(source=key):
                result = self.actual[key]
                self.assertEqual("RELATIONSHIP_PROVEN", result["status"])
                relation = result["relations"][0]
                self.assertEqual(values[0], relation["rate_check"]["disclosed_ratio"])
                self.assertEqual(values[1], relation["source_roles"]["managed_numerator"]["canonical_value"])
                self.assertEqual(values[2], relation["source_roles"]["denominator"]["canonical_value"])
                self.assertEqual(2, relation["rate_check"]["source_display_decimal_places"])
                self.assertEqual("NOT_EVALUATED", result["native_evidence_status"])
                self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, result["calls"])
                self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", result["semantic_status"])
                self.assertEqual("SOURCE_WITNESSED_WHOLE_ISSUER", result["whole_issuer_scope_status"])

    def test_nim_arithmetic_does_not_substitute_for_consolidated_subject_definition(self):
        for key, cik in (("primary", "19617"), ("alternate", "831001")):
            source = self.sources[key]
            definitions = self.actual[key]["whole_issuer_scope_evidence"][0]["issuer_definitions"]
            for definition in sorted(definitions, key=lambda d: d["definition"]["start_byte"], reverse=True):
                span = definition["definition"]
                original = source[span["start_byte"]:span["end_byte"]]
                changed = original.replace(b"subsidiaries", b"selected affiliates")
                self.assertTrue(original != changed)
                source = source[:span["start_byte"]] + changed + source[span["end_byte"]:]
            result = self.evaluate(source, cik)
            self.assertEqual("RELATIONSHIP_PROVEN", result["status"])
            self.assertEqual("UNRESOLVED", result["semantic_status"])

    def test_unknown_same_named_nim_is_retained_beside_the_valid_source_relationship(self):
        extra = (b"<table><tr><td>Year ended December 31</td><td>2025</td></tr>"
                 b"<tr><td>Adjusted net interest margin</td><td>2.50</td><td>%</td></tr></table>")
        result = self.evaluate(self.sources["primary"].replace(b"</body>", extra + b"</body>"))
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual("UNRESOLVED", result["semantic_status"])
        self.assertEqual(1, len(result["relations"]))
        self.assertTrue(any(c["disposition"] == "SAME_NAMED_NIM_CANDIDATE_UNRESOLVED" for c in result["same_named_rate_census"]))

    def test_wrong_denominator_name_is_rejected_even_with_unchanged_values(self):
        source = self.changed_table(lambda raw: raw.replace(
            b"Average interest-earning assets", b"Average total assets"))
        result = self.evaluate(source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual([], result["relations"])

    def test_reported_tax_basis_cannot_be_relabelled_managed_by_equal_arithmetic(self):
        label = self.primary_relation["role_labels"]["managed_numerator"]["raw_text"].strip().encode()
        source = self.changed_table(lambda raw: raw.replace(label, b"Net interest income - reported"))
        self.assertEqual([], self.evaluate(source)["relations"])
        managed = self.primary_relation["source_roles"]["managed_numerator"]["locator"]["text"].encode()
        reported = self.primary_relation["source_roles"]["reported_numerator"]["locator"]["text"].encode()
        source = self.changed_table(lambda raw: raw.replace(managed, reported))
        result = self.evaluate(source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIn("REPORTED_TO_FTE_BRIDGE_CONFLICT", [r["reason"] for r in result["rejected_candidates"]])

    def test_wrong_year_cannot_reuse_the_same_numeric_relationship(self):
        source = self.changed_table(lambda raw: raw.replace(b">2025<", b">2024<"))
        result = self.evaluate(source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual([], result["relations"])

    def test_same_values_under_different_business_name_are_not_a_nim(self):
        source = self.changed_table(lambda raw: raw.replace(
            b"Net yield on average interest-earning assets", b"Fee yield on average interest-earning assets"))
        result = self.evaluate(source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual([], result["relations"])

    def test_changed_currency_and_claimed_precision_are_checked_from_source(self):
        source = self.changed_table(lambda raw: raw.replace(b"(in millions,", b"(in millions of euros,"))
        self.assertEqual([], self.evaluate(source)["relations"])
        display = self.primary_relation["rate_locator"]["text"].encode()
        source = self.changed_table(lambda raw: raw.replace(display, display + b"00"))
        result = self.evaluate(source)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIn("DISCLOSED_RATE_RELATIONSHIP_CONFLICT", [r["reason"] for r in result["rejected_candidates"]])

    def test_novel_consistent_values_work_without_any_reference_answer(self):
        mapping = {role: self.primary_relation["source_roles"][role]["locator"]["text"].encode()
                   for role in ("reported_numerator", "fte_adjustment", "managed_numerator", "denominator")}

        def change(raw):
            for role, value in {"reported_numerator": b"20", "fte_adjustment": b"5",
                                "managed_numerator": b"25", "denominator": b"1,000"}.items():
                raw = raw.replace(mapping[role], value)
            return raw

        result = self.evaluate(self.changed_table(change))
        self.assertEqual("RELATIONSHIP_PROVEN", result["status"])
        self.assertEqual("25000000", result["relations"][0]["source_roles"]["managed_numerator"]["canonical_value"])

    def test_explicit_formula_and_annual_named_subject_are_required(self):
        source = self.sources["alternate"]
        relation = self.actual["alternate"]["relations"][0]
        definition = relation["formula_evidence"]["definition"]
        raw = source[definition["start_byte"]:definition["end_byte"]]
        changed = raw.replace(b"average interest-earning assets", b"average total assets")
        self.assertTrue(raw != changed)
        result = self.evaluate(source[:definition["start_byte"]] + changed + source[definition["end_byte"]:], "831001")
        self.assertEqual("UNRESOLVED", result["status"])
        narrative = relation["source_annual_narrative"]
        raw = source[narrative["start_byte"]:narrative["end_byte"]]
        changed = raw.replace(b"Citi", b"A separate business segment", 1)
        self.assertTrue(raw != changed)
        result = self.evaluate(source[:narrative["start_byte"]] + changed + source[narrative["end_byte"]:], "831001")
        self.assertEqual("UNRESOLVED", result["status"])

    def test_same_rate_in_annual_prose_cannot_erase_a_row_linked_quarter(self):
        source = self.sources["alternate"]
        note = self.actual["alternate"]["relations"][0]["formula_evidence"]["tax_basis_notes"][0]
        raw = source[note["start_byte"]:note["end_byte"]]
        changed = raw.replace(b"NIM reflects TEGU", b"NIM reflects TEGU for the fourth quarter")
        self.assertTrue(raw != changed)
        result = self.evaluate(source[:note["start_byte"]] + changed + source[note["end_byte"]:], "831001")
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual([], result["relations"])

    def test_source_subject_and_requested_period_are_native_dei_bound(self):
        with self.assertRaises(NormalAnnualInputError):
            self.evaluate(self.sources["primary"], "1")
        with self.assertRaisesRegex(FinancialRelationshipError, "SOURCE_FISCAL_PERIOD_DIFFERS"):
            self.evaluate(self.sources["primary"], period={**PERIOD, "period_start": "2025-10-01"})

    def test_discovery_and_relationship_bind_the_same_automatically_found_cell(self):
        for key, cik in (("primary", "19617"), ("alternate", "831001")):
            source = self.sources[key]
            with no_answers_or_network(), self.subTest(source=key):
                report = inspect_nim_candidate_evidence(
                    repo_root=ROOT, source_bytes=source,
                    expected_source_sha256=hashlib.sha256(source).hexdigest(),
                    expected_cik=cik, target_period=PERIOD,
                )
            self.assertEqual("RELATIONSHIP_BOUND_TO_DISCOVERED_CANDIDATE", report["status"])
            self.assertEqual(1, len(report["matched_candidate_ids"]))
            self.assertEqual("NOT_EVALUATED", report["native_evidence_status"])
            self.assertFalse(report["auto_execution_eligible"])


class NonaccrualLoanRatioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = JPM.read_bytes()
        cls.structure = index_source_structure(source_bytes=cls.raw)
        cls.actual = cls.evaluate(cls.raw)

    @staticmethod
    def evaluate(raw):
        with no_answers_or_network():
            return inspect_nonaccrual_loan_ratio(repo_root=ROOT, source_bytes=raw,
                expected_source_sha256=hashlib.sha256(raw).hexdigest(), expected_cik="19617", target_period=PERIOD)

    def changed_table(self, transform):
        order = int(self.actual["selected"][0]["locator"]["table_id"].split("_")[1]) - 1
        span = self.structure["tables"][order]
        raw = self.raw[span["start_byte"]:span["end_byte"]]
        changed = transform(raw)
        self.assertNotEqual(raw, changed)
        return self.raw[:span["start_byte"]] + changed + self.raw[span["end_byte"]:]

    def test_original_all_candidate_census_proves_one_disclosed_firmwide_ratio(self):
        result = self.actual
        self.assertEqual("SINGLE_SOURCE_SEMANTIC_FACT", result["status"])
        self.assertEqual("0.0066", result["value"])
        self.assertEqual(23, len(result["candidate_census"]))
        self.assertEqual(6, sum(c["disposition"] == "OTHER_REPORTED_BUSINESS_SEGMENT" for c in result["candidate_census"]))
        self.assertEqual(1, len(result["selected"]))
        selected = result["selected"][0]
        self.assertEqual("9857000000", selected["source_roles"]["numerator"]["canonical_value"])
        self.assertEqual("1493429000000", selected["source_roles"]["denominator"]["canonical_value"])
        self.assertTrue(selected["rate_check"]["consistent"])
        self.assertTrue(selected["rate_check"]["result_value_remains_source_disclosed"])
        self.assertEqual("2025-12-31", selected["measurement_time"]["as_of_date"])
        self.assertEqual("REQUIRES_RECOMPUTED_SOURCE_SET_ROUTE", result["structured_route_status"])

    def test_wrong_denominator_measure_and_changed_denominator_value_both_fail(self):
        for before, after in [(b"Total loans", b"Total assets"), (b"1,493,429", b"1,000")]:
            with self.subTest(after=after):
                self.assertEqual("UNRESOLVED", self.evaluate(self.changed_table(lambda raw: raw.replace(before, after)))["status"])

    def test_same_values_under_retained_loan_or_asset_ratio_names_are_not_full_loan_ratio(self):
        for before, after in [(b"total loans outstanding", b"total retained loans outstanding"),
                              (b"Firmwide nonaccrual loans", b"Firmwide nonperforming assets")]:
            with self.subTest(after=after):
                result = self.evaluate(self.changed_table(lambda raw: raw.replace(before, after)))
                self.assertEqual("UNRESOLVED", result["status"])
                self.assertIsNone(result["value"])

    def test_wrong_instant_percent_unit_and_currency_scale_do_not_reuse_the_ratio(self):
        for before, after in [(b"December 31,", b"June 30,"), (b">%<", b">$<"),
                              (b"in millions,", b"in millions of euros,"), (b"in millions,", b"EUR in millions,")]:
            with self.subTest(after=after):
                result = self.evaluate(self.changed_table(lambda raw: raw.replace(before, after)))
                self.assertEqual("UNRESOLVED", result["status"])

    def test_unknown_same_name_competitor_blocks_an_otherwise_valid_ratio(self):
        extra = (b"<table><tr><td>December 31, (in millions, except ratios)</td><td>2025</td></tr>"
                 b"<tr><td>Firmwide nonperforming loan ratio</td><td>0.66</td><td>%</td></tr></table>")
        result = self.evaluate(self.raw.replace(b"</body>", extra + b"</body>"))
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertEqual(1, len(result["selected"]))
        self.assertTrue(result["unresolved"])

    def test_segment_declaration_conflict_cannot_silently_drop_segment_candidates(self):
        first = next(c for c in self.actual["candidate_census"] if c["disposition"] == "OTHER_REPORTED_BUSINESS_SEGMENT")
        span = first["source_scope_evidence"]["segment_definition"]["consistent_source_definitions"][0]
        before = self.raw[span["start_byte"]:span["end_byte"]]
        after = before.replace(b"Commercial &amp; Investment Bank", b"Different Commercial Segment")
        if after == before:
            after = before.replace(b"Commercial & Investment Bank", b"Different Commercial Segment")
        self.assertNotEqual(before, after)
        changed = self.raw[:span["start_byte"]] + after + self.raw[span["end_byte"]:]
        result = self.evaluate(changed)
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertTrue(any(c["label"]["text"].startswith("Nonaccrual loans") for c in result["unresolved"]))


if __name__ == "__main__":
    unittest.main()
