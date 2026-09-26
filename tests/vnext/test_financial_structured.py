"""Native SourceSet/inline-fact witnesses with no source-specific answers."""

import copy
import re
import unittest

from tests.vnext.test_financial_candidates import no_answers_or_network
from tests.vnext.test_financial_duration import ROOT
from vnext.canonical import content_hash, sha256_bytes
from vnext.composite_scope import index_source_structure
from vnext.deterministic_router import source_set_manifest as build_source_set
from vnext.financial_structured import (
    FinancialStructuredError, inspect_inline_financial_claims, prepare_saved_inline_source_set,
    inspect_ordinary_a09_source_fact,
)
from vnext.r4_structured_sources import build_pinned_fixture_source_set
from vnext.sources import source_reference_record


PERIOD = {"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"}


class _LazyFixture(dict):
    """Prepare only original fixtures actually used by the selected test."""
    def __init__(self, prepare):
        super().__init__()
        self.prepare = prepare

    def __missing__(self, key):
        value = self.prepare(key)
        self[key] = value
        return value


class FinancialStructuredTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def bundle(name):
            if name == "JPM":
                with no_answers_or_network():
                    ordinary = prepare_saved_inline_source_set(repo_root=ROOT, company_id="jpmorgan_chase")
                return {key: value for key, value in ordinary.items() if key != "prepared_input_id"}
            # Existing alternate acquisitions are provenance, never answers.
            source_id, cik = {"Citi": ("citigroup_fy2025_10k", "831001"),
                              "BAC": ("bank_of_america_fy2025_10k", "70858")}[name]
            manifest = build_pinned_fixture_source_set(repo_root=ROOT, source_id=source_id)
            return {"source_bytes": (ROOT / manifest["raw_blob"]["storage_uri"]).read_bytes(),
                "source_reference": manifest["source_reference"], "source_set_manifest": manifest,
                "expected_cik": cik, "target_period": PERIOD}
        cls.bundles = _LazyFixture(bundle)
        cls.actual = _LazyFixture(lambda key: cls.evaluate(cls.bundles[key[0]], key[1]))

    @staticmethod
    def evaluate(bundle, metric):
        with no_answers_or_network():
            return inspect_inline_financial_claims(repo_root=ROOT, metric_id=metric, **bundle)

    def counterfactual(self, name, changed):
        """TEST_ONLY rebind in-memory source objects, with no acquisition credit.

        This never edits saved bodies or ledgers and cannot be used by the
        ordinary saved-input entrypoint. It isolates semantic failures from
        the simpler stale-hash refusal.
        """
        original = self.bundles[name]
        self.assertTrue(changed != original["source_bytes"])
        result = copy.deepcopy(original)
        result["source_bytes"] = changed
        old_ref = result["source_reference"]
        raw = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=changed),
               "byte_length": len(changed), "media_type": "text/html", "storage_uri": "TEST_ONLY-counterfactual.html"}
        reference = source_reference_record(raw_blob=raw, **{key: old_ref[key] for key in (
            "company_id", "source_url", "accession", "document_name", "source_role", "request_attempt_id")})
        result["source_reference"] = reference
        manifest = result["source_set_manifest"]
        if manifest["record_type"] == "SOURCE_SET_MANIFEST":
            result["source_set_manifest"] = build_source_set(
                company_id=manifest["company_id"], source_role=manifest["source_role"],
                form_types=manifest["form_types"], fiscal_or_date_window=manifest["fiscal_or_date_window"],
                discovery_policy=manifest["discovery_policy"], inventory_source_reference=result["inventory_source_reference"],
                inventory_bytes=result["inventory_bytes"], ordered_source_references=[reference],
                cutoff_timestamp_or_pinned_submissions_attempt=manifest["cutoff_timestamp_or_pinned_submissions_attempt"])
        else:
            manifest["source_reference"] = reference
            manifest["raw_blob"] = raw
            manifest["ordered_source_reference_ids"] = [reference["source_reference_id"]]
            manifest["source_set_manifest_id"] = content_hash(value={key: value for key, value in manifest.items() if key != "source_set_manifest_id"})
        return result

    def test_real_normal_source_set_and_two_direct_international_totals(self):
        for name, expected in (("JPM", "42758000000"), ("Citi", "42295000000")):
            result = self.actual[(name, "A13")]
            self.assertEqual("STRUCTURED_PRIMARY_RESOLVED", result["outcome"])
            self.assertEqual(expected, result["value"])
            self.assertEqual("FROM_SAME_FACT_ORIGINAL_ROW_LABEL_NOT_MEMBER_SPELLING",
                             result["selected"][0]["source_witness"]["member_classification"])
            self.assertFalse(result["fallback_provider_authorized"])
            self.assertFalse(result["regional_sum_used"])
        self.assertEqual("NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET", self.actual[("JPM", "A13")]["source_set_scope"])
        self.assertIn("FIXTURE_ONLY", self.actual[("Citi", "A13")]["source_set_scope"])

    def test_ordinary_a09_rebuilds_native_ambiguity_before_proving_html_source_fact(self):
        with no_answers_or_network():
            result = inspect_ordinary_a09_source_fact(repo_root=ROOT, **self.bundles["JPM"])
        self.assertEqual("STRUCTURED_SOURCE_AMBIGUOUS", result["structured_primary"]["outcome"])
        self.assertEqual("NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET", result["structured_primary"]["source_set_scope"])
        self.assertEqual("HTML_FALLBACK_SOURCE_SEMANTIC_FACT", result["outcome"])
        self.assertEqual("0.0066", result["value"])
        self.assertEqual("EXPLICIT_DETERMINISTIC_FALLBACK_RULE_REQUIRED", result["ordinary_result_rule_status"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, result["calls"])

    def test_resolved_native_a09_is_not_replaced_by_html_fallback(self):
        from unittest.mock import patch
        bundle = self.bundles["BAC"]
        with no_answers_or_network(), patch("vnext.financial_relationships.inspect_nonaccrual_loan_ratio",
                                            side_effect=AssertionError("fallback must not run")):
            result = inspect_ordinary_a09_source_fact(repo_root=ROOT, **bundle)
        self.assertEqual("STRUCTURED_PRIMARY_RESOLVED", result["outcome"])
        self.assertEqual("0.0049", result["value"])
        self.assertIsNone(result["html_fallback"])

    def test_incomplete_source_set_cannot_supply_an_ambiguity_flag(self):
        changed = copy.deepcopy(self.bundles["JPM"])
        changed["inventory_bytes"] = None
        with self.assertRaisesRegex(FinancialStructuredError, "NORMAL_SOURCE_SET_INVENTORY_REQUIRED"), no_answers_or_network():
            inspect_ordinary_a09_source_fact(repo_root=ROOT, **changed)

    def test_single_country_is_excluded_by_its_actual_linked_detail_footnote(self):
        result = self.actual[("Citi", "A13")]
        details = [d for d in result["claim_dispositions"] if d["disposition"] == "COUNTRY_DETAIL_NOT_DIRECT_INTERNATIONAL_TOTAL"]
        self.assertEqual(1, len(details))
        self.assertIn("U.K.", details[0]["source_witness"]["original_country_detail_footnote"]["visible_text"])
        self.assertTrue(details[0]["source_witness"]["referencing_international_total_labels"])

    def test_native_tags_do_not_override_an_explicit_non_reported_table_declaration(self):
        original = self.bundles["JPM"]["source_bytes"]
        cell = self.actual[("JPM", "A13")]["selected"][0]["source_witness"]["table_cell"]
        table = index_source_structure(source_bytes=original)["tables"][int(cell["table_id"].split("_")[1]) - 1]
        negative = b"<div>The following table is for illustration only and contains hypothetical amounts, not reported international revenue.</div>"
        source = original[:table["start_byte"]] + negative + original[table["start_byte"]:]
        result = self.evaluate(self.counterfactual("JPM", source), "A13")
        self.assertEqual("STRUCTURED_SOURCE_CONFLICT", result["outcome"])
        self.assertIsNone(result["value"])
        self.assertTrue(result["source_conflicts"])
        self.assertFalse(result["fallback_plan_allowed_by_route"])
        unrelated = b"<div>The preceding example contains hypothetical amounts, not reported revenue. Models can use hypothetical assumptions.</div>"
        source = original[:table["start_byte"]] + unrelated + original[table["start_byte"]:]
        result = self.evaluate(self.counterfactual("JPM", source), "A13")
        self.assertEqual("STRUCTURED_PRIMARY_RESOLVED", result["outcome"])
        self.assertEqual("42758000000", result["value"])

    def test_opaque_member_rename_does_not_require_another_company_year_mapping(self):
        original = self.bundles["JPM"]["source_bytes"]
        changed = original.replace(b"jpm:TotalInternationalMember", b"jpm:OpaqueGeographyMember")
        result = self.evaluate(self.counterfactual("JPM", changed), "A13")
        self.assertEqual("STRUCTURED_PRIMARY_RESOLVED", result["outcome"])
        self.assertEqual("42758000000", result["value"])

    def test_value_and_native_unit_scale_do_not_substitute_for_geography_or_revenue_labels(self):
        original = self.bundles["JPM"]["source_bytes"]
        changed = original.replace(b"Total international", b"Total domestic")
        self.assertIsNone(self.evaluate(self.counterfactual("JPM", changed), "A13")["value"])
        definition = self.actual[("JPM", "A13")]["selected"][0]["source_witness"]["revenue_measure"]["definition"]
        raw = original[definition["start_byte"]:definition["end_byte"]]
        changed = raw.replace(b"net interest income", b"net income")
        result = self.evaluate(self.counterfactual("JPM", original[:definition["start_byte"]] + changed + original[definition["end_byte"]:]), "A13")
        self.assertEqual("STRUCTURED_IMPLEMENTATION_GAP", result["outcome"])
        self.assertIsNone(result["value"])

    def test_currency_id_named_usd_cannot_hide_a_different_declared_measure(self):
        original = self.bundles["JPM"]["source_bytes"]
        changed = original.replace(b">iso4217:USD<", b">iso4217:EUR<")
        result = self.evaluate(self.counterfactual("JPM", changed), "A13")
        self.assertIsNone(result["value"])

    def test_conflicting_native_scale_is_checked_against_the_original_table(self):
        original = self.bundles["JPM"]["source_bytes"]
        selected = self.actual[("JPM", "A13")]["selected"][0]["claim"]["locator"]["context_ref"].encode()
        # Only the direct target Revenue fact changes; metadata and source
        # table still say millions, so a newly hashed source cannot conceal it.
        pattern = rb'(<ix:nonFraction\b(?=[^>]*contextRef="' + selected + rb'")(?=[^>]*name="us-gaap:Revenues")[^>]*scale=")6("[^>]*>)'
        changed, count = re.subn(pattern, rb'\g<1>9\2', original)
        self.assertEqual(1, count)
        result = self.evaluate(self.counterfactual("JPM", changed), "A13")
        self.assertIn("NATIVE_FACT_VISIBLE_SCALE_CONFLICT", result["implementation_gaps"])
        self.assertIsNone(result["value"])

    def test_npl_native_route_has_real_positive_and_non_firmwide_source_fallback(self):
        positive = self.actual[("BAC", "A09")]
        self.assertEqual("STRUCTURED_PRIMARY_RESOLVED", positive["outcome"])
        self.assertEqual("0.0049", positive["value"])
        self.assertEqual("2025-12-31", positive["selected"][0]["claim"]["attributes"]["context"]["period_start"])
        unresolved = self.actual[("JPM", "A09")]
        self.assertEqual("STRUCTURED_SOURCE_AMBIGUOUS", unresolved["outcome"])
        self.assertTrue(unresolved["native_raw_fact_dispositions"])
        self.assertTrue(unresolved["fallback_plan_allowed_by_route"])
        self.assertFalse(unresolved["fallback_provider_authorized"])

    def test_accruing_past_due_same_value_does_not_acquire_npl_scope(self):
        original = self.bundles["BAC"]["source_bytes"]
        table_id = self.actual[("BAC", "A09")]["selected"][0]["source_witness"]["table_cell"]["table_id"]
        span = index_source_structure(source_bytes=original)["tables"][int(table_id.split("_")[1]) - 1]
        raw = original[span["start_byte"]:span["end_byte"]]
        changed_table = raw.replace(b"Nonperforming", b"Accruing past due")
        self.assertTrue(changed_table != raw)
        changed = original[:span["start_byte"]] + changed_table + original[span["end_byte"]:]
        result = self.evaluate(self.counterfactual("BAC", changed), "A09")
        self.assertEqual("STRUCTURED_IMPLEMENTATION_GAP", result["outcome"])
        self.assertIsNone(result["value"])

    def test_missing_inventory_or_stale_source_reference_cannot_pass(self):
        bundle = copy.deepcopy(self.bundles["JPM"])
        bundle.pop("inventory_bytes")
        with self.assertRaisesRegex(FinancialStructuredError, "INVENTORY_REQUIRED"):
            self.evaluate(bundle, "A13")
        bundle = copy.deepcopy(self.bundles["JPM"])
        bundle["source_bytes"] += b" "
        with self.assertRaisesRegex(FinancialStructuredError, "SOURCE_BYTES_DIFFER"):
            self.evaluate(bundle, "A13")


if __name__ == "__main__":
    unittest.main()
