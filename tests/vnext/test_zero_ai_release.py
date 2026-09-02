"""Verify committed Issue #15 zero-AI R1 and cumulative R2 evidence."""

from __future__ import annotations

import csv
import io
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import zero_ai_r2
from vnext.canonical import content_hash, sha256_file, strict_json_file
from vnext.publication import PublicationError, PublicationView
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import ZERO_AI_FORMAL_MANIFEST
from vnext.publication import verify_publication_bundle
from vnext.projection_independence import build_projection_independence_receipt
from vnext.public_projection import METRICS_FIELDS, assemble_public_rows
from vnext.public_projection import compare_public_rows, render_public_rows
from vnext.zero_ai_release import _coordinate_periods, _freeze_r1_runs
from vnext.zero_ai_release import _r1_source_plan, _registry_rows


ZERO_COUNTERS = {
    "mock_transport_invocation_count": 0,
    "paid_model_provider_call_count": 0,
    "real_model_provider_egress_count": 0,
}
ACTIVE_R3_PUBLICATION_ID = (
    "publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8"
)
EXACT_R2_PUBLICATION_ID = (
    "publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f"
)


class ZeroAiReleaseTest(unittest.TestCase):
    """Prove R1/R2 history beneath the fully verified active R3 bundle."""

    @classmethod
    def setUpClass(cls) -> None:
        """Pin one verified active R3 -> R2 -> R1 publication chain."""
        cls.active_view = PublicationView.open(publication_root=REPO_ROOT)
        if cls.active_view.publication_id != ACTIVE_R3_PUBLICATION_ID:
            raise AssertionError("Active publication is not exact R3")
        r2_id = str(cls.active_view.manifest["previous_publication_id"])
        if r2_id != EXACT_R2_PUBLICATION_ID:
            raise AssertionError("Active R3 predecessor is not exact R2")
        r2_dir = REPO_ROOT / "outputs" / "publications" / r2_id
        r2_manifest = verify_publication_bundle(bundle_dir=r2_dir)
        cls.r2_view = PublicationView(
            publication_id=r2_id,
            bundle_dir=r2_dir,
            manifest=r2_manifest,
        )
        r1_id = str(r2_manifest["previous_publication_id"])
        r1_dir = REPO_ROOT / "outputs" / "publications" / r1_id
        r1_manifest = verify_publication_bundle(bundle_dir=r1_dir)
        cls.r1_view = PublicationView(
            publication_id=r1_id,
            bundle_dir=r1_dir,
            manifest=r1_manifest,
        )

    def _active_and_r1(self) -> tuple[PublicationView, PublicationView]:
        """Return the pinned active R3 view and verified R1 ancestor."""
        return self.active_view, self.r1_view

    def test_r2_financial_producer_has_no_legacy_semantic_input(self) -> None:
        """Ban old rows, evidence, and expected values from financial build."""
        signature = inspect.signature(zero_ai_r2._deterministic_metric_graph)
        self.assertEqual(
            ["context", "company_id", "metric_id"],
            list(signature.parameters),
        )
        source = inspect.getsource(zero_ai_r2._deterministic_metric_graph)
        for forbidden in (
            "legacy_row", "legacy_evidence", "value_normalized", "value_raw",
        ):
            self.assertNotIn(forbidden, source)
        self.assertFalse(
            hasattr(zero_ai_r2, "_selected_component_claims")
        )

    def test_r1_public_rows_render_without_legacy_rows(self) -> None:
        """Render R1 first, then use frozen legacy only as field oracle."""
        _active, r1_view = self._active_and_r1()
        legacy_dir = (
            REPO_ROOT / "outputs" / "publications"
            / str(r1_view.manifest["previous_publication_id"])
        )
        plan, companies, _proofs, projection_claims = _r1_source_plan(
            repo_root=REPO_ROOT, legacy_snapshot_dir=legacy_dir,
        )
        with tempfile.TemporaryDirectory() as directory:
            coordinates, _files, records = _freeze_r1_runs(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory),
                plan=plan,
                run_companies=companies,
            )
        coordinates = _coordinate_periods(
            coordinates=coordinates, run_companies=companies,
        )
        rendered = render_public_rows(
            repo_root=REPO_ROOT,
            metric_ids=("B01", "B03"),
            registry_rows=_registry_rows(repo_root=REPO_ROOT),
            coordinates=coordinates,
            records=records,
            source_references=plan["source_references"],
            filing_inventory=[],
            projection_claims=projection_claims,
        )
        legacy_rows = list(csv.DictReader(
            io.StringIO((legacy_dir / "metrics_matrix.csv").read_text(
                encoding="utf-8"
            ))
        ))
        oracle = [
            row for row in legacy_rows if row["metric_id"] in {"B01", "B03"}
        ]
        oracle_keys = {
            (row["company"], row["metric_id"]) for row in oracle
        }
        compatibility = compare_public_rows(
            rendered_rows=[
                row for row in rendered["rows"]
                if (row["company"], row["metric_id"]) in oracle_keys
            ],
            frozen_legacy_rows=oracle,
            approved_deltas=rendered["approved_deltas"],
            approved_delta_authority_hash=rendered[
                "approved_delta_authority_hash"
            ],
        )
        self.assertEqual(20, len(rendered["rows"]))
        self.assertEqual(18, compatibility["compared_key_count"])
        self.assertEqual(18 * len(METRICS_FIELDS), compatibility[
            "compared_field_count"
        ])
        self.assertEqual([], compatibility["unexpected_delta_exact_set"])
        self.assertEqual([], compatibility["approved_delta_exact_set"])

    def test_r2_projection_and_producers_survive_legacy_canary(self) -> None:
        """Generate 220 rows before a separate 141x20 legacy comparison."""
        _active, r1_view = self._active_and_r1()
        legacy_id = str(r1_view.manifest["previous_publication_id"])
        legacy_dir = REPO_ROOT / "outputs" / "publications" / legacy_id
        legacy_bytes = (legacy_dir / "metrics_matrix.csv").read_bytes()
        legacy_rows = list(csv.DictReader(
            io.StringIO(legacy_bytes.decode("utf-8"))
        ))
        marker = json.loads(r1_view.read_bytes(
            relative_path=ZERO_AI_FORMAL_MANIFEST
        ).decode("utf-8"))
        predecessor = {
            "active_view": r1_view,
            "r1_marker": marker,
            "legacy_predecessor_id": legacy_id,
            "legacy_predecessor_dir": legacy_dir,
            "legacy_metrics_bytes": legacy_bytes,
            "legacy_metrics": legacy_rows,
        }
        with patch(
            "vnext.zero_ai_r2._legacy_publication_context",
            return_value=predecessor,
        ):
            context = zero_ai_r2.build_r2_source_plan(repo_root=REPO_ROOT)
        producer_context = dict(context)
        for field in (
            "legacy_metrics", "legacy_metrics_bytes", "legacy_events",
            "legacy_events_sha256",
        ):
            producer_context.pop(field)
        graph = zero_ai_r2.build_r2_execution_graph(
            repo_root=REPO_ROOT, source_context=producer_context,
        )
        rendered = render_public_rows(
            repo_root=REPO_ROOT,
            metric_ids=zero_ai_r2.R2_METRIC_IDS,
            registry_rows=context["registry_rows"],
            coordinates=graph["coordinates"],
            records=(
                zero_ai_r2._r1_projection_records(active_view=r1_view)
                + [dict(record) for record in graph["records"]]
            ),
            source_references=context["plan"]["source_references"],
            filing_inventory=context["public_filing_inventory"],
            projection_claims=graph["projection_claims"],
        )
        event_compatibility = zero_ai_r2.compare_event_key_parity(
            source_context=context, graph=graph,
        )
        oracle = [
            row for row in legacy_rows
            if row["metric_id"] in set(zero_ai_r2.R2_METRIC_IDS)
        ]
        oracle_keys = {
            (row["company"], row["metric_id"]) for row in oracle
        }
        compatibility = compare_public_rows(
            rendered_rows=[
                row for row in rendered["rows"]
                if (row["company"], row["metric_id"]) in oracle_keys
            ],
            frozen_legacy_rows=oracle,
            approved_deltas=rendered["approved_deltas"],
            approved_delta_authority_hash=rendered[
                "approved_delta_authority_hash"
            ],
        )
        predecessor_rows = list(csv.DictReader(io.StringIO(
            r1_view.read_bytes(relative_path="metrics_matrix.csv").decode(
                "utf-8"
            )
        )))
        public_rows = assemble_public_rows(
            predecessor_rows=predecessor_rows,
            rendered_rows=rendered["rows"],
            metric_ids=zero_ai_r2.R2_METRIC_IDS,
        )
        new_rows = [
            row for row in rendered["rows"]
            if (row["company"], row["metric_id"]) not in oracle_keys
        ]
        key_set = sorted(
            (
                {"company": row["company"], "metric_id": row["metric_id"]}
                for row in public_rows
            ),
            key=lambda row: (row["company"], row["metric_id"]),
        )
        self.assertEqual(220, len(graph["coordinates"]))
        self.assertEqual(220, len(rendered["rows"]))
        self.assertEqual(141, compatibility["compared_key_count"])
        self.assertEqual(141 * len(METRICS_FIELDS), compatibility[
            "compared_field_count"
        ])
        self.assertEqual([], compatibility["unexpected_delta_exact_set"])
        self.assertEqual([], compatibility["approved_delta_exact_set"])
        self.assertEqual(79, len(new_rows))
        self.assertTrue(all(
            row["status"] == "N_A_STRUCTURAL"
            and row["source_class"] == "STRUCTURAL"
            for row in new_rows
        ))
        self.assertEqual(309, len(public_rows))
        self.assertEqual(
            "sha256:33b2a81ac6507b33a37509189fb8eb7fae87fa25c2f441bc4b4bca6705f56fab",
            content_hash(value=key_set),
        )
        self.assertEqual(
            "ZERO_AI_EVENT_KEY_COMPATIBILITY_RECEIPT",
            event_compatibility["record_type"],
        )
        independence = build_projection_independence_receipt(
            repo_root=REPO_ROOT,
        )
        self.assertEqual("PASSED", independence["status"])

    def test_r1_active_rollback_restore_and_read_back_are_bound(self) -> None:
        """Verify final B, predecessor A, seven receipt roles, and mirrors."""
        view, r1_view = self._active_and_r1()
        marker = json.loads(
            r1_view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode(
                "utf-8"
            )
        )
        self.assertEqual("R1", marker["release_stage"])
        self.assertEqual("PASSED", marker["status"])
        self.assertEqual(ZERO_COUNTERS, marker["counters"])
        self.assertEqual(["B01", "B03"], marker["cumulative_metric_ids"])
        self.assertEqual(20, marker["result_coordinate_count"])
        self.assertEqual(18, marker["replaced_legacy_row_count"])
        self.assertEqual(2, marker["new_public_key_count"])
        self.assertEqual(232, marker["public_matrix_row_count"])

        predecessor_dir = (
            REPO_ROOT
            / "outputs"
            / "publications"
            / marker["previous_publication_id"]
        )
        predecessor = verify_publication_bundle(bundle_dir=predecessor_dir)
        self.assertIsNone(predecessor["previous_publication_id"])
        self.assertTrue(
            (predecessor_dir / "internal/legacy_baseline_import.json").is_file()
        )

        index = json.loads(
            (
                REPO_ROOT
                / "outputs"
                / "zero_ai_release_receipts"
                / "r1"
                / "index.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual("PASSED", index["status"])
        self.assertEqual(ZERO_COUNTERS, index["counters"])
        self.assertEqual(
            {
                "active_terminal",
                "initial_read_back",
                "predecessor",
                "restore_read_back",
                "restore_terminal",
                "retirement",
                "rollback_terminal",
                "successor_publication",
            },
            set(index["receipts"]),
        )
        for binding in index["receipts"].values():
            path = REPO_ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

        for relative, mirror_relative in ROOT_MIRROR_RELATIVE_PATHS.items():
            self.assertEqual(
                view.read_bytes(relative_path=relative),
                (REPO_ROOT / mirror_relative).read_bytes(),
            )

    def test_r1_public_key_set_and_structural_additions_are_exact(self) -> None:
        """Prove 232 unique keys and only two new structural coordinates."""
        _active, view = self._active_and_r1()
        marker = json.loads(
            view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode("utf-8")
        )
        rows = list(
            csv.DictReader(
                io.StringIO(
                    view.read_bytes(relative_path="metrics_matrix.csv").decode(
                        "utf-8"
                    )
                )
            )
        )
        keys = sorted(
            (
                {"company": row["company"], "metric_id": row["metric_id"]}
                for row in rows
            ),
            key=lambda row: (row["company"], row["metric_id"]),
        )
        self.assertEqual(232, len(keys))
        self.assertEqual(232, len({(row["company"], row["metric_id"]) for row in keys}))
        self.assertEqual(marker["public_key_set_hash"], content_hash(value=keys))
        additions = [
            row
            for row in rows
            if row["company"] == "JPMorgan Chase"
            and row["metric_id"] in {"B01", "B03"}
        ]
        self.assertEqual(2, len(additions))
        self.assertTrue(
            all(
                row["status"] == "N_A_STRUCTURAL"
                and row["source_class"] == "STRUCTURAL"
                and not row["value"]
                for row in additions
            )
        )

    def test_r2_active_key_union_compatibility_and_retirement_are_bound(
        self,
    ) -> None:
        """Prove 22x10 coordinates, 309 keys, receipts, and zero calls."""
        view = self.r2_view
        r1_view = self.r1_view
        self.assertEqual(
            view.publication_id,
            self.active_view.manifest["previous_publication_id"],
        )
        marker = json.loads(
            view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode("utf-8")
        )
        self.assertEqual("R2", marker["release_stage"])
        self.assertEqual("PASSED", marker["status"])
        self.assertEqual(ZERO_COUNTERS, marker["counters"])
        self.assertEqual(22, len(marker["cumulative_metric_ids"]))
        self.assertEqual(220, marker["result_coordinate_count"])
        self.assertEqual(141, marker["replaced_legacy_row_count"])
        self.assertEqual(79, marker["new_public_key_count"])
        self.assertEqual(309, marker["public_matrix_row_count"])
        self.assertEqual(r1_view.publication_id, marker["previous_publication_id"])
        self.assertEqual(
            ["IMMUTABLE_ATTEMPT", "IMMUTABLE_GIT_BLOB"],
            marker["source_locator_classes"],
        )

        rows = list(
            csv.DictReader(
                io.StringIO(
                    view.read_bytes(relative_path="metrics_matrix.csv").decode(
                        "utf-8"
                    )
                )
            )
        )
        legacy_id = str(r1_view.manifest["previous_publication_id"])
        legacy_rows = list(
            csv.DictReader(
                io.StringIO(
                    (
                        REPO_ROOT
                        / "outputs"
                        / "publications"
                        / legacy_id
                        / "metrics_matrix.csv"
                    ).read_text(encoding="utf-8")
                )
            )
        )
        legacy_keys = {
            (row["company"], row["metric_id"]) for row in legacy_rows
        }
        additions = [
            row for row in rows
            if (row["company"], row["metric_id"]) not in legacy_keys
        ]
        self.assertEqual(309, len(rows))
        self.assertEqual(79, len(additions))
        self.assertTrue(
            all(
                row["status"] == "N_A_STRUCTURAL"
                and row["source_class"] == "STRUCTURAL"
                and not row["value"]
                for row in additions
            )
        )
        keys = sorted(
            (
                {"company": row["company"], "metric_id": row["metric_id"]}
                for row in rows
            ),
            key=lambda row: (row["company"], row["metric_id"]),
        )
        self.assertEqual(marker["public_key_set_hash"], content_hash(value=keys))

        index = json.loads(
            (
                REPO_ROOT
                / "outputs"
                / "zero_ai_release_receipts"
                / "r2"
                / "index.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(ZERO_COUNTERS, index["counters"])
        self.assertEqual(
            {
                "active_terminal",
                "immutable_read_back",
                "predecessor_r1",
                "retirement",
                "strict_compatibility",
                "successor_publication",
            },
            set(index["receipts"]),
        )
        for binding in index["receipts"].values():
            path = REPO_ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

        graph = json.loads(
            view.read_bytes(
                relative_path="internal/deterministic_execution_graph.json"
            ).decode("utf-8")
        )
        self.assertEqual("R2", graph["release_stage"])
        self.assertEqual(10, len(graph["event_key_parity"]))
        inventory = json.loads(
            (
                REPO_ROOT
                / "requirements"
                / "issue_15_v1"
                / "legacy_semantic_producer_inventory.json"
            ).read_text(encoding="utf-8")
        )
        producer_ids = {row["producer_id"] for row in inventory["producers"]}
        retirement_binding = index["receipts"]["retirement"]
        retirement = json.loads(
            (REPO_ROOT / retirement_binding["path"]).read_text(encoding="utf-8")
        )
        self.assertTrue(retirement["retired_producer_scopes"])
        self.assertTrue(
            {
                row["producer_id"]
                for row in retirement["retired_producer_scopes"]
            }.issubset(producer_ids)
        )

    def test_r1_marker_tamper_fails_closed(self) -> None:
        """Reject a forged nonzero egress counter in an otherwise copied B."""
        view = self.r1_view
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "bundle"
            shutil.copytree(view.bundle_dir, copied)
            marker_path = copied / ZERO_AI_FORMAL_MANIFEST
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["counters"]["real_model_provider_egress_count"] = 1
            body = {
                field: marker[field]
                for field in marker
                if field != "zero_ai_release_receipt_id"
            }
            marker["zero_ai_release_receipt_id"] = content_hash(value=body)
            marker_path.write_text(
                json.dumps(
                    marker,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(PublicationError):
                verify_publication_bundle(bundle_dir=copied)


class ZeroAiReleaseFastTest(unittest.TestCase):
    """Check the active edge while fully verifying only its R2 predecessor."""

    def test_r2_predecessor_bundle_fast_smoke(self) -> None:
        """Bind the active R3 manifest edge, then fully verify exact R2."""
        pointer = strict_json_file(
            path=REPO_ROOT / "outputs" / "active_publication.json"
        )
        self.assertIsInstance(pointer, dict)
        self.assertEqual(ACTIVE_R3_PUBLICATION_ID, pointer["publication_id"])
        self.assertEqual(
            EXACT_R2_PUBLICATION_ID, pointer["previous_publication_id"]
        )

        active_dir = (
            REPO_ROOT
            / "outputs"
            / "publications"
            / str(pointer["publication_id"])
        )
        active_manifest_path = active_dir / "publication_manifest.json"
        self.assertEqual(
            pointer["bundle_manifest_sha256"],
            sha256_file(path=active_manifest_path),
        )
        active_manifest = strict_json_file(path=active_manifest_path)
        self.assertIsInstance(active_manifest, dict)
        self.assertEqual(pointer["publication_id"], active_manifest["publication_id"])
        self.assertEqual(
            pointer["previous_publication_id"],
            active_manifest["previous_publication_id"],
        )

        r2_dir = (
            REPO_ROOT
            / "outputs"
            / "publications"
            / str(active_manifest["previous_publication_id"])
        )
        r2_manifest = verify_publication_bundle(bundle_dir=r2_dir)
        r2_view = PublicationView(
            publication_id=EXACT_R2_PUBLICATION_ID,
            bundle_dir=r2_dir,
            manifest=r2_manifest,
        )
        marker = json.loads(
            r2_view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode(
                "utf-8"
            )
        )
        self.assertEqual("R2", marker["release_stage"])
        self.assertEqual("PASSED", marker["status"])
        self.assertEqual(309, marker["public_matrix_row_count"])
        self.assertEqual(
            r2_manifest["previous_publication_id"],
            marker["previous_publication_id"],
        )


if __name__ == "__main__":
    unittest.main()
