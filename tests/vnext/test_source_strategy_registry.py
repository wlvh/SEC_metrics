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
from vnext.canonical import sha256_file
from vnext.publication import PublicationView
from vnext.source_strategy import ALLOWED_SOURCE_MODES
from vnext.source_strategy import GENERIC_FORBIDDEN_LITERAL_DENYLIST
from vnext.source_strategy import SourceStrategyError
from vnext.source_strategy import load_issue15_release_plan
from vnext.source_strategy import load_source_strategy_registry


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

    plan_path = repository_root / "config" / "issue_15_release_plan.json"
    plan = read_json(path=plan_path)
    plan["authority_hashes"]["source_strategy_registry_sha256"] = sha256_file(
        path=registry_path
    )
    write_json(path=plan_path, value=plan)

    baseline_path = issue_copy / "baseline_manifest.json"
    baseline = read_json(path=baseline_path)
    registry_binding = baseline["runtime_authority_files"][
        "config/source_strategy_registry.json"
    ]
    registry_binding["sha256"] = sha256_file(path=registry_path)
    registry_binding["size"] = registry_path.stat().st_size
    plan_binding = baseline["runtime_authority_files"][
        "config/issue_15_release_plan.json"
    ]
    plan_binding["sha256"] = sha256_file(path=plan_path)
    plan_binding["size"] = plan_path.stat().st_size
    write_json(path=baseline_path, value=baseline)


class SourceStrategyRegistryTest(unittest.TestCase):
    """Prove WB-2 exact coverage, schema, and state separation."""

    def test_registry_covers_exact_39_without_migration_state(self) -> None:
        """Load every route and prove only ReleasePlan owns current state."""
        loaded = load_source_strategy_registry(repo_root=REPO_ROOT)
        plan = load_issue15_release_plan(repo_root=REPO_ROOT)
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
        self.assertEqual(["B01", "B03"], plan["cumulative_metric_ids"])
        self.assertEqual([], plan["qualification_matrix_subset"])

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
            matrix_path = (
                REPO_ROOT
                / "outputs"
                / "publications"
                / str(predecessor)
                / "metrics_matrix.csv"
            )
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
