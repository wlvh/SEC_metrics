"""Successor task/source audit boundaries; no live qualification credit."""

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext.canonical import content_hash, strict_json_file
from vnext.deterministic_router import DeterministicRouterError
from vnext.deterministic_router import adapt_accession_xbrl, source_role_plan
from vnext.deterministic_router import validate_source_set_manifest
from vnext.r4_source_audit import audit_scope_alias_coverage
from vnext.r4_structured_sources import FixtureSourceSetError
from vnext.r4_structured_sources import build_pinned_fixture_source_set, validate_fixture_source_set
from vnext.r4_task_contracts import R4TaskContractError
from vnext.r4_task_contracts import inspect_r4_task_catalog, resolve_r4_task_contract
from vnext.r4_fixture_authority import load_r4_fixture_authority, R4FixtureAuthorityError
from vnext.requirements import load_requirement_snapshot


ROOT = Path(__file__).resolve().parents[2]


class R4FixtureAuthorityTest(unittest.TestCase):
    def test_input_matrix_has_exact_six_pairs_and_all_six_classes(self):
        authority = load_r4_fixture_authority(repo_root=ROOT)
        self.assertEqual(authority["matrix"]["metric_ids"], ["A03", "A04", "A09", "A11", "A12", "A13"])
        self.assertEqual(len(authority["fixtures"]), 16)
        self.assertEqual(sum(f["artifact_kind"] == "SCOPED_EXTRACTION" for f in authority["fixtures"]), 9)
        self.assertEqual(sum(f["artifact_kind"] == "STRUCTURED_PRIMARY" for f in authority["fixtures"]), 3)
        for metric in authority["matrix"]["metric_ids"]:
            pair = [f for f in authority["fixtures"] if f["metric_id"] == metric and f["fixture_class"].startswith("POSITIVE_")]
            self.assertEqual(len(pair), 2)
            sources = [authority["sources"][f["source_id"]] for f in pair]
            self.assertNotEqual(sources[0]["cik"], sources[1]["cik"])
            self.assertNotEqual(sources[0]["full_derived_asset_id"], sources[1]["full_derived_asset_id"])

    def test_rebound_input_matrix_cannot_drop_class_or_add_future_metric(self):
        original = load_r4_fixture_authority(repo_root=ROOT)["matrix"]
        mutations = []
        changed = copy.deepcopy(original)
        changed["metric_ids"].append("B06")
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["fixtures"] = [f for f in changed["fixtures"] if f["fixture_class"] != "QUALITATIVE_ONLY"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["fixtures"].append(copy.deepcopy(changed["fixtures"][0]))
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["provider_paid_sec_authorized"] = True
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["qualification_credit"] = "CURRENT"
        mutations.append(changed)
        for changed in mutations:
            def read(*, path):
                return changed if path.name == "r4_fixture_matrix_v1.json" else strict_json_file(path=path)
            with self.subTest(matrix_hash=content_hash(value=changed)), patch(
                    "vnext.r4_fixture_authority.strict_json_file", side_effect=read):
                with self.assertRaises(R4FixtureAuthorityError):
                    load_r4_fixture_authority(repo_root=ROOT)

    def test_successor_task_set_is_exact_and_v1_does_not_authorize_it(self):
        data = inspect_r4_task_catalog(repo_root=ROOT)
        self.assertEqual([task["metric_ids"][0] for task in data["contracts"]],
                         ["A03", "A04", "A09", "A11", "A12", "A13"])
        self.assertTrue(all(task["metric_spec_paths"][0].startswith("catalog/r4_v2/")
                            for task in data["contracts"]))
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / "requirements/issue_28_v1")
        with self.assertRaises((R4TaskContractError, ValueError)):
            resolve_r4_task_contract(repo_root=ROOT, requirement=requirement,
                                     task_contract_id=data["contracts"][0]["task_contract_id"])

    def test_fresh_inline_xbrl_uses_explicit_fixture_only_source_set(self):
        receipt = strict_json_file(path=ROOT / "docs/r4_offline/fixture_acquisition_receipt.json")
        for source in receipt["sources"]:
            with self.subTest(source_id=source["source_id"]):
                manifest = build_pinned_fixture_source_set(repo_root=ROOT, source_id=source["source_id"])
                self.assertEqual(manifest["source_reference"]["request_attempt_id"], source["request_attempt_id"])
                self.assertEqual(manifest["inline_dei"]["context_period_end"], "2025-12-31")
                self.assertEqual(manifest["inline_dei"]["document_period_end"], "December 31, 2025")
                self.assertFalse(manifest["latest_filing_claim"])
                self.assertFalse(manifest["full_submissions_inventory_claim"])
                with self.assertRaises(DeterministicRouterError):
                    validate_source_set_manifest(manifest=manifest)
                with self.assertRaises(DeterministicRouterError):
                    source_role_plan(manifest=manifest, source_mode="accession_xbrl")
                claims = adapt_accession_xbrl(
                    raw_bytes=(ROOT / source["source_repo_relative_path"]).read_bytes(),
                    source_reference=manifest["source_reference"], source_set_manifest=manifest,
                    fact_names=["us-gaap:Revenues"])
                self.assertTrue(claims)
                self.assertTrue(all(c["source_role"] == "offline_fixture_accession_xbrl" for c in claims))
                for field, value in (("latest_filing_claim", True),
                                     ("qualification_credit", "CURRENT"),
                                     ("record_type", "SOURCE_SET_MANIFEST")):
                    changed = copy.deepcopy(manifest)
                    changed[field] = value
                    changed["source_set_manifest_id"] = content_hash(value={
                        k: v for k, v in changed.items() if k != "source_set_manifest_id"})
                    with self.assertRaises(FixtureSourceSetError):
                        validate_fixture_source_set(manifest=changed)

    def test_a03_alternate_scope_absence_is_exhaustive_on_both_fresh_sources(self):
        receipt = strict_json_file(path=ROOT / "docs/r4_offline/fixture_acquisition_receipt.json")
        for source in receipt["sources"]:
            result = audit_scope_alias_coverage(
                repo_root=ROOT, declaration={**source, "media_type": "text/html"},
                task_contract_id="financial_liquidity_coverage_ratio_table_v1")
            self.assertEqual(result["complete_scope_tables"], [])
            self.assertGreater(result["table_count"], 300)


if __name__ == "__main__":
    unittest.main()
