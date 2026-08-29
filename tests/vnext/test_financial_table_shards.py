"""Internal financial shard Candidate, Evidence, and Review closure tests."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest import mock

from tests.vnext.common import REPO_ROOT, compiled_specs, reader_response
from tests.vnext.common import fixed_clock, reviewed_fixture, sample_asset
from vnext import qualification
from vnext.ai_adapter import AIAdapterError, READER_SHARD_OUTPUT_JSON_SCHEMA
from vnext.ai_adapter import build_recorded_adapter, run_ai_attempt
from vnext.canonical import canonical_json_bytes, content_hash
from vnext.evidence import check_evidence
from vnext.reader import validate_reader_output
from vnext.reader_input import build_reader_input_manifest
from vnext.reader_input import build_reader_shard_payload
from vnext.reader_input import prepare_reader_request
from vnext.reader_input import prepare_reader_shard_request
from vnext.records import RecordError, validate_record
from vnext.render import build_review_context, render_review_markdown
from vnext.requirements import load_requirement_snapshot
from vnext.run_store import load_frozen_run, validate_and_freeze_run
from vnext.review import build_review_unit, create_system_review_decision
from vnext.table_payload import build_contiguous_table_shard
from vnext.table_payload import encode_compact_table_payload
from vnext.table_payload import validate_contiguous_table_shard_set
from vnext.table_grid import build_table_grid
from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.workflow import create_table_task_review_run
from vnext.workflow import finalize_reviewed_direct_results


class FinancialQualificationSourceAuthorityTest(unittest.TestCase):
    """Bind current layout sources and their pre-egress difference proof."""

    def test_matrix_resolves_exact_boa_and_citi_immutable_attempts(self) -> None:
        """Keep layout sources ledger-bound without extending the registry."""
        entry = load_table_qualification_matrix(
            repo_root=REPO_ROOT,
            family_id="financial_statement",
        )["entries"]["financial_statement"]
        expected = {
            "SECOND_LAYOUT": (
                "bank_of_america_corp",
                "c8725c7963d19cd6a2f3c1d0034b2a1068b4490124be6b6600a4db23be5ed134",
                "request:attempt:535d14a6c75aff5a20d5fdd93f3e9e6a370fb34846e6d569bcc5eb17dfd7a8db",
            ),
            "POST_FREEZE_HOLDOUT": (
                "citigroup",
                "12f5818d577a8b8022e25851849e8d6d453f05ab4f89d906f185593547fb67fe",
                "request:attempt:7bf1096d7127f7eaa2b59a9922a93167b949faed22213dc4b53369f727297eb0",
            ),
        }
        for phase, values in expected.items():
            with self.subTest(phase=phase):
                sample = qualification._qualification_sample_authority(
                    repo_root=REPO_ROOT,
                    matrix_entry=entry,
                    qualification_phase=phase,
                    qualification_ordinal=1,
                )
                declaration = sample["source_binding"]["source_declaration"]
                self.assertEqual(values[0], declaration["company_id"])
                self.assertEqual(values[1], declaration["source_sha256"])
                self.assertEqual(
                    values[2], sample["source_binding"]["request_attempt_id"],
                )
                self.assertEqual(["financial"], sample["company_traits"])
                self.assertIsNone(sample["qualification_fixture_id"])

    def test_production_freeze_plans_the_matrix_owned_citi_holdout(self) -> None:
        """Avoid carrying the lodging fixture field into financial freeze."""
        planned = qualification._planned_holdout_source_identity(
            repo_root=REPO_ROOT,
            family_id="financial_statement",
        )
        self.assertEqual("POST_FREEZE_HOLDOUT", planned["qualification_phase"])
        self.assertIsNone(planned["qualification_fixture_id"])
        self.assertEqual(
            "citigroup", planned["source_declaration"]["company_id"],
        )
        self.assertEqual(
            "12f5818d577a8b8022e25851849e8d6d453f05ab4f89d906f185593547fb67fe",
            planned["source_declaration"]["source_sha256"],
        )

    def test_layout_proof_requires_two_full_document_differences(self) -> None:
        """Reject issuer-only substitutions with equal shape or headers."""
        freeze_id = "sha256:" + ("a" * 64)
        reference_signature = {
            "derived_asset_id": "sha256:" + ("1" * 64),
            "table_count": 679,
            "expanded_cell_count": 124761,
            "ordered_column_layout_hash": "sha256:" + ("7" * 64),
            "ordered_table_shape_hash": "sha256:" + ("2" * 64),
            "ordered_header_layout_hash": "sha256:" + ("3" * 64),
        }
        sample_signature = {
            "derived_asset_id": "sha256:" + ("4" * 64),
            "table_count": 369,
            "expanded_cell_count": 200229,
            "ordered_column_layout_hash": "sha256:" + ("8" * 64),
            "ordered_table_shape_hash": "sha256:" + ("5" * 64),
            "ordered_header_layout_hash": "sha256:" + ("6" * 64),
        }
        matrix_entry = {
            "development_source": {
                "company_id": "jpmorgan_chase",
                "cik": "19617",
                "accession": "0001628280-26-008131",
                "source_sha256": "1" * 64,
            },
            "materially_different_criteria": list(
                qualification.FINANCIAL_DIFFERENT_ISSUER_LAYOUT_CRITERIA
            ),
        }
        sample = {
            "source_binding": {
                "source_declaration": {
                    "company_id": "bank_of_america_corp",
                    "cik": "70858",
                    "accession": "0000070858-26-000157",
                    "source_sha256": "2" * 64,
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = (
                root / qualification.FREEZE_RECEIPT_ROOT
                / (("a" * 64) + ".json")
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(json.dumps({
                "wb4_compact_transport": {
                    "qualification_task_measurements": [{
                        "family_id": "financial_statement",
                        "task_contract_id": "financial_test_task_v1",
                        "source_sha256": "1" * 64,
                        "source_layout_signature": reference_signature,
                    }],
                },
            }), encoding="utf-8")
            proof = qualification._financial_layout_independence_proof(
                repo_root=root,
                freeze={"receipt_id": freeze_id},
                matrix_entry=matrix_entry,
                task_contract_id="financial_test_task_v1",
                qualification_phase="SECOND_LAYOUT",
                sample=sample,
                measurement={"source_layout_signature": sample_signature},
            )
            self.assertEqual(4, len(proof["verified_differences"]))
            equal_headers = copy.deepcopy(sample_signature)
            equal_headers["ordered_header_layout_hash"] = (
                reference_signature["ordered_header_layout_hash"]
            )
            equal_headers["ordered_column_layout_hash"] = (
                reference_signature["ordered_column_layout_hash"]
            )
            with self.assertRaisesRegex(
                qualification.QualificationError,
                "materially different layout",
            ):
                qualification._financial_layout_independence_proof(
                    repo_root=root,
                    freeze={"receipt_id": freeze_id},
                    matrix_entry=matrix_entry,
                    task_contract_id="financial_test_task_v1",
                    qualification_phase="SECOND_LAYOUT",
                    sample=sample,
                    measurement={"source_layout_signature": equal_headers},
                )

    def test_next_financial_task_stops_after_prior_task_terminal(self) -> None:
        """Block cross-task egress after one earlier parent fails."""
        cycle_id = "sha256:" + ("a" * 64)

        def binding(*, task_id: str, plan_digit: str) -> dict:
            value = {
                field: None
                for field in qualification._QUALIFICATION_SHARD_AUTHORIZATION_FIELDS
                if field != "qualification_authorization_id"
            }
            plan_id = "sha256:" + (plan_digit * 64)
            value.update({
                "family_id": "financial_statement",
                "qualification_cycle_id": cycle_id,
                "freeze_receipt_id": "sha256:" + ("b" * 64),
                "requirement_closure_hash": "sha256:" + ("c" * 64),
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "api": "chat_completions",
                "qualification_phase": "SECOND_LAYOUT",
                "qualification_ordinal": 1,
                "task_contract_id": task_id,
                "qualification_task_plan_id": plan_id,
                "parent_qualification_task_plan_id": (
                    "sha256:" + (("d" if task_id == "task-a" else "e") * 64)
                ),
                "table_shard_binding": {
                    "shard_index": 0,
                    "shard_count": 1,
                },
            })
            value["qualification_authorization_id"] = content_hash(
                value=value,
            )
            return value

        prior = binding(task_id="task-a", plan_digit="1")
        current = binding(task_id="task-b", plan_digit="2")
        scope = {"authorized_task_contract_ids": ["task-a", "task-b"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_root = (
                root / qualification.TABLE_QUALIFICATION_CYCLE_ROOT
                / ("a" * 64)
            )
            (cycle_root / "runs" / "prior-run").mkdir(parents=True)
            with mock.patch.object(
                qualification,
                "load_run_for_status",
                return_value=(
                    {
                        "status": "FAILED",
                        "qualification_authorization": prior,
                    },
                    [],
                    [],
                ),
            ), self.assertRaisesRegex(
                qualification.QualificationError,
                "prior financial parent",
            ):
                qualification._financial_cycle_stop_gate(
                    repo_root=root,
                    binding=current,
                    scope=scope,
                )

            workspace = cycle_root / "invocation_control" / ("1" * 64)
            workspace.mkdir(parents=True)
            frozen_run = (
                {
                    "status": "FROZEN",
                    "qualification_authorization": prior,
                },
                [],
                [],
            )
            with mock.patch.object(
                qualification,
                "load_run_for_status",
                return_value=frozen_run,
            ), mock.patch.object(
                qualification,
                "qualification_remote_egress_terminals",
                return_value=[{
                    "qualification_task_plan_id": prior[
                        "qualification_task_plan_id"
                    ],
                    "status": "PENDING_REMOTE_OUTCOME",
                    "batch_terminal": None,
                }],
            ), self.assertRaisesRegex(
                qualification.QualificationError,
                "remote terminal stopped",
            ):
                qualification._financial_cycle_stop_gate(
                    repo_root=root,
                    binding=current,
                    scope=scope,
                )
            with mock.patch.object(
                qualification,
                "load_run_for_status",
                return_value=frozen_run,
            ), mock.patch.object(
                qualification,
                "qualification_remote_egress_terminals",
                return_value=[{
                    "qualification_task_plan_id": prior[
                        "qualification_task_plan_id"
                    ],
                    "status": "SUCCEEDED",
                    "batch_terminal": False,
                }],
            ):
                qualification._financial_cycle_stop_gate(
                    repo_root=root,
                    binding=current,
                    scope=scope,
                )

    def test_every_prior_sibling_must_be_materialized(self) -> None:
        """Reject an early incomplete Run even when the latest sibling passes."""
        cycle_id = "sha256:" + ("a" * 64)

        def binding(*, shard_index: int, plan_digit: str) -> dict:
            value = {
                field: None
                for field in qualification._QUALIFICATION_SHARD_AUTHORIZATION_FIELDS
                if field != "qualification_authorization_id"
            }
            value.update({
                "family_id": "financial_statement",
                "qualification_cycle_id": cycle_id,
                "freeze_receipt_id": "sha256:" + ("b" * 64),
                "requirement_closure_hash": "sha256:" + ("c" * 64),
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "api": "chat_completions",
                "qualification_phase": "SECOND_LAYOUT",
                "qualification_ordinal": 1,
                "task_contract_id": "task-a",
                "qualification_task_plan_id": (
                    "sha256:" + (plan_digit * 64)
                ),
                "parent_qualification_task_plan_id": (
                    "sha256:" + ("d" * 64)
                ),
                "table_shard_binding": {
                    "shard_index": shard_index,
                    "shard_count": 3,
                },
            })
            value["qualification_authorization_id"] = content_hash(
                value=value,
            )
            return value

        prior = [
            binding(shard_index=0, plan_digit="1"),
            binding(shard_index=1, plan_digit="2"),
        ]
        current = binding(shard_index=2, plan_digit="3")
        scope = {"authorized_task_contract_ids": ["task-a"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_root = (
                root / qualification.TABLE_QUALIFICATION_CYCLE_ROOT
                / ("a" * 64)
            )
            for index in range(2):
                (cycle_root / "runs" / "run-{}".format(index)).mkdir(
                    parents=True,
                )
                (cycle_root / "invocation_control" / (str(index + 1) * 64)).mkdir(
                    parents=True,
                )

            def load(run_dir: Path, repo_root: Path) -> tuple:
                del repo_root
                index = int(run_dir.name.split("-")[-1])
                return (
                    {
                        "status": "OPEN",
                        "qualification_authorization": prior[index],
                    },
                    [],
                    [],
                )

            def terminals(workspace_dir: Path) -> list[dict]:
                index = int(workspace_dir.name[0]) - 1
                return [{
                    "qualification_task_plan_id": prior[index][
                        "qualification_task_plan_id"
                    ],
                    "status": "SUCCEEDED",
                    "batch_terminal": False,
                }]

            def recovery(**kwargs: object) -> str:
                prior_binding = kwargs["binding"]
                return (
                    "OPEN_BEFORE_EGRESS"
                    if prior_binding["table_shard_binding"]["shard_index"] == 0
                    else "COMPLETE_OPEN_PENDING_REVIEW"
                )

            with mock.patch.object(
                qualification,
                "load_run_for_status",
                side_effect=load,
            ), mock.patch.object(
                qualification,
                "qualification_remote_egress_terminals",
                side_effect=terminals,
            ), mock.patch.object(
                qualification,
                "_table_qualification_recovery_state",
                side_effect=recovery,
            ), self.assertRaisesRegex(
                qualification.QualificationError,
                "not materialized",
            ):
                qualification._financial_cycle_stop_gate(
                    repo_root=root,
                    binding=current,
                    scope=scope,
                )


class FinancialTableShardClosureTest(unittest.TestCase):
    """Prove shard-local outcomes remain bound to complete ordered coverage."""

    def setUp(self) -> None:
        """Build two one-table shards over one complete local filing grid."""
        self.asset = sample_asset()
        self.source = reviewed_fixture(asset=self.asset)["source"]
        self.spec = compiled_specs()["DISCLOSURE"]
        self.manifest = build_reader_input_manifest(
            derived_asset=self.asset,
            source_reference_ids=[self.source["source_reference_id"]],
        )
        self.parent = encode_compact_table_payload(derived_asset=self.asset)
        self.shards = [
            build_contiguous_table_shard(
                parent_transport=self.parent,
                shard_index=index,
                shard_count=2,
                start_table_order=index,
                end_table_order=index,
            )
            for index in range(2)
        ]
        self.coverage = validate_contiguous_table_shard_set(
            shards=self.shards,
            parent_transport=self.parent,
        )

    def _candidate_and_evidence(
        self, *, shard_index: int, response: dict,
    ) -> tuple[dict, dict, dict]:
        payload = build_reader_shard_payload(
            manifest=self.manifest,
            derived_asset=self.asset,
            task_contract={"fixture": "financial-shard"},
            table_shard=self.shards[shard_index],
            table_shard_set_id=self.coverage["shard_set_id"],
        )
        candidate = validate_reader_output(
            response_text=json.dumps(response),
            attempt_id="attempt:financial:shard:{}".format(shard_index),
            required_roles=["occupancy", "revpar", "adr"],
            scope_contract=self.spec["compiled"]["scope_contract"],
            source_reference_ids=[self.source["source_reference_id"]],
            derived_asset_ids=[self.asset["derived_asset_id"]],
            table_shard_contract=payload["table_shard_contract"],
        )
        evidence = check_evidence(
            candidate=candidate,
            derived_asset=self.asset,
            reader_manifest=self.manifest,
            reader_payload_body=payload["body"],
            source_references=[self.source],
            identity_constraints=self.spec["compiled"][
                "identity_constraints"
            ],
            scope_contract=self.spec["compiled"]["scope_contract"],
        )
        return candidate, evidence, payload

    def test_no_candidate_shard_passes_local_evidence_and_system_review(
        self,
    ) -> None:
        """Approve only the shard-local absence fact, never a metric result."""
        shard = self.shards[0]
        response = {
            "disclosure_group": "lodging_kpi_table",
            "shard_id": shard["shard_id"],
            "examined_table_ids": list(shard["table_ids"]),
            "shard_disposition": "NO_CANDIDATE_IN_SHARD",
            "table_locator": None,
            "candidates": [],
            "unresolved_competing_claims": [],
        }
        candidate, evidence, _payload = self._candidate_and_evidence(
            shard_index=0,
            response=response,
        )
        self.assertEqual("PASS", evidence["status"])
        self.assertTrue(evidence["system_approval_eligible"])
        self.assertEqual({}, evidence["normalized_values"])
        context = build_review_context(
            candidate=candidate,
            evidence_check=evidence,
            derived_asset=self.asset,
            source_bindings=[self.source],
            spec_semantic_hash=self.spec["spec_semantic_hash"],
            required_claims=self.spec["compiled"]["required_claims"],
        )
        rendered = render_review_markdown(
            review_context=context["review_context"],
        )
        self.assertIn("Complete examined shard tables", rendered["text"])
        self.assertEqual(
            shard["table_ids"], context["review_context"]["examined_table_ids"],
        )
        unit = build_review_unit(
            candidate=candidate,
            evidence_check=evidence,
            source_bindings=[self.source],
            compiled_spec=self.spec,
            review_context_hash=context["review_context_hash"],
            rendered_review_hash=rendered["rendered_review_hash"],
            renderer_semantic_version=rendered[
                "review_renderer_semantic_version"
            ],
        )
        decision = create_system_review_decision(
            review_unit=unit,
            required_claims=unit["required_claims"],
            decided_at_utc="2026-08-28T12:30:00Z",
            requirement=load_requirement_snapshot(
                snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1",
            ),
        )
        self.assertEqual("APPROVE", decision["decision"])
        self.assertEqual(
            "NO_CANDIDATE_IN_SHARD", unit["shard_disposition"],
        )

    def test_candidate_shard_reuses_existing_claim_evidence(self) -> None:
        """Keep ordinary locator/scope checks for a candidate-bearing shard."""
        shard = self.shards[1]
        response = json.loads(reader_response(asset=self.asset))
        response.update({
            "shard_id": shard["shard_id"],
            "examined_table_ids": list(shard["table_ids"]),
            "shard_disposition": "CANDIDATE_PRESENT",
        })
        candidate, evidence, _payload = self._candidate_and_evidence(
            shard_index=1,
            response=response,
        )
        self.assertEqual("PASS", evidence["status"])
        self.assertEqual(
            {"occupancy", "revpar", "adr"},
            set(evidence["normalized_values"]),
        )
        self.assertEqual(shard["shard_id"], candidate[
            "table_shard_binding"
        ]["shard_id"])

    def test_shard_record_identity_rejects_coverage_mutation(self) -> None:
        """Make the exact examined table range part of Candidate identity."""
        shard = self.shards[0]
        response = {
            "disclosure_group": "lodging_kpi_table",
            "shard_id": shard["shard_id"],
            "examined_table_ids": list(shard["table_ids"]),
            "shard_disposition": "NO_CANDIDATE_IN_SHARD",
            "table_locator": None,
            "candidates": [],
            "unresolved_competing_claims": [],
        }
        candidate, _evidence, _payload = self._candidate_and_evidence(
            shard_index=0,
            response=response,
        )
        changed = copy.deepcopy(candidate)
        changed["examined_table_ids"] = ["table_substituted"]
        with self.assertRaises(RecordError):
            validate_record(record=changed)

    def test_recorded_attempt_binds_v4_schema_and_exact_shard(self) -> None:
        """Carry the same shard identity through the existing attempt record."""
        shard = self.shards[0]
        response = canonical_json_bytes(value={
            "disclosure_group": "financial_statement",
            "shard_id": shard["shard_id"],
            "examined_table_ids": list(shard["table_ids"]),
            "shard_disposition": "NO_CANDIDATE_IN_SHARD",
            "table_locator": None,
            "candidates": [],
            "unresolved_competing_claims": [],
        })
        prepared = prepare_reader_shard_request(
            manifest=self.manifest,
            derived_asset=self.asset,
            repo_root=REPO_ROOT,
            task_contract_id="financial_net_interest_margin_table_v1",
            table_shard=shard,
            table_shard_set_id=self.coverage["shard_set_id"],
        )
        returned, _raw, attempt, payloads = run_ai_attempt(
            adapter=build_recorded_adapter(
                response_bytes=response,
                fixture_id="financial-shard-recorded",
            ),
            prepared_request=prepared,
            clock=fixed_clock,
        )
        self.assertEqual(response, returned)
        self.assertEqual(shard["shard_id"], attempt["table_shard_id"])
        self.assertEqual(
            canonical_json_bytes(value=READER_SHARD_OUTPUT_JSON_SCHEMA),
            payloads.output_schema_bytes,
        )

    def test_financial_v4_request_cannot_bypass_sharding(self) -> None:
        """Reject the old one-request full-document path for financial tasks."""
        prepared = prepare_reader_request(
            manifest=self.manifest,
            derived_asset=self.asset,
            repo_root=REPO_ROOT,
            task_contract_id="financial_net_interest_margin_table_v1",
        )
        with self.assertRaises(AIAdapterError):
            run_ai_attempt(
                adapter=build_recorded_adapter(
                    response_bytes=b"{}",
                    fixture_id="financial-unsharded-recorded",
                ),
                prepared_request=prepared,
                clock=fixed_clock,
            )

    def test_no_candidate_shard_freezes_as_withheld_not_publication_credit(
        self,
    ) -> None:
        """Reuse Run/Review while materializing only a withheld shard result."""
        matrix = load_table_qualification_matrix(
            repo_root=REPO_ROOT,
            family_id="financial_statement",
        )
        entry = matrix["entries"]["financial_statement"]
        fixture = json.loads((
            REPO_ROOT
            / "fixtures/vnext/layouts/hilton-2024-sec-layout-v1/fixture_manifest.json"
        ).read_text(encoding="utf-8"))
        source_bytes = (
            REPO_ROOT / fixture["source_repo_relative_path"]
        ).read_bytes()
        asset = build_table_grid(
            html_bytes=source_bytes,
            parent_raw_asset_ids=["sha256:" + fixture["source_sha256"]],
            storage_uri="artifacts/vnext/derived/financial-shard-test.json",
        )
        parent = encode_compact_table_payload(derived_asset=asset)
        shard = build_contiguous_table_shard(
            parent_transport=parent,
            shard_index=0,
            shard_count=1,
            start_table_order=0,
            end_table_order=len(asset["tables"]) - 1,
        )
        coverage = validate_contiguous_table_shard_set(
            shards=[shard], parent_transport=parent,
        )
        response = canonical_json_bytes(value={
            "disclosure_group": "financial_statement",
            "shard_id": shard["shard_id"],
            "examined_table_ids": list(shard["table_ids"]),
            "shard_disposition": "NO_CANDIDATE_IN_SHARD",
            "table_locator": None,
            "candidates": [],
            "unresolved_competing_claims": [],
        })
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_table_task_review_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                run_id="run:financial:shard:no-candidate",
                company_id="jpmorgan_chase",
                target_period=entry["target_period"],
                source_repo_relative_path=fixture[
                    "source_repo_relative_path"
                ],
                source_media_type=entry["source_media_type"],
                source_url=fixture["source_url"],
                accession=fixture["accession"],
                document_name=fixture["document_name"],
                source_role=fixture["source_role"],
                request_attempt_id=fixture["request_attempt_id"],
                task_contract_id="financial_net_interest_margin_table_v1",
                adapter=build_recorded_adapter(
                    response_bytes=response,
                    fixture_id="financial-no-candidate-full-shard",
                ),
                clock=fixed_clock,
                table_shard=shard,
                table_shard_set_id=coverage["shard_set_id"],
            )
            self.assertEqual("PENDING_HUMAN_REVIEW", created["status"])
            finalized = finalize_reviewed_direct_results(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            self.assertEqual([], finalized["observation_ids"])
            validate_and_freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)
            _manifest, records, _decisions = load_frozen_run(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            results = [
                record for record in records
                if record["record_type"] == "METRIC_RESULT"
            ]
            self.assertEqual(1, len(results))
            self.assertEqual("WITHHELD", results[0]["publication"])
            self.assertEqual("SHARD_NO_CANDIDATE", results[0]["reason_code"])

    def _phase_terminal_fixture(
        self, *, root: Path, candidate_values: dict[int, str],
        omit_index: Optional[int] = None,
    ) -> tuple[str, dict[str, tuple[dict, list[dict], list]]]:
        cycle_id = "sha256:" + ("9" * 64)
        run_root = (
            root
            / qualification.TABLE_QUALIFICATION_CYCLE_ROOT
            / cycle_id.split(":", 1)[1]
            / "runs"
        )
        run_root.mkdir(parents=True)
        loaded = {}
        shard_count = 3
        for index in range(shard_count):
            if index == omit_index:
                continue
            run_dir = run_root / "{:02d}".format(index)
            run_dir.mkdir()
            shard_binding = {
                "request_shard_plan_id": "sha256:" + ("8" * 64),
                "table_shard_set_id": "sha256:" + ("7" * 64),
                "shard_id": "sha256:" + format(index + 1, "064x"),
                "shard_payload_sha256": format(index + 4, "064x"),
                "shard_index": index,
                "shard_count": shard_count,
                "start_table_order": index,
                "end_table_order": index,
                "table_ids": ["table_{:06d}".format(index)],
                "reader_request_body_sha256": format(index + 7, "064x"),
                "reader_request_bytes": 100,
                "provider_request_body_sha256": format(index + 10, "064x"),
                "provider_envelope_bytes": 120,
                "provider_output_schema_sha256": format(index + 13, "064x"),
                "estimated_input_tokens": 120,
                "packing_utf8_upper_bound_tokens": 191,
                "blocking_reason_codes": [],
            }
            disposition = (
                "CANDIDATE_PRESENT"
                if index in candidate_values
                else "NO_CANDIDATE_IN_SHARD"
            )
            binding = {
                "family_id": "financial_statement",
                "qualification_phase": "SECOND_LAYOUT",
                "qualification_ordinal": 1,
                "task_contract_id": "financial_example_table_v1",
                "qualification_terminal_id": "sha256:" + format(
                    index + 20, "064x"
                ),
                "qualification_task_plan_id": "sha256:" + format(
                    index + 30, "064x"
                ),
                "parent_qualification_task_plan_id": "sha256:" + ("6" * 64),
                "context_feasibility_binding": {
                    "provider_request_body_sha256": shard_binding[
                        "provider_request_body_sha256"
                    ],
                },
                "source_binding_hash": "sha256:" + ("5" * 64),
                "table_shard_binding": shard_binding,
            }
            evidence_id = "sha256:" + format(index + 40, "064x")
            result_id = "sha256:" + format(index + 50, "064x")
            candidate = {
                "record_type": "OBSERVATION_CANDIDATE",
                "table_shard_binding": shard_binding,
                "shard_disposition": disposition,
            }
            check = {
                "record_type": "EVIDENCE_CHECK",
                "status": "PASS",
                "table_shard_binding": shard_binding,
                "evidence_check_id": "sha256:" + format(index + 60, "064x"),
                "normalized_values": (
                    {"value": candidate_values[index]}
                    if index in candidate_values
                    else {}
                ),
                "normalized_scope": (
                    {"scope": "same"} if index in candidate_values else {}
                ),
            }
            records = [
                {
                    "record_type": "TABLE_QUALIFICATION_EVIDENCE",
                    "qualification_evidence_id": evidence_id,
                },
                {"record_type": "METRIC_RESULT", "result_id": result_id},
                candidate,
                check,
            ]
            manifest = {
                "status": "FROZEN",
                "run_id": "run:financial:shard:{}".format(index),
                "qualification_authorization": binding,
            }
            loaded[run_dir.name] = (manifest, records, [])
        return cycle_id, loaded

    def test_phase_credit_requires_complete_shards_and_candidate(self) -> None:
        """Collapse child Runs only after exact coverage and one candidate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_id, loaded = self._phase_terminal_fixture(
                root=root,
                candidate_values={1: "10"},
            )
            with mock.patch.object(
                qualification,
                "load_run_for_status",
                side_effect=lambda run_dir, repo_root: loaded[run_dir.name],
            ), mock.patch.object(
                qualification,
                "validate_table_qualification_run_bindings",
            ):
                rows = qualification._table_phase_terminal_rows(
                    repo_root=root,
                    qualification_cycle_id=cycle_id,
                    family_id="financial_statement",
                    qualification_phase="SECOND_LAYOUT",
                )
            self.assertEqual(1, len(rows))
            self.assertEqual(3, rows[0]["shard_count"])
            self.assertEqual(1, rows[0]["candidate_shard_count"])
            self.assertTrue(rows[0]["all_shards_examined_before_credit"])
            self.assertEqual(
                ["table_000000", "table_000001", "table_000002"],
                rows[0]["covered_table_ids"],
            )

    def test_phase_credit_rejects_missing_or_conflicting_shards(self) -> None:
        """Withhold aggregate credit for a gap or conflicting candidate facts."""
        cases = (
            ({1: "10"}, 2, "SHARD_COVERAGE_INCOMPLETE"),
            ({0: "10", 1: "11"}, None, "SHARD_CONFLICT_WITHHELD"),
        )
        for candidate_values, omit_index, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cycle_id, loaded = self._phase_terminal_fixture(
                    root=root,
                    candidate_values=candidate_values,
                    omit_index=omit_index,
                )
                with mock.patch.object(
                    qualification,
                    "load_run_for_status",
                    side_effect=lambda run_dir, repo_root: loaded[run_dir.name],
                ), mock.patch.object(
                    qualification,
                    "validate_table_qualification_run_bindings",
                ), self.assertRaisesRegex(
                    qualification.QualificationError,
                    reason,
                ):
                    qualification._table_phase_terminal_rows(
                        repo_root=root,
                        qualification_cycle_id=cycle_id,
                        family_id="financial_statement",
                        qualification_phase="SECOND_LAYOUT",
                    )


if __name__ == "__main__":
    unittest.main()
