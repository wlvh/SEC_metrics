"""Verify the Issue #15 39-metric SourceStrategy registry."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Dict

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_issue15_authority import copy_test_repository
from tests.vnext.test_issue15_authority import read_json, write_json
from vnext.canonical import content_hash, sha256_file
from vnext.publication import PublicationView, verify_publication_bundle
from vnext.source_strategy import ALLOWED_SOURCE_MODES
from vnext.source_strategy import GENERIC_FORBIDDEN_LITERAL_DENYLIST
from vnext.source_strategy import RELEASED_PLAN_REQUIREMENT_CLOSURES
from vnext.source_strategy import SourceStrategyError
from vnext.source_strategy import _qualification_subset
from vnext.source_strategy import _reader_family_versions
from vnext.source_strategy import _release_authority
from vnext.source_strategy import _retired_producer_ids
from vnext.source_strategy import load_issue15_release_plan
from vnext.source_strategy import load_issue15_release_plans
from vnext.source_strategy import load_source_strategy_registry
from vnext.requirements import load_requirement_snapshot


ISSUE_15_DIR = REPO_ROOT / "requirements" / "issue_15_v1"


def rebind_registry(*, issue_copy: Path, registry: Dict[str, object]) -> None:
    """Write a forged registry and repair its outer Requirement bindings.

    Args:
        issue_copy: Copied ``requirements/issue_15_v1`` directory.
        registry: Mutated registry object under semantic negative test.

    Expected output:
        Registry and ReleasePlan byte checks remain self-consistent, forcing
        the semantic loader to reject the actual policy drift.
    """
    repository_root = issue_copy.parents[1]
    registry_path = repository_root / "config" / "source_strategy_registry.json"
    write_json(path=registry_path, value=registry)

    baseline_path = issue_copy / "baseline_manifest.json"
    baseline = read_json(path=baseline_path)
    registry_binding = baseline["runtime_authority_files"][
        "config/source_strategy_registry.json"
    ]
    registry_binding["sha256"] = sha256_file(path=registry_path)
    registry_binding["size"] = registry_path.stat().st_size
    write_json(path=baseline_path, value=baseline)


def rebind_plan_chain(*, repository_root: Path) -> None:
    """Recompute plan and index content identities after a negative mutation."""
    index_path = repository_root / "config" / "issue_15_release_plan.json"
    index = read_json(path=index_path)
    for entry in index["release_plan_paths"]:
        plan_path = repository_root / entry["path"]
        plan = read_json(path=plan_path)
        body = {
            field: plan[field]
            for field in plan if field != "release_plan_content_id"
        }
        plan["release_plan_content_id"] = content_hash(value=body)
        entry["release_plan_content_id"] = plan["release_plan_content_id"]
        write_json(path=plan_path, value=plan)
    active = index["release_plan_paths"][-1]
    index["active_release_plan_id"] = active["release_plan_id"]
    index["active_release_plan_content_id"] = active[
        "release_plan_content_id"
    ]
    body = {
        field: index[field]
        for field in index if field != "release_plan_index_id"
    }
    index["release_plan_index_id"] = content_hash(value=body)
    write_json(path=index_path, value=index)


def rederive_r2_semantics(
    *, repository_root: Path, plan: Dict[str, object],
) -> None:
    """Recompute every cumulative-dependent R2 field after mutation."""
    registry = load_source_strategy_registry(repo_root=repository_root)
    cumulative = list(plan["cumulative_metric_ids"])
    plan["retired_legacy_producer_ids"] = _retired_producer_ids(
        repo_root=repository_root,
        cumulative_metric_ids=cumulative,
    )
    plan["reader_family_versions"] = _reader_family_versions(
        cumulative_metric_ids=cumulative,
        registry=registry,
    )
    qualification_subset = _qualification_subset(
        cumulative_metric_ids=cumulative,
        metrics=registry["metrics"],
    )
    plan["authority_hashes"] = _release_authority(
        repo_root=repository_root,
        registry=registry,
        qualification_subset=qualification_subset,
    )


class SourceStrategyRegistryTest(unittest.TestCase):
    """Prove WB-2 exact coverage, schema, and state separation."""

    def test_registry_covers_exact_39_without_migration_state(self) -> None:
        """Load every route and prove only ReleasePlan owns current state."""
        loaded = load_source_strategy_registry(repo_root=REPO_ROOT)
        plan = load_issue15_release_plan(
            repo_root=REPO_ROOT, release_plan_id="issue_15_zero_ai_r2",
        )
        registry = loaded["registry"]
        metrics = loaded["metrics"]
        self.assertEqual(39, len(metrics))
        self.assertEqual(ALLOWED_SOURCE_MODES, registry["allowed_source_modes"])
        self.assertEqual(
            {
                "structured_only": 24,
                "structured_first_ai_fallback": 4,
                "ai_table": 7,
                "ai_text": 4,
            },
            dict(Counter(metric["source_mode"] for metric in metrics.values())),
        )
        serialized = json.dumps(registry, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("ai_event_text", serialized)
        for state in (
            "ROUTE_INVENTORY_ONLY",
            "SHADOW_ONLY",
            "MIGRATED_PRODUCTION",
        ):
            self.assertNotIn(state, serialized)
        self.assertEqual(
            "ReleasePlan.cumulative_metric_ids",
            registry["migration_state_authority"],
        )
        self.assertEqual(
            [
                "A01", "A02", "A05", "A06", "A07", "A08", "A10",
                "B01", "B02", "B03", "B04", "B05", "B07", "B08",
                "B09", "B12", "C01", "E01", "E02", "E03", "E04",
                "E05",
            ],
            plan["cumulative_metric_ids"],
        )
        self.assertEqual([], plan["qualification_matrix_subset"])

    def test_release_plan_chain_is_complete_and_monotonic(self) -> None:
        """Bind immutable R1/R2/R3 parent, keys, families, and closure."""
        loaded = load_issue15_release_plans(repo_root=REPO_ROOT)
        r1, r2, r3 = loaded["plans"]
        self.assertEqual("issue_15_lodging_r3", loaded["active_release_plan_id"])
        self.assertEqual(None, r1["parent_release_plan_id"])
        self.assertEqual(r1["release_plan_id"], r2["parent_release_plan_id"])
        self.assertEqual(
            r1["release_plan_content_id"],
            r2["parent_release_plan_content_id"],
        )
        self.assertEqual(["B01", "B03"], r1["added_metric_ids"])
        self.assertEqual(20, len(r1["cumulative_vnext_result_keys"]))
        self.assertEqual(20, len(r2["added_metric_ids"]))
        self.assertEqual(22, len(r2["cumulative_metric_ids"]))
        self.assertEqual(220, len(r2["cumulative_vnext_result_keys"]))
        self.assertEqual(r2["release_plan_id"], r3["parent_release_plan_id"])
        self.assertEqual(
            r2["release_plan_content_id"],
            r3["parent_release_plan_content_id"],
        )
        self.assertEqual(["B10", "B11"], r3["added_metric_ids"])
        self.assertEqual(24, len(r3["cumulative_metric_ids"]))
        self.assertEqual(240, len(r3["cumulative_vnext_result_keys"]))
        self.assertEqual(
            [
                {
                    "metric_id": "B10",
                    "reader_family_id": "lodging_kpi_table",
                    "source_mode": "ai_table",
                },
                {
                    "metric_id": "B11",
                    "reader_family_id": "lodging_kpi_table",
                    "source_mode": "ai_table",
                },
            ],
            r3["qualification_matrix_subset"],
        )
        self.assertEqual(
            sorted(
                set(r2["cumulative_metric_ids"])
                - set(r1["cumulative_metric_ids"])
            ),
            r2["added_metric_ids"],
        )
        self.assertTrue(
            set(r1["retired_legacy_producer_ids"]).issubset(
                set(r2["retired_legacy_producer_ids"])
            )
        )
        transition = loaded["ratchet_transitions"][1]
        self.assertEqual([], transition["removed_metric_ids"])
        self.assertEqual([], transition["removed_vnext_result_keys"])
        self.assertEqual([], transition["unretired_legacy_producer_ids"])
        self.assertEqual(
            r1["release_plan_content_id"],
            transition["parent_release_plan_content_id"],
        )
        r3_transition = loaded["ratchet_transitions"][2]
        self.assertEqual(["B10", "B11"], r3_transition["added_metric_ids"])
        self.assertEqual([], r3_transition["removed_metric_ids"])
        self.assertEqual([], r3_transition["removed_vnext_result_keys"])
        self.assertEqual([], r3_transition["unretired_legacy_producer_ids"])
        self.assertEqual(
            r2["release_plan_content_id"],
            r3_transition["parent_release_plan_content_id"],
        )
        for plan in (r1, r2, r3):
            self.assertEqual(
                RELEASED_PLAN_REQUIREMENT_CLOSURES[plan["release_plan_id"]],
                plan["requirement_closure_hash"],
            )
        self.assertEqual(
            r3["requirement_closure_hash"],
            loaded["requirement_closure_hash"],
        )
        current = load_requirement_snapshot(snapshot_dir=ISSUE_15_DIR)
        self.assertEqual(
            current["requirement_closure_hash"],
            loaded["current_requirement_closure_hash"],
        )
        self.assertNotEqual(
            loaded["requirement_closure_hash"],
            loaded["current_requirement_closure_hash"],
        )
        self.assertEqual(
            124761,
            current["effective_decisions"]["D-35"]["choice"][
                "financial_materialization_resource_policy"
            ]["production_max_total_cells_after"],
        )
        self.assertNotEqual(
            r2["requirement_closure_hash"],
            loaded["current_requirement_closure_hash"],
        )

    def test_release_plan_parent_forgery_fails_after_rehash(self) -> None:
        """Reject a content-addressed R2 that detaches from immutable R1."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            repository_root = issue_copy.parents[1]
            path = (
                repository_root / "config" / "release_plans"
                / "issue_15_zero_ai_r2.json"
            )
            plan = read_json(path=path)
            plan["parent_release_plan_id"] = "issue_15_zero_ai_r0"
            write_json(path=path, value=plan)
            rebind_plan_chain(repository_root=repository_root)
            with self.assertRaisesRegex(
                SourceStrategyError, "ratchet chain differs",
            ):
                load_issue15_release_plans(repo_root=repository_root)

    def test_release_plan_requirement_forgery_fails_after_rehash(self) -> None:
        """Reject a plan whose declared Requirement closure is detached."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            repository_root = issue_copy.parents[1]
            path = (
                repository_root / "config" / "release_plans"
                / "issue_15_zero_ai_r1.json"
            )
            plan = read_json(path=path)
            plan["requirement_closure_hash"] = "sha256:" + "0" * 64
            write_json(path=path, value=plan)
            rebind_plan_chain(repository_root=repository_root)
            with self.assertRaisesRegex(
                SourceStrategyError, "identity differs",
            ):
                load_issue15_release_plans(repo_root=repository_root)

    def test_release_plan_removed_metric_fails_after_full_rehash(self) -> None:
        """Reject removed B01 after all child semantic hashes are rebound."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            repository_root = issue_copy.parents[1]
            path = (
                repository_root / "config" / "release_plans"
                / "issue_15_zero_ai_r2.json"
            )
            plan = read_json(path=path)
            plan["cumulative_metric_ids"] = [
                metric_id
                for metric_id in plan["cumulative_metric_ids"]
                if metric_id != "B01"
            ]
            plan["cumulative_vnext_result_keys"] = [
                key for key in plan["cumulative_vnext_result_keys"]
                if key["metric_id"] != "B01"
            ]
            parent = read_json(
                path=(
                    repository_root / "config" / "release_plans"
                    / "issue_15_zero_ai_r1.json"
                )
            )
            plan["added_metric_ids"] = sorted(
                set(plan["cumulative_metric_ids"])
                - set(parent["cumulative_metric_ids"])
            )
            rederive_r2_semantics(
                repository_root=repository_root, plan=plan,
            )
            write_json(path=path, value=plan)
            rebind_plan_chain(repository_root=repository_root)
            with self.assertRaisesRegex(
                SourceStrategyError, "no-removal gate failed",
            ):
                load_issue15_release_plans(repo_root=repository_root)

    def test_release_plan_removed_parent_key_fails_after_rehash(self) -> None:
        """Reject one removed parent coordinate after content re-signing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            repository_root = issue_copy.parents[1]
            path = (
                repository_root / "config" / "release_plans"
                / "issue_15_zero_ai_r2.json"
            )
            plan = read_json(path=path)
            removed = False
            keys = []
            for key in plan["cumulative_vnext_result_keys"]:
                if key["metric_id"] == "B01" and not removed:
                    removed = True
                    continue
                keys.append(key)
            self.assertTrue(removed)
            plan["cumulative_vnext_result_keys"] = keys
            write_json(path=path, value=plan)
            rebind_plan_chain(repository_root=repository_root)
            with self.assertRaisesRegex(
                SourceStrategyError, "no-removal gate failed",
            ):
                load_issue15_release_plans(repo_root=repository_root)

    def test_release_plan_unretires_parent_producer_after_rehash(self) -> None:
        """Reject a smaller child retirement set after content re-signing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            repository_root = issue_copy.parents[1]
            r1 = read_json(
                path=(
                    repository_root / "config" / "release_plans"
                    / "issue_15_zero_ai_r1.json"
                )
            )
            path = (
                repository_root / "config" / "release_plans"
                / "issue_15_zero_ai_r2.json"
            )
            plan = read_json(path=path)
            parent_producer = r1["retired_legacy_producer_ids"][0]
            plan["retired_legacy_producer_ids"] = [
                producer_id
                for producer_id in plan["retired_legacy_producer_ids"]
                if producer_id != parent_producer
            ]
            write_json(path=path, value=plan)
            rebind_plan_chain(repository_root=repository_root)
            with self.assertRaisesRegex(
                SourceStrategyError, "no-removal gate failed",
            ):
                load_issue15_release_plans(repo_root=repository_root)

    def test_family_literals_are_specific_and_drive_one_union(self) -> None:
        """Keep forbidden literals family-owned and exclude common words."""
        loaded = load_source_strategy_registry(repo_root=REPO_ROOT)
        literals = loaded["forbidden_production_literals"]
        folded = {literal.casefold() for literal in literals}
        self.assertTrue(literals)
        self.assertEqual(len(literals), len(folded))
        self.assertFalse(GENERIC_FORBIDDEN_LITERAL_DENYLIST.intersection(folded))
        for family in loaded["families"].values():
            self.assertIn("forbidden_production_literals", family)

    def test_wb2_does_not_change_root_business_outputs(self) -> None:
        """Bind the untouched public matrix to the frozen WB-1 receipt."""
        baseline = read_json(
            path=ISSUE_15_DIR / "source_strategy_baseline_receipt.json"
        )
        pointer_path = REPO_ROOT / "outputs" / "active_publication.json"
        if pointer_path.exists():
            # WB-2's frozen bytes remain the immutable predecessor after the
            # later ratchet publishes additional structural coordinates.
            active = PublicationView.open(publication_root=REPO_ROOT)
            predecessor = active.manifest["previous_publication_id"]
            while predecessor is not None:
                bundle = (
                    REPO_ROOT / "outputs" / "publications" / str(predecessor)
                )
                manifest = verify_publication_bundle(bundle_dir=bundle)
                if (bundle / "internal/legacy_baseline_import.json").is_file():
                    matrix_path = bundle / "metrics_matrix.csv"
                    break
                predecessor = manifest["previous_publication_id"]
            else:
                self.fail("Active publication chain lacks legacy A")
        else:
            matrix_path = REPO_ROOT / "outputs" / "metrics_matrix.csv"
        self.assertEqual(
            baseline["matrix_sha256"], sha256_file(path=matrix_path),
        )
        self.assertEqual(230, baseline["row_count"])

    def test_missing_metric_fails_after_outer_hashes_are_rebound(self) -> None:
        """Reject a 38-row registry even when its file hashes are repaired."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            registry = read_json(
                path=issue_copy.parents[1]
                / "config"
                / "source_strategy_registry.json"
            )
            del registry["metrics"]["E05"]
            rebind_registry(issue_copy=issue_copy, registry=registry)
            with self.assertRaisesRegex(
                SourceStrategyError, "metric exact set differs",
            ):
                load_source_strategy_registry(repo_root=issue_copy.parents[1])

    def test_ai_event_text_fails_after_outer_hashes_are_rebound(self) -> None:
        """Reject the removed event-AI source mode explicitly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            registry = read_json(
                path=issue_copy.parents[1]
                / "config"
                / "source_strategy_registry.json"
            )
            registry["metrics"]["E01"]["source_mode"] = "ai_event_text"
            registry["metrics"]["E01"]["structured_route_id"] = None
            rebind_registry(issue_copy=issue_copy, registry=registry)
            with self.assertRaisesRegex(SourceStrategyError, "ai_event_text"):
                load_source_strategy_registry(repo_root=issue_copy.parents[1])

    def test_registry_cannot_store_current_migration_state(self) -> None:
        """Reject a family literal used to smuggle a current state value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            registry = read_json(
                path=issue_copy.parents[1]
                / "config"
                / "source_strategy_registry.json"
            )
            registry["families"]["financial_statement"][
                "forbidden_production_literals"
            ].append("MIGRATED_PRODUCTION")
            rebind_registry(issue_copy=issue_copy, registry=registry)
            with self.assertRaisesRegex(
                SourceStrategyError, "current migration state",
            ):
                load_source_strategy_registry(repo_root=issue_copy.parents[1])

    def test_generic_word_cannot_enter_family_literal_list(self) -> None:
        """Reject an overbroad semantic-lint word after complete rebinding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            registry = read_json(
                path=issue_copy.parents[1]
                / "config"
                / "source_strategy_registry.json"
            )
            registry["families"]["risk_legal_text"][
                "forbidden_production_literals"
            ].append("risk")
            rebind_registry(issue_copy=issue_copy, registry=registry)
            with self.assertRaisesRegex(
                SourceStrategyError, "Generic words",
            ):
                load_source_strategy_registry(repo_root=issue_copy.parents[1])

    def test_metric_cannot_own_a_publication_state_field(self) -> None:
        """Reject metric-level migration state even with an innocuous value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            registry = read_json(
                path=issue_copy.parents[1]
                / "config"
                / "source_strategy_registry.json"
            )
            mutated = copy.deepcopy(registry)
            mutated["metrics"]["A01"]["publication_state"] = "INACTIVE"
            rebind_registry(issue_copy=issue_copy, registry=mutated)
            with self.assertRaisesRegex(
                SourceStrategyError, "metric route fields are not exact",
            ):
                load_source_strategy_registry(repo_root=issue_copy.parents[1])


if __name__ == "__main__":
    unittest.main()
