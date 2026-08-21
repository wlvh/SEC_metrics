"""Exercise WB-6 catalog-owned single-table task contract derivation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import compiled_specs, fixed_clock, reader_response
from tests.vnext.common import sample_asset
from tests.vnext.common import sample_source_reference
from vnext.ai_adapter import build_deepseek_chat_completions_body
from vnext.ai_adapter import build_recorded_adapter, run_ai_attempt
from vnext.ai_adapter import TransportPolicy
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
from vnext.sources import raw_blob_record
from vnext.table_grid import build_table_grid
from vnext.workflow import create_table_task_review_run
from vnext.workflow import finalize_reviewed_direct_results


REPO_ROOT = Path(__file__).resolve().parents[2]


class TableTaskContractsTest(unittest.TestCase):
    """Verify no table contract depends on a runtime metric/table selector."""

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
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "catalog-task-run"
            created = create_table_task_review_run(
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
            self.assertEqual("2", task["output_schema_version"])
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

    def test_matrix_task_plan_binds_one_catalog_task_before_workflow(self) -> None:
        """Derive a future ordinal plan without falling back to schema v1."""
        with mock.patch(
            "vnext.qualification.require_table_qualification_freeze",
            return_value={"receipt_id": "sha256:" + "a" * 64},
        ):
            plan = table_qualification_task_plan(
                repo_root=REPO_ROOT,
                family_id="lodging_kpi_table",
                task_contract_id="lodging_occupancy_table_v2",
                qualification_ordinal=1,
            )
        self.assertEqual("lodging_kpi_table", plan["family_id"])
        self.assertEqual(
            "lodging_occupancy_table_v2",
            plan["task_contract_id"],
        )
        self.assertEqual(1, plan["qualification_ordinal"])
        self.assertTrue(plan["task_spec_semantic_hash"].startswith("sha256:"))
        self.assertTrue(plan["qualification_task_plan_id"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
