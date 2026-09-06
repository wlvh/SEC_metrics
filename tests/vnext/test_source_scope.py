"""B0 SourceScopeManifest full-artifact round-trip and tamper checks."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import cell_locator
from tests.vnext.r4_b0_fixture_support import REPO_ROOT, b0_fixture, zero_call_audit
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.source_scope import SourceScopeError, build_source_scope_manifest
from vnext.source_scope import load_source_scope_manifest, validate_source_scope_manifest


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

    def _rebind(self, value):
        value["source_scope_manifest_id"] = content_hash(value={
            key: item for key, item in value.items() if key != "source_scope_manifest_id"})
        return value

    def _assert_rebound_rejected(self, mutation, scope=None):
        changed = copy.deepcopy(scope or self.fixture["scope"])
        mutation(changed)
        self._rebind(changed)
        with self.assertRaises(ValueError):
            validate_source_scope_manifest(manifest=changed,
                expected_manifest_id=changed["source_scope_manifest_id"], **self.fixture["authority"])

    def _scope_with_closed_candidates(self):
        audit = copy.deepcopy(self.fixture["audit"])
        asset = self.fixture["authority"]["full_derived_asset"]
        for index, row_index, column_index in ((0, 0, 0), (1, 0, 1), (2, 0, 0)):
            locator = cell_locator(asset=asset, table_id=asset["tables"][index]["table_id"],
                                   row_index=row_index, column_index=column_index)
            item = {"locator": locator, "disposition": "NOT_TARGET_METRIC",
                    "evidence": "Synthetic complete-file audit rejects this non-observation", "unresolved": False}
            row = audit["table_audit"][index]
            row["candidate_dispositions"].append(item)
            row["candidate_locator_ids"].append(content_hash(value=locator))
            if row["disposition"] != "TARGET":
                row["disposition"] = "CANDIDATES_CLOSED"
            if index != 1:
                audit["out_of_window_candidates"].append(item)
        return build_source_scope_manifest(audit=audit, **self.fixture["authority"])

    def test_all_nested_schema_mutations_fail_even_when_self_id_is_rebound(self):
        mutations = [
            lambda m: m["reference"].__setitem__("extra", "unapproved"),
            lambda m: m["reference"].pop("period"),
            lambda m: m["reference"].__setitem__("value", "1.12"),
            lambda m: m["reference"].__setitem__("unit", "USD"),
            lambda m: m["reference"].__setitem__("period", "FY2024"),
            lambda m: m["reference"]["scope"].__setitem__("aggregation", "point_in_time"),
            lambda m: m["estimated_tokens"].__setitem__("actual_provider_usage", 1),
            lambda m: m["table_audit"][1].pop("candidate_dispositions"),
            lambda m: m["table_audit"][1]["candidate_locator_ids"].clear(),
            lambda m: m["table_audit"][1]["candidate_dispositions"][0].__setitem__("unresolved", 0),
            lambda m: m["table_audit"][1]["candidate_dispositions"][0].__setitem__("evidence", ""),
            lambda m: m["navigation_paths"][0].pop("source_sha256"),
            lambda m: m["navigation_paths"][1].__setitem__("method", m["navigation_paths"][0]["method"]),
            lambda m: m["navigation_paths"][1].__setitem__("source_sha256", "0" * 64),
            lambda m: m["navigation_paths"].reverse(),
            lambda m: m["material_layout_proof"].__setitem__("source_cik", "124"),
            lambda m: m["material_layout_proof"].__setitem__("source_sha256", "0" * 64),
            lambda m: m["material_layout_proof"].__setitem__("kind", "UNKNOWN"),
            lambda m: m["windows"][0].__setitem__("start_order", True),
            lambda m: m["ordered_table_ids"].append("table_000003"),
            lambda m: m["table_audit"].reverse(),
            lambda m: m["table_audit"].pop(),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self._assert_rebound_rejected(mutation)

    def test_successor_generation_and_partial_identities_cannot_downgrade(self):
        identity_fields = ["artifact_requirement_generation", "requirement_id",
                           "requirement_closure_hash", "requirement_hashes"]
        for fields in [identity_fields, identity_fields[1:], identity_fields[:2]] + [[f] for f in identity_fields]:
            with self.subTest(fields=fields):
                self._assert_rebound_rejected(lambda m: [m.pop(field) for field in fields])
        for key, value in (("artifact_requirement_generation", "LEGACY_IMPLICIT"),
                           ("requirement_id", "issue_15_v1"),
                           ("requirement_closure_hash", "sha256:" + "0" * 64),
                           ("requirement_hashes", {})):
            with self.subTest(field=key):
                self._assert_rebound_rejected(lambda m: m.__setitem__(key, value))

    def test_two_windows_keep_original_ids_and_require_exact_projection(self):
        audit = copy.deepcopy(self.fixture["audit"])
        audit["windows"] = [{"start_order": 0, "end_order": 0}, {"start_order": 1, "end_order": 1}]
        scope = build_source_scope_manifest(audit=audit, **self.fixture["authority"])
        self.assertEqual(["table_000001", "table_000002"], scope["ordered_table_ids"])
        self.assertEqual([0, 1], scope["ordered_table_orders"])
        self._assert_rebound_rejected(lambda m: m["ordered_table_ids"].reverse(), scope=scope)
        self._assert_rebound_rejected(lambda m: m["ordered_grid_hashes"].pop(), scope=scope)

    def test_outside_closure_and_inside_candidates_have_one_exact_census(self):
        scope = self._scope_with_closed_candidates()
        self.assertEqual(2, len(scope["out_of_window_candidates"]))
        self.assertEqual(2, len(scope["table_audit"][1]["candidate_dispositions"]))
        mutations = [lambda m: m["out_of_window_candidates"].pop(),
                     lambda m: m["out_of_window_candidates"].reverse(),
                     lambda m: m["out_of_window_candidates"].append(m["table_audit"][1]["candidate_dispositions"][1]),
                     lambda m: m["table_audit"][0]["candidate_dispositions"][0].__setitem__("unresolved", True),
                     lambda m: m["table_audit"][0]["candidate_dispositions"][0].__setitem__("disposition", "POSSIBLE"),
                     lambda m: m["table_audit"][1]["candidate_dispositions"].pop()]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self._assert_rebound_rejected(mutation, scope=scope)

    def test_alternate_requires_different_issuer_source_and_material_differences(self):
        audit = copy.deepcopy(self.fixture["audit"])
        audit["fixture_class"] = "POSITIVE_ALTERNATE_LAYOUT"
        audit["material_layout_proof"].update(kind="MATERIAL_ALTERNATE_LAYOUT", comparison_source_cik="124",
            comparison_source_sha256="1" * 64, differences=["TABLE_GEOMETRY", "COLUMN_ORDER"])
        scope = build_source_scope_manifest(audit=audit, **self.fixture["authority"])
        for key, value in (("comparison_source_cik", "123"), ("comparison_source_sha256", scope["source_sha256"]),
                           ("differences", ["TABLE_GEOMETRY"]), ("kind", "PRODUCTION_BASELINE")):
            with self.subTest(field=key):
                self._assert_rebound_rejected(lambda m: m["material_layout_proof"].__setitem__(key, value), scope=scope)

    def test_scope_loader_requires_regular_exact_bytes_and_rechecks_source(self):
        f = self.fixture
        with tempfile.TemporaryDirectory(prefix="r4-scope-loader-", dir=REPO_ROOT) as tmp:
            path = Path(tmp) / "scope.json"
            encoded = canonical_json_bytes(value=f["scope"])
            path.write_bytes(encoded)
            kwargs = {"path": path, "repo_root": REPO_ROOT,
                      "expected_manifest_id": f["scope"]["source_scope_manifest_id"], **f["authority"]}
            self.assertEqual(f["scope"], load_source_scope_manifest(
                expected_sha256=sha256_bytes(content=encoded), expected_size=len(encoded), **kwargs))
            with self.assertRaisesRegex(SourceScopeError, "byte hash"):
                load_source_scope_manifest(expected_sha256="0" * 64, **kwargs)
            with self.assertRaisesRegex(SourceScopeError, "byte size"):
                load_source_scope_manifest(expected_size=len(encoded) + 1, **kwargs)
            alias = Path(tmp) / "alias.json"
            alias.symlink_to(path)
            with self.assertRaisesRegex(SourceScopeError, "regular"):
                load_source_scope_manifest(**{**kwargs, "path": alias})
            directory_alias = Path(tmp) / "alias-dir"
            directory_alias.symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaisesRegex(SourceScopeError, "regular"):
                load_source_scope_manifest(**{**kwargs, "path": directory_alias / "scope.json"})
            path.write_text('{"record_type":"SOURCE_SCOPE_MANIFEST","record_type":"SOURCE_SCOPE_MANIFEST"}')
            with self.assertRaisesRegex(SourceScopeError, "strict UTF-8 JSON"):
                load_source_scope_manifest(**kwargs)
            path.write_text(json.dumps({**f["scope"], "unexpected": True}))
            with self.assertRaisesRegex(SourceScopeError, "fields are not exact"):
                load_source_scope_manifest(**kwargs)

    def test_zero_call_scope_cannot_claim_positive_value_or_target(self):
        f = self.fixture
        audit = zero_call_audit(audit=f["audit"], classification="NEGATIVE_EXPECTED")
        scope = build_source_scope_manifest(audit=audit, **f["authority"])
        self.assertIsNone(scope["check_evidence_result"])
        self._assert_rebound_rejected(lambda m: m.__setitem__("target_locator", f["scope"]["target_locator"]), scope=scope)
        self._assert_rebound_rejected(lambda m: m["reference"].__setitem__("value", "1.11"), scope=scope)

    def test_scope_disk_load_detects_real_source_byte_drift(self):
        f = self.fixture
        with tempfile.TemporaryDirectory(prefix="r4-source-drift-", dir=REPO_ROOT) as tmp:
            directory = Path(tmp)
            source_path = directory / "source.html"
            source_path.write_bytes((REPO_ROOT / f["authority"]["raw_blob"]["storage_uri"]).read_bytes())
            authority = copy.deepcopy(f["authority"])
            authority["raw_blob"]["storage_uri"] = source_path.relative_to(REPO_ROOT).as_posix()
            scope = build_source_scope_manifest(audit=f["audit"], **authority)
            scope_path = directory / "scope.json"
            scope_path.write_bytes(canonical_json_bytes(value=scope))
            args = {"path": scope_path, "repo_root": REPO_ROOT,
                    "expected_manifest_id": scope["source_scope_manifest_id"], **authority}
            self.assertEqual(scope, load_source_scope_manifest(**args))
            source_path.write_bytes(source_path.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                load_source_scope_manifest(**args)
