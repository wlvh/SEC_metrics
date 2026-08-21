"""Exercise the sole LIVE table-qualification authorization boundary."""

from __future__ import annotations

import copy
import concurrent.futures
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator
from unittest import mock

from tests.vnext.common import cell_locator
from vnext import ai_adapter, qualification, workflow
from vnext.ai_adapter import TransportObservation, TransportResult
from vnext.ai_adapter import build_provider_request_body
from vnext.canonical import atomic_write_bytes, atomic_write_json, content_hash
from vnext.replay import replay_frozen_results
from vnext.run_store import load_frozen_run, RunStoreError, validate_and_freeze_run
from vnext.stage_a_snapshot import write_stage_a_snapshot
from vnext.table_grid import build_table_grid
from vnext.table_qualification_freeze import _measurement_receipts
from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_qualification_freeze import validate_table_qualification_freeze
from vnext.table_qualification_freeze import write_table_qualification_freeze_receipt
from vnext.table_task_contracts import load_table_task_contracts
from vnext.workflow import finalize_reviewed_direct_results


REPO_ROOT = Path(__file__).resolve().parents[2]
MARRIOTT_SOURCE = (
    "evidence/request_attempts/c3/"
    "c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547/"
    "mar-20251231.htm"
)
MARRIOTT_RAW_ID = (
    "sha256:c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547"
)


def _run_git(*, workdir: Path, arguments: list[str], stdin: bytes = b"") -> str:
    """Run one local Git command or fail the test with its captured stderr."""
    completed = subprocess.run(
        ["git", *arguments],
        cwd=workdir,
        input=stdin,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", "replace"))
    return completed.stdout.decode("utf-8")


@contextmanager
def synthetic_no_d07_repository() -> Iterator[Path]:
    """Build a clean, committed test-only authority without D-07 blocking.

    This changes only a disposable worktree's matrix-owned development
    measurement inputs, then invokes the real freeze builder.  In particular,
    it never flips a receipt boolean or mocks the qualification gate.
    """
    with tempfile.TemporaryDirectory() as directory:
        parent = Path(directory)
        worktree = parent / "tree"
        _run_git(
            workdir=REPO_ROOT,
            arguments=["worktree", "add", "--detach", str(worktree), "HEAD"],
        )
        try:
            patch = subprocess.run(
                ["git", "diff", "--binary"],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
            )
            if patch.returncode != 0:
                raise AssertionError("Cannot read current source patch")
            if patch.stdout:
                _run_git(
                    workdir=worktree,
                    arguments=["apply"],
                    stdin=patch.stdout,
                )
                _run_git(workdir=worktree, arguments=["add", "-u"])
                _run_git(
                    workdir=worktree,
                    arguments=[
                        "-c", "user.name=synthetic", "-c",
                        "user.email=synthetic@example.invalid", "commit", "-m",
                        "synthetic source authority",
                    ],
                )
            (worktree / "outputs/active_publication.json.lock").touch()
            matrix_path = worktree / "config/table_qualification_matrix.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            entries = {
                entry["family_id"]: entry
                for entry in matrix["families"]
            }
            # The production financial source reaches the local complete-grid
            # resource stop.  The test-only authority reuses the already local
            # complete Marriott source merely to exercise the no-D-07 success
            # branch through the normal measurement builder.
            entries["financial_statement"]["development_source"] = copy.deepcopy(
                entries["lodging_kpi_table"]["development_source"]
            )
            for entry in entries.values():
                entry["token_context_limits"][
                    "max_estimated_input_tokens"
                ] = 1_000_000
            atomic_write_json(path=matrix_path, value=matrix)
            catalog_path = worktree / "catalog/table_task_contracts.json"
            # The split receipt intentionally measures complete task envelopes.
            # Its test-only catalog values must therefore be iterated through
            # the real estimator rather than guessed from a production row.
            for _iteration in range(16):
                contracts = load_table_task_contracts(repo_root=worktree)
                measurements = _measurement_receipts(
                    repo_root=worktree,
                    matrix=load_table_qualification_matrix(repo_root=worktree),
                    task_contracts=contracts,
                )
                estimates = {
                    row["task_contract_id"]: row["estimated_input_tokens"]
                    for row in measurements["qualification_task_measurements"]
                }
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                by_family = {}
                for contract in catalog["contracts"]:
                    by_family.setdefault(
                        contract["reader_family_id"],
                        [],
                    ).append(contract)
                changed = False
                for contracts_for_family in by_family.values():
                    for ordinal, contract in enumerate(sorted(
                        contracts_for_family,
                        key=lambda item: item["task_contract_id"],
                    )):
                        expected = (
                            0 if ordinal == 0
                            else estimates[contract["task_contract_id"]]
                        )
                        if contract["estimated_incremental_tokens"] != expected:
                            contract["estimated_incremental_tokens"] = expected
                            changed = True
                atomic_write_json(path=catalog_path, value=catalog)
                if not changed:
                    break
            else:
                raise AssertionError(
                    "Synthetic split-cost measurement did not reach a fixed point"
                )
            _run_git(
                workdir=worktree,
                arguments=[
                    "add", "--", "config/table_qualification_matrix.json",
                    "catalog/table_task_contracts.json",
                ],
            )
            _run_git(
                workdir=worktree,
                arguments=[
                    "-c", "user.name=synthetic", "-c",
                    "user.email=synthetic@example.invalid", "commit", "-m",
                    "synthetic no-d07 measurement authority",
                ],
            )
            freeze_commit = _run_git(
                workdir=worktree,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            receipt = write_table_qualification_freeze_receipt(
                repo_root=worktree,
                freeze_commit=freeze_commit,
                frozen_at_utc="2026-08-21T08:30:00Z",
            )
            if receipt["d07_decision_required"] is not False:
                raise AssertionError("Synthetic measurement authority still blocks D-07")
            atomic_write_json(
                path=worktree / "config/table_qualification_freeze.json",
                value={
                    "schema_version": 1,
                    "qualification_cycle_id": receipt[
                        "qualification_cycle_id"
                    ],
                    "receipt_id": receipt[
                        "table_qualification_freeze_receipt_id"
                    ],
                    "receipt_path": receipt["receipt_path"],
                },
            )
            _run_git(
                workdir=worktree,
                arguments=[
                    "add", "--", "config/table_qualification_freeze.json",
                    "artifacts/vnext/table_qualification_freeze",
                ],
            )
            _run_git(
                workdir=worktree,
                arguments=[
                    "-c", "user.name=synthetic", "-c",
                    "user.email=synthetic@example.invalid", "commit", "-m",
                    "synthetic no-d07 authority",
                ],
            )
            write_stage_a_snapshot(
                repo_root=worktree,
                frozen_at_utc="2026-08-21T08:31:00Z",
            )
            yield worktree
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
            )


def _occupancy_response(*, repo_root: Path) -> bytes:
    """Build one valid single-role response against Marriott's full grid."""
    asset = build_table_grid(
        html_bytes=(repo_root / MARRIOTT_SOURCE).read_bytes(),
        parent_raw_asset_ids=[MARRIOTT_RAW_ID],
        storage_uri="synthetic/derived.json",
    )

    def locator(*, row: int, column: int) -> Dict[str, object]:
        """Return an exact locator from the expanded Evidence Authority."""
        return cell_locator(
            asset=asset,
            table_id="table_000011",
            row_index=row,
            column_index=column,
        )

    return json.dumps(
        {
            "disclosure_group": "lodging_kpi_table",
            "table_locator": {
                "derived_asset_id": asset["derived_asset_id"],
                "table_id": "table_000011",
            },
            "candidates": [
                {
                    "role": "occupancy",
                    "claimed_raw_value": "69.3",
                    "claimed_period": "FY2025",
                    "claimed_reported_unit": "percent",
                    "claimed_scope": [
                        {
                            "dimension": "property_population",
                            "raw_value": "Comparable Systemwide Properties",
                            "evidence_locator_ids": ["population"],
                        },
                        {
                            "dimension": "operating_scope",
                            "raw_value": "Comparable Systemwide Properties",
                            "evidence_locator_ids": ["population"],
                        },
                        {
                            "dimension": "geography",
                            "raw_value": "Worldwide",
                            "evidence_locator_ids": ["geography"],
                        },
                    ],
                    "locator": locator(row=26, column=15),
                    "scope_evidence_locators": [
                        {
                            "id": "population",
                            "supports_dimensions": [
                                "property_population", "operating_scope",
                            ],
                            "location_type": "label",
                            "locator": locator(row=18, column=0),
                            "raw_text": "Comparable Systemwide Properties",
                        },
                        {
                            "id": "geography",
                            "supports_dimensions": ["geography"],
                            "location_type": "row",
                            "locator": locator(row=26, column=0),
                            "raw_text": "\nWorldwide (2)",
                        },
                    ],
                    "competing_candidates": [],
                },
            ],
            "unresolved_competing_claims": [],
        },
        ensure_ascii=False,
    ).encode("utf-8")


class TableQualificationAuthorizationTest(unittest.TestCase):
    """Prove LIVE qualification cannot be a generic debugging request."""

    def test_synthetic_authority_binds_canary_and_rejects_drift(self) -> None:
        """Exercise auth, evidence, replay, root drift, and source drift."""
        with synthetic_no_d07_repository() as repo_root:
            response_bytes = _occupancy_response(repo_root=repo_root)
            calls = []
            clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
            with mock.patch.object(
                ai_adapter,
                "_REPOSITORY_ROOT",
                repo_root,
            ), mock.patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "synthetic-only"},
                clear=False,
            ):
                authorization = qualification.issue_table_qualification_authorization(
                    repo_root=repo_root,
                    family_id="lodging_kpi_table",
                    task_contract_id="lodging_occupancy_table_v2",
                    qualification_ordinal=1,
                )
                binding = authorization.as_mapping()
                concurrent_bindings = [
                    qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_revpar_table_v2",
                        qualification_ordinal=1,
                    ).as_mapping(),
                    qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="financial_statement",
                        task_contract_id=(
                            "financial_assets_under_management_table_v1"
                        ),
                        qualification_ordinal=1,
                    ).as_mapping(),
                ]

                def ledger_entry(
                    *, value: Dict[str, object], ordinal: int,
                ) -> Dict[str, object]:
                    """Build one strict no-network row for append-lock coverage."""
                    body = {
                        "record_type": (
                            "TABLE_QUALIFICATION_PROVIDER_LEDGER_ENTRY"
                        ),
                        "qualification_authorization": value,
                        "qualification_authorization_id": value[
                            "qualification_authorization_id"
                        ],
                        "qualification_task_plan_id": value[
                            "qualification_task_plan_id"
                        ],
                        "qualification_cycle_id": value[
                            "qualification_cycle_id"
                        ],
                        "freeze_receipt_id": value["freeze_receipt_id"],
                        "family_id": value["family_id"],
                        "task_contract_id": value["task_contract_id"],
                        "qualification_ordinal": value[
                            "qualification_ordinal"
                        ],
                        "source_binding_hash": value["source_binding_hash"],
                        "run_id": value["run_id"],
                        "attempt_id": "attempt:concurrent:{}".format(ordinal),
                        "request_body_sha256": "{:064x}".format(ordinal),
                        "provider_request_id": "request:concurrent:{}".format(
                            ordinal
                        ),
                        "transport_observation": {
                            "egress_attempted": True,
                            "test_only": "concurrent-lock",
                        },
                    }
                    return {
                        **body,
                        "qualification_provider_ledger_entry_id": content_hash(
                            value=body,
                        ),
                    }

                concurrent_entries = [
                    ledger_entry(value=value, ordinal=index)
                    for index, value in enumerate(concurrent_bindings, start=1)
                ]
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(
                            qualification._append_qualification_ledger_entry,
                            repo_root=repo_root,
                            binding=value,
                            entry=entry,
                        )
                        for value, entry in zip(
                            concurrent_bindings,
                            concurrent_entries,
                        )
                    ]
                    for future in futures:
                        future.result()
                concurrent_rows = [
                    json.loads(line)
                    for line in (
                        repo_root / binding["qualification_provider_ledger_path"]
                    ).read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(
                    {
                        entry["qualification_provider_ledger_entry_id"]
                        for entry in concurrent_entries
                    },
                    {
                        row["qualification_provider_ledger_entry_id"]
                        for row in concurrent_rows
                    },
                )
                adapter = ai_adapter.build_invocation_controlled_transport_adapter(
                    release_input_plan_id=binding["qualification_task_plan_id"],
                    workspace_dir=(
                        repo_root / binding["wb3_workspace_relative_path"]
                    ),
                    owner_token="synthetic-owner",
                )

                def transport(
                    *, prepared_request: object, egress_capability: object,
                ) -> TransportResult:
                    """Return one valid mock transport result without a socket."""
                    outbound, schema = build_provider_request_body(
                        policy=adapter.policy,
                        reader_request_bytes=(
                            prepared_request.prepared_request.request_bytes
                        ),
                    )
                    calls.append(outbound)
                    policy = adapter.policy
                    return TransportResult(
                        response_bytes=response_bytes,
                        provider_request_id="request:synthetic-qualification",
                        observation=TransportObservation(
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
                            request_body_bytes=len(outbound),
                        ),
                        raw_response_bytes=(
                            b'{"usage":{"prompt_tokens":10,'
                            b'"completion_tokens":2}}'
                        ),
                        outbound_request_bytes=outbound,
                        output_schema_bytes=schema,
                    )

                with mock.patch.object(
                    ai_adapter._InvocationControllerTransport,
                    "transport_kind",
                    "MOCK",
                ), mock.patch.object(
                    adapter,
                    "_complete_repository_transport",
                    side_effect=transport,
                ), mock.patch.object(
                    qualification,
                    "build_invocation_controlled_transport_adapter",
                    return_value=adapter,
                ):
                    created = qualification.execute_table_qualification_task(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                        target_period={
                            "fiscal_year": 2025,
                            "period_start": "2025-01-01",
                            "period_end": "2025-12-31",
                        },
                        owner_token="synthetic-owner",
                        clock=clock,
                    )
                run_dir = repo_root / binding["run_directory_relative_path"]
                finalized = finalize_reviewed_direct_results(
                    run_dir=run_dir,
                    repo_root=repo_root,
                )
                records_path = run_dir / "records.jsonl"
                ledger_path = (
                    repo_root / binding["qualification_provider_ledger_path"]
                )
                original_records = records_path.read_bytes()
                original_ledger = ledger_path.read_bytes()

                def write_records(value: list[Dict[str, object]]) -> None:
                    """Persist test-only canonical-enough JSONL mutation bytes."""
                    atomic_write_bytes(
                        path=records_path,
                        content=(
                            "\n".join(
                                json.dumps(
                                    record,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                                for record in value
                            )
                            + "\n"
                        ).encode("utf-8"),
                    )

                def refresh_evidence_link(
                    *, value: list[Dict[str, object]], entry: Dict[str, object],
                ) -> None:
                    """Keep link/ID syntactically valid for deeper ledger checks."""
                    evidence_value = next(
                        record
                        for record in value
                        if record["record_type"]
                        == "TABLE_QUALIFICATION_EVIDENCE"
                    )
                    evidence_value["provider_ledger_entry_id"] = entry[
                        "qualification_provider_ledger_entry_id"
                    ]
                    evidence_body = {
                        key: item
                        for key, item in evidence_value.items()
                        if key != "qualification_evidence_id"
                    }
                    evidence_value["qualification_evidence_id"] = content_hash(
                        value=evidence_body,
                    )

                def mutate_ledger(
                    *, mutation: str,
                    apply: object,
                    refresh_link: bool = True,
                ) -> None:
                    """Require every ledger/evidence mutation to fail formal freeze."""
                    values = [
                        json.loads(line)
                        for line in original_records.decode("utf-8").splitlines()
                    ]
                    rows = [
                        json.loads(line)
                        for line in original_ledger.decode("utf-8").splitlines()
                    ]
                    target = next(
                        row
                        for row in rows
                        if row["qualification_authorization_id"]
                        == binding["qualification_authorization_id"]
                    )
                    apply(target)
                    if mutation != "ledger_entry_id":
                        target["qualification_provider_ledger_entry_id"] = (
                            qualification._expected_ledger_entry_identifier(
                                entry=target,
                            )
                        )
                    if refresh_link:
                        refresh_evidence_link(value=values, entry=target)
                    write_records(values)
                    atomic_write_bytes(
                        path=ledger_path,
                        content=(
                            "\n".join(
                                json.dumps(
                                    row,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                                for row in rows
                            )
                            + "\n"
                        ).encode("utf-8"),
                    )
                    try:
                        with self.subTest(formal_mutation=mutation), self.assertRaises(
                            RunStoreError,
                        ):
                            validate_and_freeze_run(
                                run_dir=run_dir,
                                repo_root=repo_root,
                            )
                    finally:
                        atomic_write_bytes(
                            path=records_path,
                            content=original_records,
                        )
                        atomic_write_bytes(
                            path=ledger_path,
                            content=original_ledger,
                        )

                evidence_values = [
                    json.loads(line)
                    for line in original_records.decode("utf-8").splitlines()
                ]
                evidence_mutation = next(
                    value
                    for value in evidence_values
                    if value["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
                )
                evidence_mutation["qualification_evidence_id"] = (
                    "sha256:" + "0" * 64
                )
                write_records(evidence_values)
                with self.assertRaises(RunStoreError):
                    validate_and_freeze_run(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                atomic_write_bytes(path=records_path, content=original_records)
                mutate_ledger(
                    mutation="ledger_entry_id",
                    apply=lambda value: value.update({
                        "qualification_provider_ledger_entry_id": (
                            "sha256:" + "1" * 64
                        ),
                    }),
                    refresh_link=False,
                )
                mutate_ledger(
                    mutation="provider_request_id",
                    apply=lambda value: value.update({
                        "provider_request_id": "request:tampered-provider",
                    }),
                )
                mutate_ledger(
                    mutation="transport_observation",
                    apply=lambda value: value["transport_observation"].update({
                        "timeout_seconds": 999,
                    }),
                )

                def mutate_authority_field(
                    value: Dict[str, object], field: str, replacement: object,
                ) -> None:
                    """Change one duplicated ledger authority fact coherently."""
                    value[field] = replacement
                    value["qualification_authorization"][field] = replacement

                mutate_ledger(
                    mutation="family",
                    apply=lambda value: mutate_authority_field(
                        value,
                        "family_id",
                        "financial_statement",
                    ),
                )
                mutate_ledger(
                    mutation="task",
                    apply=lambda value: mutate_authority_field(
                        value,
                        "task_contract_id",
                        "lodging_revpar_table_v2",
                    ),
                )
                mutate_ledger(
                    mutation="ordinal",
                    apply=lambda value: mutate_authority_field(
                        value,
                        "qualification_ordinal",
                        2,
                    ),
                )
                mutate_ledger(
                    mutation="source_binding",
                    apply=lambda value: mutate_authority_field(
                        value,
                        "source_binding_hash",
                        "sha256:" + "2" * 64,
                    ),
                )
                mutate_ledger(
                    mutation="request_body_hash",
                    apply=lambda value: value.update({
                        "request_body_sha256": "3" * 64,
                    }),
                )
                frozen = validate_and_freeze_run(
                    run_dir=run_dir,
                    repo_root=repo_root,
                )
                replay = replay_frozen_results(
                    run_dir=run_dir,
                    repo_root=repo_root,
                )
                manifest, records, _decisions = load_frozen_run(
                    run_dir=run_dir,
                    repo_root=repo_root,
                )
                evidence = next(
                    record
                    for record in records
                    if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
                )
                ledger_rows = [
                    json.loads(line)
                    for line in (
                        repo_root / binding["qualification_provider_ledger_path"]
                    ).read_text(encoding="utf-8").splitlines()
                ]
                ledger_entry = next(
                    row
                    for row in ledger_rows
                    if row["qualification_authorization_id"]
                    == binding["qualification_authorization_id"]
                )
                self.assertEqual("PENDING_HUMAN_REVIEW", created["status"])
                self.assertEqual(1, len(calls))
                self.assertEqual(1, len(finalized["result_ids"]))
                self.assertEqual("FROZEN", frozen["status"])
                self.assertEqual(1, len(replay["results"]))
                self.assertEqual(binding, manifest["qualification_authorization"])
                self.assertEqual(binding, evidence["qualification_authorization"])
                self.assertEqual(
                    binding,
                    ledger_entry["qualification_authorization"],
                )
                self.assertEqual(
                    evidence["provider_ledger_entry_id"],
                    ledger_entry["qualification_provider_ledger_entry_id"],
                )

                source = binding["source_binding"]
                common = {
                    "repo_root": repo_root,
                    "company_id": "marriott_international",
                    "target_period": binding["target_period"],
                    "source_repo_relative_path": source["source_declaration"][
                        "source_repo_relative_path"
                    ],
                    "source_media_type": binding["source_media_type"],
                    "source_url": source["source_url"],
                    "accession": source["source_declaration"]["accession"],
                    "document_name": source["source_declaration"][
                        "document_name"
                    ],
                    "source_role": source["source_role"],
                    "request_attempt_id": source["request_attempt_id"],
                    "task_contract_id": "lodging_occupancy_table_v2",
                    "adapter": adapter,
                    "clock": clock,
                }
                mutations = {
                    "family_id": "financial_statement",
                    "task_contract_id": "lodging_revpar_table_v2",
                    "qualification_ordinal": 2,
                    "freeze_receipt_id": "sha256:" + "0" * 64,
                    "qualification_cycle_id": "sha256:" + "1" * 64,
                    "system_prompt_hash": "sha256:" + "2" * 64,
                    "output_schema_hash": "sha256:" + "3" * 64,
                    "target_period": {
                        "fiscal_year": 2024,
                        "period_start": "2024-01-01",
                        "period_end": "2024-12-31",
                    },
                    "source_media_type": "application/json",
                    "run_id": "run:qualification:table:" + "5" * 64,
                    "run_directory_relative_path": (
                        "artifacts/vnext/qualification/cycles/"
                        + "6" * 64 + "/runs/" + "7" * 64
                    ),
                }
                with mock.patch.object(
                    workflow,
                    "run_ai_attempt",
                    side_effect=AssertionError("transport bypass"),
                ) as blocked_transport:
                    for field, value in mutations.items():
                        forged = copy.deepcopy(binding)
                        forged[field] = value
                        forged_authorization = qualification.issue_table_qualification_authorization(
                            repo_root=repo_root,
                            family_id="lodging_kpi_table",
                            task_contract_id="lodging_occupancy_table_v2",
                            qualification_ordinal=1,
                        )
                        object.__setattr__(
                            forged_authorization,
                            "_binding",
                            forged,
                        )
                        with self.subTest(field=field), self.assertRaises(
                            workflow.WorkflowError,
                        ):
                            workflow.create_table_task_review_run(
                                run_dir=repo_root / "synthetic-mutations" / field,
                                run_id="run:synthetic-mutation:" + field,
                                qualification_authorization=forged_authorization,
                                **common,
                            )
                    forged = copy.deepcopy(binding)
                    forged["source_binding"]["source_binding_hash"] = (
                        "sha256:" + "4" * 64
                    )
                    forged_authorization = qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                    )
                    object.__setattr__(
                        forged_authorization,
                        "_binding",
                        forged,
                    )
                    with self.assertRaises(workflow.WorkflowError):
                        workflow.create_table_task_review_run(
                            run_dir=repo_root / "synthetic-mutations/source",
                            run_id="run:synthetic-mutation:source",
                            qualification_authorization=forged_authorization,
                            **common,
                        )
                self.assertEqual(0, blocked_transport.call_count)

            root_paths = (
                "outputs/active_publication.json",
                "outputs/metrics_matrix.csv",
                "outputs/metric_evidence.csv",
                "REPORT_十公司财务指标.md",
            )
            expected_families = {"financial_statement", "lodging_kpi_table"}
            active_path = repo_root / "outputs/active_publication.json"
            active_original = active_path.read_bytes()
            active_path.write_bytes(active_original.replace(
                b"publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f",
                b"publication_000000000000000000000000000000000000000000000000000000000000",
                1,
            ))
            active_status = validate_table_qualification_freeze(
                repo_root=repo_root,
            )
            self.assertEqual(
                expected_families,
                set(active_status["invalidated_family_ids"]),
            )
            self.assertTrue(all(
                "r2_root:active_publication_id" in labels
                for labels in active_status["drift_by_family"].values()
            ))
            active_path.write_bytes(active_original)
            for relative in root_paths:
                path = repo_root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                status = validate_table_qualification_freeze(repo_root=repo_root)
                self.assertEqual(
                    expected_families,
                    set(status["invalidated_family_ids"]),
                )
                self.assertTrue(all(
                    any(label.startswith("r2_root:") for label in labels)
                    for labels in status["drift_by_family"].values()
                ))
                for family_id, task_contract_id in (
                    ("lodging_kpi_table", "lodging_occupancy_table_v2"),
                    (
                        "financial_statement",
                        "financial_assets_under_management_table_v1",
                    ),
                ):
                    with self.subTest(
                        root_drift=relative,
                        qualification_family=family_id,
                    ), self.assertRaises(qualification.QualificationError):
                        qualification.issue_table_qualification_authorization(
                            repo_root=repo_root,
                            family_id=family_id,
                            task_contract_id=task_contract_id,
                            qualification_ordinal=1,
                        )
                path.write_bytes(original)

            source_path = repo_root / "scripts/vnext/public_projection.py"
            source_path.write_bytes(source_path.read_bytes() + b"\n")
            for family_id, task_contract_id in (
                ("lodging_kpi_table", "lodging_occupancy_table_v2"),
                ("financial_statement", "financial_assets_under_management_table_v1"),
            ):
                with self.subTest(source_drift_family=family_id), self.assertRaises(
                    qualification.QualificationError,
                ):
                    qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id=family_id,
                        task_contract_id=task_contract_id,
                        qualification_ordinal=1,
                    )


if __name__ == "__main__":
    unittest.main()
