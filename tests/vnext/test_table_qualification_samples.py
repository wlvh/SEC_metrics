"""Verify matrix-owned qualification phases and exact request identities."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sec_http import parse_request_log_rows, request_log_attempt_id
from tests.vnext.common import REPO_ROOT
from vnext import ai_adapter
from vnext import qualification as qualification_module
from vnext import workflow as workflow_module
from vnext.canonical import strict_json_file
from vnext.reader_input import build_reader_input_manifest
from vnext.reader_input import prepare_live_reader_request
from vnext.reader_input import prepare_reader_request
from vnext.sources import load_raw_blob_bytes
from vnext.sources import raw_blob_record
from vnext.sources import source_reference_record
from vnext.table_grid import build_table_grid
from vnext.traits import repository_company_ciks
from vnext.qualification import _qualification_sample_authority
from vnext.qualification import _qualification_sample_measurement
from vnext.qualification import QualificationError
from vnext.requirements import load_requirement_snapshot
from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_task_contracts import resolve_table_task_contract


class TableQualificationSamplesTest(unittest.TestCase):
    """Keep source selection phase-based, exact, and network-free at plan time."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load current authority and the last dual-attestation freeze body."""
        cls.requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_15_v1",
        )
        cls.entry = load_table_qualification_matrix(
            repo_root=REPO_ROOT, family_id="lodging_kpi_table",
        )["entries"]["lodging_kpi_table"]
        pointer = strict_json_file(
            path=REPO_ROOT / "config/table_qualification_freeze.json",
        )
        cls.freeze = strict_json_file(
            path=REPO_ROOT / pointer["receipt_path"],
        )

    def _measurement(self, *, phase: str, task_id: str) -> dict:
        """Build one exact offline phase/task request."""
        sample = _qualification_sample_authority(
            repo_root=REPO_ROOT,
            matrix_entry=self.entry,
            qualification_phase=phase,
            qualification_ordinal=1,
        )
        task = resolve_table_task_contract(
            repo_root=REPO_ROOT,
            task_contract_id=task_id,
            family_id="lodging_kpi_table",
        )
        return _qualification_sample_measurement(
            repo_root=REPO_ROOT,
            family_id="lodging_kpi_table",
            task_contract=task,
            matrix_entry=self.entry,
            sample=sample,
            requirement=self.requirement,
            freeze=self.freeze,
        )

    def test_matrix_phases_resolve_exact_sources_and_requests(self) -> None:
        """Bind second, holdout, and fresh sources without caller locators."""
        expected = {
            ("SECOND_LAYOUT", "lodging_occupancy_table_v2"): (
                "marriott_international", 388755,
                "6e95c0225c147246346c787e25f161441a6d9dbd16fa08ffdc195c691"
                "41bcaa8",
                "BLOCKED",
            ),
            ("SECOND_LAYOUT", "lodging_revpar_table_v2"): (
                "marriott_international", 388746,
                "0ff01b4a8e65ed57a88a7094f6b875289fddb426ccde1c138c8a02af"
                "8396b920",
                "BLOCKED",
            ),
            ("POST_FREEZE_HOLDOUT", "lodging_occupancy_table_v2"): (
                "hyatt_hotels", 206778,
                "27d25c6dcf0d1a88dc5edc2d73acd12a85d3a4d326237e3172d528dc5400500d",
                "BLOCKED",
            ),
            ("POST_FREEZE_HOLDOUT", "lodging_revpar_table_v2"): (
                "hyatt_hotels", 206769,
                "20127563885ecc4443e1e5da2e8283730e36367e57297800a01efb434eb710fc",
                "BLOCKED",
            ),
            ("FRESH_STABILITY", "lodging_occupancy_table_v2"): (
                "marriott_international", 394837,
                "da4f47feca0046758c8d0375333fb6b16eac675ec1c5a0812eb9d2e47c01ec7b",
                "PASSED",
            ),
            ("FRESH_STABILITY", "lodging_revpar_table_v2"): (
                "marriott_international", 394828,
                "1afd27317162e441fb0812253e79e287bbb302da0fb9ddf301c887541d06e43a",
                "PASSED",
            ),
        }
        with mock.patch.object(ai_adapter, "_open_provider_request") as opener:
            for (phase, task_id), values in expected.items():
                with self.subTest(phase=phase, task_contract_id=task_id):
                    sample = _qualification_sample_authority(
                        repo_root=REPO_ROOT,
                        matrix_entry=self.entry,
                        qualification_phase=phase,
                        qualification_ordinal=1,
                    )
                    measurement = self._measurement(
                        phase=phase, task_id=task_id,
                    )
                    company, tokens, request_hash, status = values
                    self.assertEqual(
                        company,
                        sample["source_binding"]["source_declaration"][
                            "company_id"
                        ],
                    )
                    self.assertEqual(tokens, measurement["estimated_input_tokens"])
                    self.assertEqual(
                        request_hash, measurement["provider_request_body_sha256"],
                    )
                    self.assertEqual(
                        status, measurement["context_feasibility"]["status"],
                    )
        opener.assert_not_called()

    def test_replacement_second_layout_proves_scope_before_model(self) -> None:
        """Require one same-table literal closure and distinct grid geometry."""
        sample = _qualification_sample_authority(
            repo_root=REPO_ROOT,
            matrix_entry=self.entry,
            qualification_phase="SECOND_LAYOUT",
            qualification_ordinal=1,
        )
        self.assertEqual(
            "marriott-2024-sec-layout-v1",
            sample["qualification_fixture_id"],
        )
        ledger_rows = parse_request_log_rows(text=(
            REPO_ROOT / "evidence/requests_log.csv"
        ).read_text(encoding="utf-8"))
        acquisition_rows = [
            (index, row)
            for index, row in enumerate(ledger_rows)
            if row["purpose"] == "issue15_lodging_second_layout_candidate"
        ]
        self.assertEqual(1, len(acquisition_rows))
        row_index, acquisition = acquisition_rows[0]
        self.assertEqual("0", acquisition["retry_attempt"])
        self.assertTrue(acquisition["user_agent"].startswith(
            "redacted-sha256:"
        ))
        self.assertEqual(
            64,
            len(acquisition["user_agent"].removeprefix(
                "redacted-sha256:"
            )),
        )
        self.assertNotIn("@", acquisition["user_agent"])
        self.assertEqual(
            sample["source_binding"]["request_attempt_id"],
            request_log_attempt_id(row_index=row_index, row=acquisition),
        )
        source = sample["source_binding"]["source_declaration"]
        candidate = build_table_grid(
            html_bytes=(
                REPO_ROOT / source["source_repo_relative_path"]
            ).read_bytes(),
            parent_raw_asset_ids=["sha256:" + source["source_sha256"]],
            storage_uri="audit://marriott-2024-second-layout",
        )
        development = self.entry["development_source"]
        fresh = build_table_grid(
            html_bytes=(
                REPO_ROOT / development["source_repo_relative_path"]
            ).read_bytes(),
            parent_raw_asset_ids=[
                "sha256:" + development["source_sha256"]
            ],
            storage_uri="audit://marriott-2025-fresh",
        )

        def matching_tables(asset: dict) -> list[dict]:
            matches = []
            for table in asset["tables"]:
                raw_values = [
                    cell["raw_text"]
                    for row in table["rows"]
                    for cell in row["cells"]
                    if cell["is_origin"]
                ]
                normalized = [
                    cell["text"]
                    for row in table["rows"]
                    for cell in row["cells"]
                    if cell["is_origin"]
                ]
                if (
                    all(any(literal in value for value in raw_values) for literal in (
                        "Comparable Systemwide Properties", "Worldwide",
                    ))
                    and all(any(role in value for value in normalized) for role in (
                        "Occupancy", "RevPAR",
                    ))
                ):
                    matches.append(table)
            return matches

        candidate_matches = matching_tables(candidate)
        fresh_matches = matching_tables(fresh)
        self.assertEqual(1, len(candidate_matches))
        self.assertEqual(1, len(fresh_matches))
        candidate_table = candidate_matches[0]
        fresh_table = fresh_matches[0]
        self.assertEqual("table_000011", candidate_table["table_id"])
        self.assertEqual((29, 39), (
            candidate_table["row_count"], candidate_table["column_count"],
        ))
        self.assertEqual((27, 39), (
            fresh_table["row_count"], fresh_table["column_count"],
        ))
        self.assertNotEqual(
            candidate_table["grid_sha256"], fresh_table["grid_sha256"],
        )
        sentinel = strict_json_file(path=(
            REPO_ROOT
            / "fixtures/vnext/layouts/marriott-2024-sec-layout-v1/"
            "recorded_response.json"
        ))
        self.assertEqual({
            "status": "NOT_RUN",
            "reason": (
                "SOURCE_ONLY_LIVE_QUALIFICATION_FIXTURE_REQUIRES_NEW_"
                "PROVIDER_EXECUTION"
            ),
            "provider_egress_count": 0,
        }, sentinel)

    def test_invalid_phase_ordinals_fail_before_source_or_provider(self) -> None:
        """Keep layout phases single-ordinal and fresh at the D-37 count."""
        for phase, ordinal in (
            ("SECOND_LAYOUT", 2),
            ("POST_FREEZE_HOLDOUT", 2),
            ("FRESH_STABILITY", 4),
            ("UNKNOWN", 1),
        ):
            with self.subTest(phase=phase, ordinal=ordinal):
                with self.assertRaises(QualificationError):
                    _qualification_sample_authority(
                        repo_root=REPO_ROOT,
                        matrix_entry=self.entry,
                        qualification_phase=phase,
                        qualification_ordinal=ordinal,
                    )

    def test_fresh_ordinal_two_requires_every_task_ordinal_one_frozen(
        self,
    ) -> None:
        """Fail before adapter construction when the global barrier is absent."""
        tasks = [
            "lodging_occupancy_table_v2",
            "lodging_revpar_table_v2",
        ]
        requirement = {
            "effective_decisions": {
                "D-07": {
                    "choice": {
                        "live_qualification_authorized": True,
                        "live_qualification_scope": {
                            "authorized_family_ids": ["lodging_kpi_table"],
                            "authorized_task_contract_ids": tasks,
                            "financial_qualification_authorized": False,
                        },
                    },
                },
            },
        }
        freeze = {"qualification_cycle_id": "sha256:" + "a" * 64}
        holdout = [{"task_contract_id": task_id} for task_id in tasks]
        with mock.patch.object(
            qualification_module,
            "load_requirement_snapshot",
            return_value=requirement,
        ), mock.patch.object(
            qualification_module,
            "require_table_qualification_freeze",
            return_value=freeze,
        ), mock.patch.object(
            qualification_module,
            "validate_table_production_semantic_freeze",
        ), mock.patch.object(
            qualification_module,
            "_table_phase_terminal_rows",
            side_effect=(holdout, []),
        ), mock.patch.object(
            qualification_module,
            "build_table_qualification_transport_adapter",
        ) as opener:
            with self.assertRaises(QualificationError) as raised:
                qualification_module.execute_table_qualification_task(
                    repo_root=REPO_ROOT,
                    family_id="lodging_kpi_table",
                    task_contract_id="lodging_occupancy_table_v2",
                    qualification_phase="FRESH_STABILITY",
                    qualification_ordinal=2,
                    target_period={},
                    owner_token="sequence-regression",
                )
        self.assertEqual(
            "TABLE_QUALIFICATION_PRIOR_ORDINAL_REQUIRED",
            raised.exception.code,
        )
        opener.assert_not_called()

    def test_prior_fresh_open_run_is_not_a_frozen_prerequisite(self) -> None:
        """Treat an existing but non-FROZEN prior Run as a sequence blocker."""
        cycle_id = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = (
                root / qualification_module.TABLE_QUALIFICATION_CYCLE_ROOT
                / cycle_id.split(":", maxsplit=1)[1] / "runs" / "open-run"
            )
            run_dir.mkdir(parents=True)
            manifest = {
                "status": "OPEN",
                "qualification_authorization": {
                    "family_id": "lodging_kpi_table",
                    "qualification_phase": "FRESH_STABILITY",
                    "qualification_ordinal": 1,
                },
            }
            with mock.patch.object(
                qualification_module,
                "load_run_for_status",
                return_value=(manifest, [], []),
            ):
                with self.assertRaises(QualificationError) as raised:
                    qualification_module._table_phase_terminal_rows(
                        repo_root=root,
                        qualification_cycle_id=cycle_id,
                        family_id="lodging_kpi_table",
                        qualification_phase="FRESH_STABILITY",
                        qualification_ordinals=(1,),
                    )
        self.assertEqual(
            "TABLE_QUALIFICATION_SEQUENCE_INVALID",
            raised.exception.code,
        )

    def test_layout_source_uses_opaque_qualification_cik_authority(
        self,
    ) -> None:
        """Permit the exact external SEC fixture without expanding registry."""
        fixture = qualification_module._matrix_fixture_source_binding(
            repo_root=REPO_ROOT,
            fixture_id="hyatt-2025-sec-holdout-v2",
        )
        source = {
            key: value for key, value in fixture.items()
            if key in qualification_module._SOURCE_BINDING_FIELDS
        }
        binding = {"source_binding": source}
        authorization = qualification_module.TableQualificationAuthorization(
            binding=binding,
            capability=(
                qualification_module._QUALIFICATION_AUTHORIZATION_CAPABILITY
            ),
        )
        declaration = source["source_declaration"]
        with mock.patch.object(
            qualification_module,
            "_rebuild_authorization_binding",
            return_value=binding,
        ):
            allowed_ciks = (
                qualification_module.qualification_authorized_company_ciks(
                    repo_root=REPO_ROOT,
                    authorization=authorization,
                    company_id=str(declaration["company_id"]),
                )
            )
        raw = raw_blob_record(
            repo_root=REPO_ROOT,
            repo_relative_path=str(declaration["source_repo_relative_path"]),
            media_type=str(fixture["source_media_type"]),
        )
        with mock.patch.object(
            workflow_module,
            "repository_company_ciks",
            side_effect=AssertionError("production registry fallback reached"),
        ):
            proof = workflow_module._validate_live_source_authority(
                repo_root=REPO_ROOT,
                company_id=str(declaration["company_id"]),
                raw_blob=raw,
                source_url=str(source["source_url"]),
                accession=str(declaration["accession"]),
                document_name=str(declaration["document_name"]),
                source_role=str(source["source_role"]),
                request_attempt_id=str(source["request_attempt_id"]),
                allowed_ciks=allowed_ciks,
            )
        self.assertEqual(source["request_attempt_id"], proof["request_attempt_id"])
        with self.assertRaises(workflow_module.LiveSourceAuthorityError):
            workflow_module._validate_live_source_authority(
                repo_root=REPO_ROOT,
                company_id=str(declaration["company_id"]),
                raw_blob=raw,
                source_url=str(source["source_url"]),
                accession=str(declaration["accession"]),
                document_name=str(declaration["document_name"]),
                source_role=str(source["source_role"]),
                request_attempt_id=str(source["request_attempt_id"]),
                allowed_ciks=["1"],
            )

    def test_adapter_replays_matrix_owned_layout_cik_without_registry_row(
        self,
    ) -> None:
        """Replay the exact Hyatt fixture while preserving ten-company registry."""
        fixture = qualification_module._matrix_fixture_source_binding(
            repo_root=REPO_ROOT,
            fixture_id="hyatt-2025-sec-holdout-v2",
        )
        source = {
            key: value for key, value in fixture.items()
            if key in qualification_module._SOURCE_BINDING_FIELDS
        }
        declaration = source["source_declaration"]
        registry_text = (REPO_ROOT / "config/company_registry.csv").read_text(
            encoding="utf-8",
        )
        self.assertNotIn(str(declaration["company_id"]), registry_text)
        self.assertEqual(
            ["1468174"],
            repository_company_ciks(
                repo_root=REPO_ROOT,
                company_id=str(declaration["company_id"]),
            ),
        )
        raw = raw_blob_record(
            repo_root=REPO_ROOT,
            repo_relative_path=str(declaration["source_repo_relative_path"]),
            media_type=str(fixture["source_media_type"]),
        )
        reference = source_reference_record(
            raw_blob=raw,
            company_id=str(declaration["company_id"]),
            source_url=str(source["source_url"]),
            accession=str(declaration["accession"]),
            document_name=str(declaration["document_name"]),
            source_role=str(source["source_role"]),
            request_attempt_id=str(source["request_attempt_id"]),
        )
        asset = build_table_grid(
            html_bytes=load_raw_blob_bytes(repo_root=REPO_ROOT, raw_blob=raw),
            parent_raw_asset_ids=[str(raw["raw_asset_id"])],
            storage_uri="artifacts/vnext/derived/test-hyatt.json",
        )
        manifest = build_reader_input_manifest(
            derived_asset=asset,
            source_reference_ids=[str(reference["source_reference_id"])],
        )
        prepared = prepare_reader_request(
            manifest=manifest,
            derived_asset=asset,
            repo_root=REPO_ROOT,
            task_contract_id="lodging_occupancy_table_v2",
        )
        live = prepare_live_reader_request(
            prepared_request=prepared,
            raw_blob=raw,
            source_reference=reference,
            derived_asset=asset,
            reader_manifest=manifest,
            disclosure_spec_path="catalog/table_task_contracts.json",
            immutable_source_repo_relative_path=str(
                declaration["source_repo_relative_path"]
            ),
        )
        rebuilt = ai_adapter._validate_live_prepared_request(
            prepared_request=live,
        )
        self.assertEqual(prepared, rebuilt)

    def test_production_freeze_binds_second_layout_and_ledger_prefix(self) -> None:
        """Require two FROZEN tasks and reject later semantic-tree drift."""
        cycle_id = "sha256:" + "a" * 64
        task_ids = [
            "lodging_occupancy_table_v2",
            "lodging_revpar_table_v2",
        ]
        rows = [
            {
                "task_contract_id": task_id,
                "qualification_phase": "SECOND_LAYOUT",
                "qualification_ordinal": 1,
                "qualification_terminal_id": "sha256:" + str(index) * 64,
                "qualification_task_plan_id": "sha256:" + str(index + 2) * 64,
                "provider_request_body_sha256": str(index + 4) * 64,
                "source_binding_hash": "sha256:" + str(index + 6) * 64,
                "run_id": "run:test:{}".format(index),
                "qualification_evidence_ids": [
                    "sha256:" + str(index + 7) * 64
                ],
                "result_ids": ["result:test:{}".format(index)],
            }
            for index, task_id in enumerate(task_ids)
        ]
        freeze = {
            "qualification_cycle_id": cycle_id,
            "receipt_id": "sha256:" + "b" * 64,
            "provider_ledger_before": {"path": "ledger.jsonl"},
        }
        requirement = {
            "effective_decisions": {
                "D-07": {
                    "choice": {
                        "live_qualification_scope": {
                            "authorized_task_contract_ids": task_ids,
                            "post_freeze_holdout_fixture_id": (
                                "hyatt-2025-sec-holdout-v2"
                            ),
                        }
                    }
                }
            }
        }
        tree = {
            "semantic_tree_id": "sha256:" + "c" * 64,
            "files": {"scripts/example.py": {"sha256": "d" * 64, "size": 1}},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ledger.jsonl").write_bytes(b"{}\n{}\n")
            with mock.patch.object(
                qualification_module,
                "require_table_qualification_freeze",
                return_value=freeze,
            ), mock.patch.object(
                qualification_module,
                "load_requirement_snapshot",
                return_value=requirement,
            ), mock.patch.object(
                qualification_module,
                "_table_phase_terminal_rows",
                return_value=rows,
            ), mock.patch.object(
                qualification_module,
                "production_semantic_tree",
                return_value=tree,
            ):
                receipt = qualification_module.write_table_production_semantic_freeze(
                    repo_root=root,
                    family_id="lodging_kpi_table",
                    frozen_at_utc="2026-08-25T13:00:00Z",
                )
                validated = (
                    qualification_module.validate_table_production_semantic_freeze(
                        repo_root=root,
                        family_id="lodging_kpi_table",
                    )
                )
                self.assertEqual(receipt["receipt_id"], validated["receipt_id"])
                self.assertEqual(2, validated[
                    "pre_holdout_qualification_ledger_prefix"
                ]["row_count"])
                with mock.patch.object(
                    qualification_module,
                    "production_semantic_tree",
                    return_value={**tree, "semantic_tree_id": "sha256:" + "e" * 64},
                ):
                    with self.assertRaises(QualificationError):
                        qualification_module.validate_table_production_semantic_freeze(
                            repo_root=root,
                            family_id="lodging_kpi_table",
                        )


if __name__ == "__main__":
    unittest.main()
