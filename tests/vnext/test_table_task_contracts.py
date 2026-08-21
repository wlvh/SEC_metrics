"""Exercise WB-6 catalog-owned single-table task contract derivation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import compiled_specs, reader_response, sample_asset
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


if __name__ == "__main__":
    unittest.main()
