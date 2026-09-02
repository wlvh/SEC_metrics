"""Exercise WB-6 catalog-owned single-table task contract derivation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.vnext_qualification import QualificationCliError, prepare_layout
from tests.vnext.common import compiled_specs, fixed_clock, reader_response
from tests.vnext.common import sample_asset
from tests.vnext.common import sample_source_reference
from vnext import ai_adapter
from vnext import workflow as workflow_module
from vnext.ai_adapter import AttemptPayloads, TransportObservation
from vnext.ai_adapter import approved_transport_policy
from vnext.ai_adapter import build_deepseek_chat_completions_body
from vnext.ai_adapter import build_provider_request_body
from vnext.ai_adapter import build_recorded_adapter, run_ai_attempt
from vnext.ai_adapter import TransportPolicy
from vnext.canonical import atomic_write_bytes, atomic_write_json, sha256_bytes
from vnext.requirements import (
    ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
)
from vnext.requirements import load_requirement_snapshot
from vnext.source_strategy import load_source_strategy_registry
from vnext.table_task_contracts import _table_route_sets
from vnext.table_task_contracts import TableTaskContractError
from vnext.table_task_contracts import load_table_task_contracts
from vnext.table_task_contracts import resolve_table_task_contract
from vnext.reader_input import build_reader_input_manifest
from vnext.reader_input import prepare_reader_request
from vnext.qualification import table_qualification_task_plan
from vnext.replay import replay_frozen_results
from vnext.review import create_review_decision
from vnext.run_store import append_review_decision, load_frozen_run
from vnext.run_store import load_open_run, validate_and_freeze_run
from vnext.run_store import write_attempt_payloads
from vnext.run_store import RunStoreError
from vnext.sources import raw_blob_record
from vnext.table_grid import build_table_grid
from vnext.workflow import create_table_task_review_run
from vnext.workflow import finalize_reviewed_direct_results
from vnext.workflow import WorkflowError


REPO_ROOT = Path(__file__).resolve().parents[2]


class TableTaskContractsTest(unittest.TestCase):
    """Verify no table contract depends on a runtime metric/table selector."""

    @staticmethod
    def _create_catalog_task_run(*, run_dir: Path) -> dict:
        """Create one single-role recorded catalog Run with exact source bytes.

        Args:
            run_dir: New temporary Run directory.

        Returns:
            Workflow result at the pending-review boundary.
        """
        source_relative = "tests/fixtures/vnext/sample_lodging.html"
        raw_blob = raw_blob_record(
            repo_root=REPO_ROOT,
            repo_relative_path=source_relative,
            media_type="text/html",
        )
        asset = build_table_grid(
            html_bytes=(REPO_ROOT / source_relative).read_bytes(),
            parent_raw_asset_ids=[str(raw_blob["raw_asset_id"])],
            storage_uri="artifacts/vnext/derived/{}.json".format(
                str(raw_blob["raw_asset_id"]).split(":", maxsplit=1)[1]
            ),
        )
        response = json.loads(reader_response(asset=asset).decode("utf-8"))
        response["candidates"] = [response["candidates"][0]]
        return create_table_task_review_run(
            repo_root=REPO_ROOT,
            run_dir=run_dir,
            run_id="run:catalog-task:occupancy",
            company_id="marriott_international",
            target_period={
                "fiscal_year": 2025,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
            source_repo_relative_path=source_relative,
            source_media_type="text/html",
            source_url="https://www.sec.gov/Archives/sample.htm",
            accession="0001048286-25-000001",
            document_name="sample_lodging.html",
            source_role="target_primary",
            request_attempt_id="request:attempt:fixture",
            task_contract_id="lodging_occupancy_table_v2",
            adapter=build_recorded_adapter(
                response_bytes=json.dumps(response).encode("utf-8"),
                fixture_id="catalog-task-formal-run",
            ),
            clock=fixed_clock,
        )

    @staticmethod
    def _replace_recorded_attempt_with_issue15_remote_observation(
        *, run_dir: Path,
    ) -> None:
        """Replace test-only recorded transport bytes with Issue #15 D-01 data.

        Args:
            run_dir: OPEN temporary catalog Run whose response remains local.

        Why:
            The test must exercise the remote replay branch without opening a
            socket.  It forms the exact provider envelope and observation from
            Issue #15 D-01, then persists them as immutable fixture bytes.
        """
        _manifest, records, _decisions = load_open_run(run_dir=run_dir)
        attempt = next(
            record
            for record in records
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
        )
        requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements" / "issue_15_v1",
        )
        policy = approved_transport_policy(requirement=requirement)
        reader_payload = (run_dir / attempt["reader_payload_path"]).read_bytes()
        task_contract = (run_dir / attempt["task_contract_path"]).read_bytes()
        assistant_output = (
            run_dir / attempt["assistant_output_path"]
        ).read_bytes()
        raw_response = (run_dir / attempt["raw_response_path"]).read_bytes()
        provider_envelope, output_schema = build_provider_request_body(
            policy=policy,
            reader_request_bytes=reader_payload,
        )
        observation = TransportObservation(
            egress_attempted=True,
            provider=policy.provider,
            model=policy.model,
            model_requested=policy.model,
            model_returned=policy.model,
            api=policy.api,
            store=False,
            endpoint_host=policy.endpoint_host,
            region=policy.region,
            retention=policy.retention,
            data_use=policy.data_use,
            timeout_seconds=policy.timeout_seconds,
            retry_count=policy.retry_count,
            retries_performed=0,
            maximum_payload_bytes=policy.maximum_payload_bytes,
            filing_egress_policy=policy.filing_egress_policy,
            request_body_bytes=len(provider_envelope),
        )
        changed = dict(attempt)
        request_digest = sha256_bytes(content=provider_envelope)
        schema_digest = sha256_bytes(content=output_schema)
        changed.update({
            "provider": observation.provider,
            "model": observation.model,
            "model_requested": observation.model_requested,
            "model_returned": observation.model_returned,
            "api": observation.api,
            "endpoint_host": observation.endpoint_host,
            "transport_observation": observation.as_mapping(),
            "request_body_sha256": request_digest,
            "request_body_path": (
                "attempt_payloads/request_{}.bin".format(request_digest)
            ),
            "output_schema_sha256": schema_digest,
            "output_schema_path": (
                "attempt_payloads/output_schema_{}.json".format(
                    schema_digest
                )
            ),
            "provider_request_id": "request:synthetic-issue15",
        })
        for field in ("request_body_path", "output_schema_path"):
            previous = run_dir / attempt[field]
            current = run_dir / changed[field]
            if previous != current:
                previous.unlink()
        write_attempt_payloads(
            run_dir=run_dir,
            attempt=changed,
            payloads=AttemptPayloads(
                request_body_bytes=provider_envelope,
                reader_payload_bytes=reader_payload,
                task_contract_bytes=task_contract,
                output_schema_bytes=output_schema,
                assistant_output_bytes=assistant_output,
                raw_response_bytes=raw_response,
            ),
        )
        rewritten = [
            changed
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            else record
            for record in records
        ]
        records_bytes = (
            "\n".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True)
                for record in rewritten
            )
            + "\n"
        ).encode("utf-8")
        atomic_write_bytes(
            path=run_dir / "records.jsonl",
            content=records_bytes,
        )

    def test_all_table_routes_are_single_role_catalog_contracts(self) -> None:
        """Derive the exact table-authorized family and metric sets offline."""
        catalog = load_table_task_contracts(repo_root=REPO_ROOT)
        registry = load_source_strategy_registry(repo_root=REPO_ROOT)
        route_sets = _table_route_sets(repo_root=REPO_ROOT, registry=registry)
        self.assertEqual(
            route_sets["table_family_ids"],
            catalog["authorized_family_ids"],
        )
        self.assertEqual(
            route_sets["table_metric_ids"],
            catalog["table_metric_ids"],
        )
        for contract in catalog["contracts"]:
            with self.subTest(task_contract_id=contract["task_contract_id"]):
                self.assertEqual("table", contract["representation"])
                self.assertEqual(1, len(contract["required_roles"]))
                self.assertEqual("NOT_RUN", contract["actual_incremental_tokens"])
                self.assertEqual(
                    "FIRST_TASK_PLUS_DUPLICATED_FULL_PAYLOAD",
                    contract["split_baseline_kind"],
                )
                self.assertNotEqual(
                    "",
                    str(contract["estimated_incremental_tokens"]),
                )
                self.assertTrue(contract["task_contract_hash"].startswith("sha256:"))
                self.assertTrue(contract["output_schema_hash"].startswith("sha256:"))
                self.assertTrue(contract["system_prompt_hash"].startswith("sha256:"))
                self.assertEqual(1, len(contract["metric_specs"]))

    def test_runtime_task_reuses_catalog_metric_scope_schema_and_prompt(self) -> None:
        """Bind one actual Reader task to the selected catalog identity."""
        catalog = load_table_task_contracts(repo_root=REPO_ROOT)
        selected = catalog["contracts"][0]
        runtime = resolve_table_task_contract(
            repo_root=REPO_ROOT,
            task_contract_id=selected["task_contract_id"],
        )
        self.assertEqual(selected["task_contract_id"], runtime["task_contract_id"])
        self.assertEqual(selected["task_contract_hash"], runtime[
            "catalog_task_contract_hash"
        ])
        self.assertEqual(selected["output_schema_hash"], runtime[
            "output_schema_hash"
        ])
        self.assertEqual(selected["system_prompt_hash"], runtime[
            "system_prompt_hash"
        ])
        self.assertEqual(selected["required_roles"], runtime["required_roles"])

    def test_revised_prompt_is_lodging_local_and_schema_preserving(self) -> None:
        """Change only two prompt strings and retain one shared schema hash."""
        catalog = load_table_task_contracts(repo_root=REPO_ROOT)
        lodging = [
            value for value in catalog["contracts"]
            if value["reader_family_id"] == "lodging_kpi_table"
        ]
        financial = [
            value for value in catalog["contracts"]
            if value["reader_family_id"] == "financial_statement"
        ]
        self.assertEqual(2, len(lodging))
        self.assertEqual(8, len(financial))
        self.assertEqual(
            {ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT},
            {value["system_prompt"] for value in lodging},
        )
        self.assertIn(
            "selected target table supplies a non-empty caption_raw_text",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "all eight locator fields copied from one supplied cell in the "
            "same selected target table",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Never use text from another table or nearby prose.",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "valid JSON escape sequences such as \\n, \\r, and \\t",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "never trim, normalize, or collapse whitespace",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "c=[caption,caption_raw_text]",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "[row_index,column_index,rowspan,colspan,header,raw_text,text]",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "copy c[1] for caption or x[5]",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertIn(
            "never copy c[0] or x[6]",
            ISSUE_15_D07_COMPACT_RAW_TEXT_LODGING_SYSTEM_PROMPT,
        )
        self.assertEqual(
            {"Return raw claims and exact locators from one selected table only."},
            {value["system_prompt"] for value in financial},
        )
        self.assertEqual(
            1, len({value["output_schema_hash"] for value in lodging + financial}),
        )

    def test_fallback_representation_schema_requires_every_structured_route(self) -> None:
        """Reject an incomplete table/text representation authority before catalog use."""
        registry = load_source_strategy_registry(repo_root=REPO_ROOT)
        source = REPO_ROOT / "config" / "source_strategy_fallback_representation.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        del payload["fallback_representation_by_metric"]["A09"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            (config / source.name).write_text(
                json.dumps(payload), encoding="utf-8",
            )
            with self.assertRaises(TableTaskContractError):
                _table_route_sets(repo_root=root, registry=registry)

    def test_catalog_task_is_the_actual_prepared_request_and_attempt_authority(self) -> None:
        """Bind one single-role catalog task through the recorded attempt path."""
        asset = sample_asset()
        source = sample_source_reference(
            raw_asset_id=str(asset["parent_raw_asset_ids"][0]),
        )
        manifest = build_reader_input_manifest(
            derived_asset=asset,
            source_reference_ids=[source["source_reference_id"]],
        )
        catalog = load_table_task_contracts(repo_root=REPO_ROOT)
        selected = catalog["contracts"][-2]
        prepared = prepare_reader_request(
            manifest=manifest,
            derived_asset=asset,
            compiled_spec=compiled_specs()["DISCLOSURE"],
            repo_root=REPO_ROOT,
            task_contract_id=selected["task_contract_id"],
        )
        task = json.loads(prepared.task_contract_bytes.decode("utf-8"))
        self.assertEqual(selected["task_contract_id"], task["task_contract_id"])
        self.assertEqual(["occupancy"], task["required_roles"])
        response = json.loads(reader_response(asset=asset).decode("utf-8"))
        response["candidates"] = [response["candidates"][0]]
        _body, _raw, attempt, _payloads = run_ai_attempt(
            adapter=build_recorded_adapter(
                response_bytes=json.dumps(response).encode("utf-8"),
                fixture_id="table-task-contract",
            ),
            prepared_request=prepared,
        )
        self.assertEqual("SUCCEEDED", attempt["status"])
        self.assertEqual(selected["task_contract_id"], attempt[
            "task_contract_id"
        ])
        self.assertEqual(selected["task_contract_hash"], attempt[
            "catalog_task_contract_hash"
        ])
        self.assertEqual(selected["output_schema_hash"], attempt[
            "catalog_output_schema_hash"
        ])
        self.assertEqual(selected["system_prompt_hash"], attempt[
            "system_prompt_hash"
        ])
        policy = TransportPolicy.from_mapping(
            value={
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "api": "chat_completions",
                "endpoint_host": "api.deepseek.com",
                "region": "provider-managed-no-residency-guarantee",
                "retention": "provider-managed; no zero-retention claim",
                "data_use": "provider-managed; no training or data-use guarantee",
                "timeout_seconds": 120,
                "retry_count": 2,
                "maximum_payload_bytes": 8388608,
                "filing_egress_policy": "PUBLIC_SEC_FILING_TABLE_GRIDS_ONLY",
            },
        )
        envelope, _schema = build_deepseek_chat_completions_body(
            policy=policy,
            reader_request_bytes=prepared.request_bytes,
        )
        system_text = json.loads(envelope.decode("utf-8"))["messages"][0][
            "content"
        ]
        self.assertIn(task["system_prompt"], system_text)

    def test_catalog_task_runs_through_formal_freeze_and_replay(self) -> None:
        """Freeze and replay one schema-v2 single-role catalog task offline."""
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "catalog-task-run"
            created = self._create_catalog_task_run(run_dir=run_dir)
            self.assertEqual("PENDING_HUMAN_REVIEW", created["status"])
            manifest, records, _decisions = load_open_run(run_dir=run_dir)
            self.assertEqual(1, len(manifest["task_contract_bindings"]))
            attempt = next(
                record
                for record in records
                if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            )
            self.assertEqual("lodging_occupancy_table_v2", attempt[
                "task_contract_id"
            ])
            payload_path = run_dir / str(attempt["task_contract_path"])
            task = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual("3", task["output_schema_version"])
            self.assertEqual(["occupancy"], task["required_roles"])
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            decision = create_review_decision(
                review_unit=unit,
                decision="APPROVE",
                approved_claims=unit["required_claims"],
                required_claims=unit["required_claims"],
                reviewer_id="human:catalog-task:fixture",
                decided_at_utc="2026-08-21T00:00:00Z",
                reason="Recorded single-table scope and locator reviewed.",
                supersedes_decision_id=None,
            )
            append_review_decision(run_dir=run_dir, decision=decision)
            finalized = finalize_reviewed_direct_results(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            self.assertEqual(1, len(finalized["result_ids"]))
            frozen = validate_and_freeze_run(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            self.assertEqual("FROZEN", frozen["status"])
            loaded, _loaded_records, _loaded_decisions = load_frozen_run(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            replay = replay_frozen_results(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
        self.assertEqual("FROZEN", loaded["status"])
        self.assertEqual(1, len(replay["results"]))

    def test_unauthorised_catalog_remote_transport_cannot_freeze_or_replay(self) -> None:
        """Reject a synthetic remote catalog attempt with no qualification evidence."""
        parent_requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements" / "ai_first_v3_3_1",
        )
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "unauthorised-remote-finalize"
            self._create_catalog_task_run(run_dir=run_dir)
            self._replace_recorded_attempt_with_issue15_remote_observation(
                run_dir=run_dir,
            )
            with self.assertRaisesRegex(
                WorkflowError,
                "TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED",
            ):
                finalize_reviewed_direct_results(
                    run_dir=run_dir,
                    repo_root=REPO_ROOT,
                )

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "unauthorised-remote-freeze"
            self._create_catalog_task_run(run_dir=run_dir)
            finalize_reviewed_direct_results(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            self._replace_recorded_attempt_with_issue15_remote_observation(
                run_dir=run_dir,
            )
            with self.assertRaisesRegex(
                RunStoreError,
                "TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED",
            ):
                validate_and_freeze_run(
                    run_dir=run_dir,
                    repo_root=REPO_ROOT,
                )

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "parent-hash-negative"
            self._create_catalog_task_run(run_dir=run_dir)
            finalize_reviewed_direct_results(
                run_dir=run_dir,
                repo_root=REPO_ROOT,
            )
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["requirement_hashes"] = parent_requirement["hashes"]
            atomic_write_json(path=manifest_path, value=manifest)
            with self.assertRaisesRegex(
                RunStoreError,
                "Catalog task Run Requirement hashes differ from Issue #15",
            ):
                validate_and_freeze_run(
                    run_dir=run_dir,
                    repo_root=REPO_ROOT,
                )

    def test_live_catalog_paths_require_qualification_authorization(self) -> None:
        """Reject every catalog LIVE wrapper before source or transport work."""
        common = {
            "repo_root": REPO_ROOT,
            "company_id": "marriott_international",
            "target_period": {
                "fiscal_year": 2025,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
            "source_repo_relative_path": "tests/fixtures/vnext/sample_lodging.html",
            "source_media_type": "text/html",
            "source_url": "https://www.sec.gov/Archives/sample.htm",
            "accession": "0001048286-25-000001",
            "document_name": "sample_lodging.html",
            "source_role": "target_primary",
            "request_attempt_id": "request:attempt:fixture",
            "task_contract_id": "lodging_occupancy_table_v2",
            "clock": fixed_clock,
        }
        with tempfile.TemporaryDirectory() as temporary:
            adapter = ai_adapter.build_invocation_controlled_transport_adapter(
                release_input_plan_id="sha256:" + "a" * 64,
                workspace_dir=Path(temporary) / "unrelated-workspace",
                owner_token="live-catalog-canary",
            )
            transport = mock.Mock(name="provider_opener")
            with mock.patch.object(
                workflow_module,
                "run_ai_attempt",
                side_effect=AssertionError("transport must not be reached"),
            ) as run_attempt, mock.patch.object(
                ai_adapter,
                "_DEEPSEEK_OPENER",
                transport,
            ):
                wrappers = (
                    (
                        "table_wrapper",
                        lambda run_dir: create_table_task_review_run(
                            run_dir=run_dir,
                            run_id="run:live-catalog:table-wrapper",
                            adapter=adapter,
                            **common,
                        ),
                    ),
                    (
                        "generic_wrapper",
                        lambda run_dir: workflow_module.create_review_run(
                            run_dir=run_dir,
                            run_id="run:live-catalog:generic-wrapper",
                            disclosure_spec_path=(
                                "catalog/table_task_contracts.json"
                            ),
                            adapter=adapter,
                            **common,
                        ),
                    ),
                    (
                        "shared_callee",
                        lambda run_dir: workflow_module._create_review_run_with_traits(
                            run_dir=run_dir,
                            run_id="run:live-catalog:shared-callee",
                            company_traits=["lodging"],
                            disclosure_spec_path=(
                                "catalog/table_task_contracts.json"
                            ),
                            adapter=adapter,
                            **common,
                        ),
                    ),
                )
                for label, invoke in wrappers:
                    with self.subTest(path=label), self.assertRaisesRegex(
                        WorkflowError,
                        "TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED",
                    ):
                        invoke(Path(temporary) / label)
        self.assertEqual(0, run_attempt.call_count)
        self.assertEqual(0, transport.call_count)

    def test_matrix_task_plan_uses_scope_bound_proofs(self) -> None:
        """Form a reviewed-usage plan without reusing historical proofs."""
        plan = table_qualification_task_plan(
            repo_root=REPO_ROOT,
            family_id="lodging_kpi_table",
            task_contract_id="lodging_occupancy_table_v2",
            qualification_ordinal=1,
        )
        self.assertEqual("lodging_kpi_table", plan["family_id"])
        self.assertEqual(
            "lodging_occupancy_table_v2", plan["task_contract_id"],
        )
        self.assertEqual(1, plan["qualification_ordinal"])
        self.assertEqual(
            "EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE",
            plan["context_evidence_basis"],
        )

    def test_legacy_qualification_prepare_requires_catalog_task(self) -> None:
        """Reject schema-v1 fixture input before choosing any family gate."""
        with self.assertRaises(QualificationCliError) as raised:
            prepare_layout(fixture_id="hilton-2024-sec-layout-v1")
        self.assertEqual("TABLE_TASK_CONTRACT_REQUIRED", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
