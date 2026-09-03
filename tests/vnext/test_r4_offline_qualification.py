"""Audit regressions only: rejected references must never become qualification."""

import copy
import unittest
from pathlib import Path

from tests.vnext.r4_b0_fixture_support import b0_fixture
from vnext.batch_workflow import request_attempt_binding
from vnext.canonical import content_hash, strict_json_file
from vnext.deterministic_router import adapt_accession_xbrl, source_set_manifest
from vnext.r4_source_audit import R4SourceAuditError, _native_probe
from vnext.r4_source_audit import audit_scope_alias_coverage
from vnext.r4_source_audit import inventory_immutable_sources, source_authority
from vnext.sources import raw_blob_record, source_reference_record


REPO_ROOT = Path(__file__).resolve().parents[2]
RECIPE_PATH = REPO_ROOT / "tests/fixtures/vnext/r4_offline/jpm_fy2025_probe.json"


class R4OfflineAuditTest(unittest.TestCase):
    def test_inventory_binds_existing_ledger_and_immutable_source(self):
        recipe = strict_json_file(path=RECIPE_PATH)
        inventory = inventory_immutable_sources(
            repo_root=REPO_ROOT, issuer_ciks=[recipe["source"]["cik"]])
        body = {k: v for k, v in inventory.items() if k != "inventory_id"}
        self.assertEqual(inventory["inventory_id"], content_hash(value=body))
        self.assertEqual(inventory["provider_paid_sec_calls"], [0, 0, 0])
        self.assertIn(recipe["source"]["source_sha256"], [
            row["source_sha256"] for row in inventory["issuer_inventory"][0]["immutable_sources"]])

    def test_source_path_sha_size_and_attempt_identity_are_not_optional(self):
        declaration = strict_json_file(path=RECIPE_PATH)["source"]
        source = source_authority(repo_root=REPO_ROOT, declaration=declaration)
        self.assertEqual(source["raw_blob"]["raw_asset_id"],
                         "sha256:" + declaration["source_sha256"])
        self.assertTrue(source["source_reference"]["request_attempt_id"].startswith("request:attempt:"))
        for field, value in (("source_sha256", "f" * 64),
                             ("source_size", declaration["source_size"] + 1),
                             ("accession", "0000000000-26-000001"),
                             ("source_repo_relative_path", "outputs/metrics_matrix.csv")):
            with self.subTest(field=field):
                changed = dict(declaration, **{field: value})
                with self.assertRaises(R4SourceAuditError):
                    source_authority(repo_root=REPO_ROOT, declaration=changed)

    def test_native_review_required_remains_non_auto_eligible(self):
        fixture = b0_fixture()
        authority = fixture["authority"]
        recipe = {
            "target": {"table_order": 1, "row_index": 1, "column_index": 1},
            "claimed_period": "FY2025", "scope_labels": [],
            "header_coordinates": [],
        }
        original_asset = copy.deepcopy(authority["full_derived_asset"])
        result = _native_probe(
            asset=authority["full_derived_asset"],
            source={"source_reference": authority["source_reference"]},
            task=authority["task_contract"], recipe=recipe, unit="percent")
        self.assertEqual(result["candidate"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["evidence"]["status"], "PASS")
        self.assertFalse(result["evidence"]["system_approval_eligible"])
        self.assertEqual(authority["full_derived_asset"], original_asset)

    def test_jpm_native_a12_has_no_complete_same_table_scope(self):
        recipe = strict_json_file(path=RECIPE_PATH)
        task_id = next(p["task_contract_id"] for p in recipe["probes"]
                       if p["metric_id"] == "A12")
        coverage = audit_scope_alias_coverage(
            repo_root=REPO_ROOT, declaration=recipe["source"], task_contract_id=task_id)
        self.assertEqual(coverage["table_count"], 679)
        self.assertEqual(coverage["complete_scope_tables"], [])
        self.assertTrue(coverage["any_alias_tables"])
        self.assertTrue(all("holding_period" not in row["scope_aliases"]
                            for row in coverage["any_alias_tables"]))
        self.assertEqual(coverage["qualification_credit"], "NONE_OFFLINE_AUDIT")

    def test_structured_ambiguity_replays_through_native_accession_adapter(self):
        """Verify actual claim sets without choosing a new economic meaning."""
        recipe = strict_json_file(path=RECIPE_PATH)
        evidence = strict_json_file(path=REPO_ROOT / "docs/r4_offline/source_audit_evidence.json")
        expected = evidence["structured_route_probe"]
        declaration = dict(recipe["source"])
        declaration.update({
            "document_name": "jpm-20251231_htm.xml",
            "source_url": recipe["source"]["source_url"].replace(".htm", "_htm.xml"),
            "source_repo_relative_path": "evidence/request_attempts/{}/{}/{}".format(
                expected["source_sha256"][:2], expected["source_sha256"], "jpm-20251231_htm.xml"),
            "source_sha256": expected["source_sha256"],
            "source_size": expected["source_size"], "media_type": "application/xml",
        })
        source = source_authority(repo_root=REPO_ROOT, declaration=declaration)
        inventory_name = "CIK{}.json".format(declaration["cik"].zfill(10))
        inventory_url = "https://data.sec.gov/submissions/" + inventory_name
        inventory_path = "evidence/request_attempts/{}/{}/{}".format(
            expected["submissions_sha256"][:2], expected["submissions_sha256"], inventory_name)
        raw = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=inventory_path,
                              media_type="application/json")
        binding = request_attempt_binding(
            repo_root=REPO_ROOT, source_url=inventory_url,
            content_sha256=expected["submissions_sha256"],
            accession="SUBMISSIONS-2025", document_name=inventory_name)
        self.assertEqual(binding["request_attempt_id"], expected["submissions_attempt_id"])
        reference = source_reference_record(
            raw_blob=raw, company_id=declaration["company_id"],
            source_url=inventory_url, accession="SUBMISSIONS-2025",
            document_name=inventory_name, source_role="sec_submissions_inventory",
            request_attempt_id=binding["request_attempt_id"])
        manifest = source_set_manifest(
            company_id=declaration["company_id"], source_role="target_primary",
            form_types=["10-K"], fiscal_or_date_window=expected["filing_date_window"],
            discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
            inventory_source_reference=reference,
            inventory_bytes=(REPO_ROOT / inventory_path).read_bytes(),
            ordered_source_references=[source["source_reference"]],
            cutoff_timestamp_or_pinned_submissions_attempt=reference["request_attempt_id"])
        self.assertEqual(manifest["source_set_manifest_id"], expected["source_set_manifest_id"])
        for outcome in expected["outcomes"]:
            with self.subTest(metric_id=outcome["metric_id"]):
                claims = adapt_accession_xbrl(
                    raw_bytes=source["source_bytes"], source_reference=source["source_reference"],
                    source_set_manifest=manifest, fact_names=outcome["fact_names"])
                self.assertEqual(len(claims), outcome["adapted_claims_count"])
                self.assertEqual(content_hash(value=claims), outcome["adapted_claims_hash"])
                axes = outcome.get("geographic_dimension_axes", [])
                current = [claim for claim in claims
                           if claim["attributes"]["context"]["period_end"] == "2025-12-31"
                           and (not axes or set(axes).intersection(
                               claim["attributes"]["context"]["dimensions"]))]
                self.assertEqual(len(current), outcome["current_period_candidates_count"])
                self.assertEqual(content_hash(value=current), outcome["current_period_candidates_hash"])
                self.assertGreater(len(current), 1)
                self.assertEqual(outcome["candidate_resolution"], "NOT_SELECTED_BY_AUDIT")
                self.assertEqual(outcome["no_anchor_closure"], "NOT_COMPLETE")


if __name__ == "__main__":
    unittest.main()
