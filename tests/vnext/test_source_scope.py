"""B0 SourceScopeManifest full-artifact round-trip and tamper checks."""

import copy
import unittest

from tests.vnext.r4_b0_fixture_support import b0_fixture
from vnext.canonical import content_hash
from vnext.source_scope import SourceScopeError, build_source_scope_manifest
from vnext.source_scope import validate_source_scope_manifest


class SourceScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = b0_fixture()

    def test_complete_native_candidate_and_evidence_are_bound(self):
        f = self.fixture
        scope = validate_source_scope_manifest(
            manifest=f["scope"], expected_manifest_id=f["scope"]["source_scope_manifest_id"],
            **f["authority"],
        )
        self.assertEqual(["table_000002"], scope["ordered_table_ids"])
        self.assertEqual([1], scope["ordered_table_orders"])
        self.assertEqual(3, len(scope["table_audit"]))
        self.assertEqual("PASS", scope["check_evidence_result"]["status"])
        self.assertEqual("1.11", scope["check_evidence_result"]["normalized_values"]["liquidity_coverage_ratio"])

    def test_deleted_added_reordered_or_drifting_artifacts_cannot_rebind_pin(self):
        f = self.fixture
        mutations = [
            lambda x: x["ordered_table_ids"].clear(),
            lambda x: x["ordered_table_ids"].append("table_000003"),
            lambda x: x["ordered_table_orders"].__setitem__(0, 2),
            lambda x: x["ordered_grid_hashes"].__setitem__(0, "sha256:" + "0" * 64),
            lambda x: x.__setitem__("source_sha256", "0" * 64),
            lambda x: x.__setitem__("full_derived_asset_id", "sha256:" + "0" * 64),
            lambda x: x.__setitem__("task_contract_hash", "sha256:" + "0" * 64),
            lambda x: x["table_audit"].pop(),
            lambda x: x["reference"].__setitem__("value", "9.99"),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(f["scope"])
            mutation(changed)
            changed["source_scope_manifest_id"] = content_hash(value={
                k: v for k, v in changed.items() if k != "source_scope_manifest_id"
            })
            with self.subTest(mutation=mutation):
                with self.assertRaises(SourceScopeError):
                    validate_source_scope_manifest(
                        manifest=changed, expected_manifest_id=f["scope"]["source_scope_manifest_id"],
                        **f["authority"],
                    )

    def test_invalid_windows_fail_before_certification(self):
        f = self.fixture
        for windows in ([], [{"start_order": -1, "end_order": 1}],
                        [{"start_order": 1, "end_order": 3}],
                        [{"start_order": 1, "end_order": 2}, {"start_order": 2, "end_order": 2}],
                        [{"start_order": 2, "end_order": 2}, {"start_order": 1, "end_order": 1}]):
            audit = copy.deepcopy(f["audit"])
            audit["windows"] = windows
            with self.subTest(windows=windows), self.assertRaises(SourceScopeError):
                build_source_scope_manifest(audit=audit, **f["authority"])

    def test_b06_and_b13_cannot_be_r4_tasks(self):
        f = self.fixture
        for metric in ("B06", "B13"):
            authority = copy.deepcopy(f["authority"])
            authority["task_contract"]["metric_ids"] = [metric]
            authority["evidence_authority_payload"]["task_contract"] = authority["task_contract"]
            with self.assertRaisesRegex(SourceScopeError, "exact R4"):
                build_source_scope_manifest(audit=f["audit"], **authority)
