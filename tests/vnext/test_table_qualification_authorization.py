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
from typing import Dict, Iterator, Sequence
from unittest import mock

from tests.vnext.common import cell_locator
from vnext import ai_adapter, invocation_control, qualification, workflow
from vnext.ai_adapter import TransportAttemptError, TransportObservation
from vnext.ai_adapter import TransportResult
from vnext.ai_adapter import build_provider_request_body
from vnext.canonical import atomic_write_bytes, atomic_write_json, content_hash
from vnext.replay import replay_frozen_results
from vnext.run_store import load_frozen_run, load_run_for_status, RunStoreError
from vnext.run_store import validate_and_freeze_run
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


@contextmanager
def cloned_synthetic_no_d07_repositories(*, count: int) -> Iterator[list[Path]]:
    """Share one built authority while isolating each crash scenario's WB-3 state."""
    if type(count) is not int or count < 1:
        raise AssertionError("Synthetic clone count is invalid")
    with synthetic_no_d07_repository() as authority_root:
        _run_git(
            workdir=authority_root,
            arguments=[
                "add", "--",
                "artifacts/vnext/table_qualification_freeze/stage_a_validation",
            ],
        )
        _run_git(
            workdir=authority_root,
            arguments=[
                "-c", "user.name=synthetic", "-c",
                "user.email=synthetic@example.invalid", "commit", "-m",
                "synthetic stage-a overlay",
            ],
        )
        clones = []
        try:
            for ordinal in range(count):
                clone = authority_root.parent / "clone-{}".format(ordinal)
                _run_git(
                    workdir=authority_root,
                    arguments=["worktree", "add", "--detach", str(clone), "HEAD"],
                )
                clones.append(clone)
            yield clones
        finally:
            for clone in reversed(clones):
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(clone)],
                    cwd=authority_root,
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


def _revpar_response(*, repo_root: Path) -> bytes:
    """Build one valid Marriott single-role RevPAR response."""
    asset = build_table_grid(
        html_bytes=(repo_root / MARRIOTT_SOURCE).read_bytes(),
        parent_raw_asset_ids=[MARRIOTT_RAW_ID],
        storage_uri="synthetic/derived.json",
    )

    def locator(*, row: int, column: int) -> Dict[str, object]:
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
                    "role": "revpar",
                    "claimed_raw_value": "128.80",
                    "claimed_period": "FY2025",
                    "claimed_reported_unit": "USD",
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
                    "locator": locator(row=26, column=4),
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


@contextmanager
def mocked_live_table_transport(
    *, repo_root: Path, binding: Dict[str, object], response_bytes: bytes,
    calls: list[bytes], provider_request_id: str,
) -> Iterator[None]:
    """Patch only the socket edge while exercising the real auth chain."""
    with mock.patch.object(
        ai_adapter,
        "_REPOSITORY_ROOT",
        repo_root,
    ), mock.patch.dict(
        os.environ,
        {"DEEPSEEK_API_KEY": "synthetic-only"},
        clear=False,
    ):
        adapter = ai_adapter.build_invocation_controlled_transport_adapter(
            release_input_plan_id=binding["qualification_task_plan_id"],
            workspace_dir=repo_root / binding["wb3_workspace_relative_path"],
            owner_token="synthetic-owner",
        )

        def transport(
            *, prepared_request: object, egress_capability: object,
        ) -> TransportResult:
            """Return a schema-valid test response after a real reservation."""
            outbound, schema = build_provider_request_body(
                policy=adapter.policy,
                reader_request_bytes=prepared_request.prepared_request.request_bytes,
            )
            calls.append(outbound)
            policy = adapter.policy
            return TransportResult(
                response_bytes=response_bytes,
                provider_request_id=provider_request_id,
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
                    b'{"usage":{"prompt_tokens":10,"completion_tokens":2}}'
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
            yield


@contextmanager
def mocked_live_table_failure_transport(
    *, repo_root: Path, binding: Dict[str, object],
    outcomes: Sequence[tuple[str, int]], calls: list[bytes],
    request_label: str,
) -> Iterator[None]:
    """Exercise the full LIVE/WB-3 path with exact injected failures only."""
    with mock.patch.object(
        ai_adapter,
        "_REPOSITORY_ROOT",
        repo_root,
    ), mock.patch.dict(
        os.environ,
        {"DEEPSEEK_API_KEY": "synthetic-only"},
        clear=False,
    ):
        adapter = ai_adapter.build_invocation_controlled_transport_adapter(
            release_input_plan_id=binding["qualification_task_plan_id"],
            workspace_dir=repo_root / binding["wb3_workspace_relative_path"],
            owner_token="synthetic-owner",
        )
        remaining = list(outcomes)

        def transport(
            *, prepared_request: object, egress_capability: object,
        ) -> TransportResult:
            """Return one named failure after the real reservation marker."""
            if not remaining:
                raise AssertionError("provider transport reinvoked")
            error_class, status_code = remaining.pop(0)
            outbound, schema = build_provider_request_body(
                policy=adapter.policy,
                reader_request_bytes=prepared_request.prepared_request.request_bytes,
            )
            calls.append(outbound)
            policy = adapter.policy
            observation = TransportObservation(
                egress_attempted=True,
                provider=policy.provider,
                model=policy.model,
                model_requested=policy.model,
                model_returned="none",
                api=policy.api,
                store=False,
                endpoint_host=policy.endpoint_host,
                region=policy.region,
                retention=policy.retention,
                data_use=policy.data_use,
                timeout_seconds=policy.timeout_seconds,
                retry_count=policy.retry_count,
                # D-35 creates the second WB-3 attempt; it is not a D-01
                # transport-internal retry, so the per-observation count
                # remains zero under the frozen D-01 policy.
                retries_performed=0,
                maximum_payload_bytes=policy.maximum_payload_bytes,
                filing_egress_policy=policy.filing_egress_policy,
                request_body_bytes=len(outbound),
            )
            raise TransportAttemptError(
                "synthetic qualification failure",
                observation=observation,
                provider_request_id="request:{}:{}".format(
                    request_label, len(calls),
                ),
                raw_response_bytes=None,
                error_class=error_class,
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
            yield


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

    def test_interrupted_exact_success_materializes_without_second_transport(
        self,
    ) -> None:
        """Recover every durable crash boundary without a second transport."""
        phases = (
            "AFTER_CREATE_RUN",
            "AFTER_EXACT_SUCCESS",
            "AFTER_ATTEMPT_PAYLOAD",
            "AFTER_ATTEMPT_RECORD",
            "AFTER_LEDGER",
            "AFTER_QUALIFICATION_EVIDENCE",
            "AFTER_CANDIDATE_EVIDENCE",
            "AFTER_REVIEW_UNIT",
            "AFTER_REVIEW_ASSETS",
            "AFTER_CHECKPOINT_REMOVAL",
        )

        class InjectedCrash(RuntimeError):
            """Stop a test execution after one durable recovery boundary."""

        with cloned_synthetic_no_d07_repositories(count=len(phases)) as roots:
            for index, (phase, repo_root) in enumerate(zip(phases, roots)):
                with self.subTest(phase=phase):
                    clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
                    (repo_root / "outputs/active_publication.json.lock").touch()
                    binding = qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                    ).as_mapping()
                    calls: list[bytes] = []
                    response = _occupancy_response(repo_root=repo_root)

                    def crash_here(observed: str) -> None:
                        if observed == phase:
                            raise InjectedCrash(observed)

                    common = {
                        "repo_root": repo_root,
                        "family_id": "lodging_kpi_table",
                        "task_contract_id": "lodging_occupancy_table_v2",
                        "qualification_ordinal": 1,
                        "target_period": binding["target_period"],
                        "owner_token": "synthetic-owner",
                        "clock": clock,
                    }
                    request_id = "request:recovery-{}".format(index)
                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding,
                        response_bytes=response,
                        calls=calls,
                        provider_request_id=request_id,
                    ), mock.patch.object(
                        workflow,
                        "_TABLE_QUALIFICATION_RECOVERY_HOOK",
                        side_effect=crash_here,
                    ):
                        with self.assertRaises(InjectedCrash):
                            qualification.execute_table_qualification_task(**common)
                    run_dir = repo_root / binding["run_directory_relative_path"]
                    checkpoint = run_dir / "qualification_recovery.json"
                    if phase == "AFTER_EXACT_SUCCESS":
                        # Simulate the narrow process-loss window in which
                        # WB-3 has retained the accepted response but the
                        # Run-local materialization checkpoint is absent.
                        checkpoint.unlink()
                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding,
                        response_bytes=response,
                        calls=calls,
                        provider_request_id=request_id,
                    ):
                        resumed = qualification.execute_table_qualification_task(
                            **common,
                        )
                    expected_state = (
                        "OPEN_BEFORE_EGRESS"
                        if phase == "AFTER_CREATE_RUN"
                        else "COMPLETE_OPEN_PENDING_REVIEW"
                        if phase == "AFTER_CHECKPOINT_REMOVAL"
                        else "EXACT_SUCCESS_NOT_MATERIALIZED"
                    )
                    if phase == "AFTER_CHECKPOINT_REMOVAL":
                        self.assertEqual(expected_state, resumed["status"])
                    else:
                        self.assertEqual(expected_state, resumed["recovery_state"])
                    self.assertEqual(1, len(calls))
                    self.assertFalse(checkpoint.exists())
                    manifest, records, _decisions = load_run_for_status(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    review_unit = next(
                        record for record in records
                        if record["record_type"] == "REVIEW_UNIT"
                    )
                    review_dir = run_dir / "review" / review_unit[
                        "review_unit_hash"
                    ]
                    self.assertEqual(
                        {"review_context.json", "review.md"},
                        {path.name for path in review_dir.iterdir()},
                    )
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=run_dir,
                        manifest=manifest,
                        records=records,
                    )
                    finalized = finalize_reviewed_direct_results(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    self.assertTrue(finalized["result_ids"])
                    frozen = validate_and_freeze_run(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    self.assertEqual("FROZEN", frozen["status"])
                    records_before = (run_dir / "records.jsonl").read_bytes()
                    ledger_path = repo_root / binding[
                        "qualification_provider_ledger_path"
                    ]
                    ledger_before = ledger_path.read_bytes()
                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding,
                        response_bytes=response,
                        calls=calls,
                        provider_request_id=request_id,
                    ):
                        third = qualification.execute_table_qualification_task(
                            **common,
                        )
                    self.assertEqual("FROZEN", third["status"])
                    self.assertEqual(
                        records_before, (run_dir / "records.jsonl").read_bytes(),
                    )
                    self.assertEqual(ledger_before, ledger_path.read_bytes())
                    self.assertEqual(1, len(calls))

    def test_wb3_seal_recovery_materializes_authorized_success(self) -> None:
        """Recover a persisted WB-3 success before its execution seal exists."""
        phases = (
            "AFTER_SUCCESS_RESPONSE_PERSISTED",
            "AFTER_EXECUTION_SEALED",
        )

        class InjectedCrash(RuntimeError):
            """Stop at a durable invocation-control seal boundary."""

        with cloned_synthetic_no_d07_repositories(count=len(phases)) as roots:
            for phase, repo_root in zip(phases, roots):
                with self.subTest(phase=phase):
                    (repo_root / "outputs/active_publication.json.lock").touch()
                    clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
                    binding = qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                    ).as_mapping()
                    common = {
                        "repo_root": repo_root,
                        "family_id": "lodging_kpi_table",
                        "task_contract_id": "lodging_occupancy_table_v2",
                        "qualification_ordinal": 1,
                        "target_period": binding["target_period"],
                        "owner_token": "synthetic-owner",
                        "clock": clock,
                    }
                    calls: list[bytes] = []

                    def crash_here(observed: str) -> None:
                        if observed == phase:
                            raise InjectedCrash(observed)

                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding,
                        response_bytes=_occupancy_response(repo_root=repo_root),
                        calls=calls,
                        provider_request_id="request:seal:" + phase,
                    ), mock.patch.object(
                        invocation_control,
                        "_INVOCATION_TERMINAL_RECOVERY_HOOK",
                        side_effect=crash_here,
                    ), self.assertRaises(InjectedCrash):
                        qualification.execute_table_qualification_task(**common)
                    self.assertEqual(1, len(calls))

                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding,
                        response_bytes=_occupancy_response(repo_root=repo_root),
                        calls=calls,
                        provider_request_id="request:seal:" + phase,
                    ), mock.patch.object(
                        invocation_control,
                        "_process_is_alive",
                        return_value=False,
                    ):
                        resumed = qualification.execute_table_qualification_task(
                            **common,
                        )
                    self.assertEqual("PENDING_HUMAN_REVIEW", resumed["status"])
                    self.assertEqual(1, len(calls))
                    run_dir = repo_root / binding["run_directory_relative_path"]
                    manifest, records, _decisions = load_run_for_status(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=run_dir,
                        manifest=manifest,
                        records=records,
                    )
                    terminals = qualification.qualification_remote_egress_terminals(
                        workspace_dir=(
                            repo_root / binding["wb3_workspace_relative_path"]
                        ),
                    )
                    self.assertEqual(["SUCCEEDED"], [
                        terminal["status"] for terminal in terminals
                    ])

    def test_cycle_blocks_other_terminal_until_wb3_success_materializes(
        self,
    ) -> None:
        """A WB-3 success outside Run records blocks every cycle finalization."""
        scenarios = ("checkpoint_present", "checkpoint_deleted")

        class InjectedCrash(RuntimeError):
            """Stop after WB-3 success but before any Run attempt record."""

        with cloned_synthetic_no_d07_repositories(
            count=len(scenarios),
        ) as roots:
            for mode, repo_root in zip(scenarios, roots):
                with self.subTest(checkpoint_mode=mode):
                    (repo_root / "outputs/active_publication.json.lock").touch()
                    clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
                    authorization_a = (
                        qualification.issue_table_qualification_authorization(
                            repo_root=repo_root,
                            family_id="lodging_kpi_table",
                            task_contract_id="lodging_occupancy_table_v2",
                            qualification_ordinal=1,
                        )
                    )
                    binding_a = authorization_a.as_mapping()
                    authorization_b = (
                        qualification.issue_table_qualification_authorization(
                            repo_root=repo_root,
                            family_id="lodging_kpi_table",
                            task_contract_id="lodging_revpar_table_v2",
                            qualification_ordinal=1,
                        )
                    )
                    binding_b = authorization_b.as_mapping()
                    calls_a: list[bytes] = []
                    calls_b: list[bytes] = []
                    common_a = {
                        "repo_root": repo_root,
                        "family_id": "lodging_kpi_table",
                        "task_contract_id": "lodging_occupancy_table_v2",
                        "qualification_ordinal": 1,
                        "target_period": binding_a["target_period"],
                        "owner_token": "synthetic-owner",
                        "clock": clock,
                    }
                    common_b = {
                        "repo_root": repo_root,
                        "family_id": "lodging_kpi_table",
                        "task_contract_id": "lodging_revpar_table_v2",
                        "qualification_ordinal": 1,
                        "target_period": binding_b["target_period"],
                        "owner_token": "synthetic-owner",
                        "clock": clock,
                    }

                    def crash_after_success(phase: str) -> None:
                        if phase == "AFTER_EXACT_SUCCESS":
                            raise InjectedCrash(phase)

                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding_a,
                        response_bytes=_occupancy_response(repo_root=repo_root),
                        calls=calls_a,
                        provider_request_id="request:pending-a",
                    ), mock.patch.object(
                        workflow,
                        "_TABLE_QUALIFICATION_RECOVERY_HOOK",
                        side_effect=crash_after_success,
                    ):
                        with self.assertRaises(InjectedCrash):
                            qualification.execute_table_qualification_task(
                                **common_a,
                            )
                    run_a = repo_root / binding_a["run_directory_relative_path"]
                    checkpoint_a = run_a / "qualification_recovery.json"
                    self.assertTrue(checkpoint_a.is_file())
                    if mode == "checkpoint_deleted":
                        checkpoint_a.unlink()
                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding_b,
                        response_bytes=_revpar_response(repo_root=repo_root),
                        calls=calls_b,
                        provider_request_id="request:pending-b",
                    ):
                        created_b = qualification.execute_table_qualification_task(
                            **common_b,
                        )
                    self.assertEqual("PENDING_HUMAN_REVIEW", created_b["status"])
                    run_b = repo_root / binding_b["run_directory_relative_path"]
                    with self.assertRaisesRegex(
                        workflow.WorkflowError,
                        "TABLE_QUALIFICATION_CYCLE_PENDING_MATERIALIZATION",
                    ):
                        finalize_reviewed_direct_results(
                            run_dir=run_b,
                            repo_root=repo_root,
                        )
                    self.assertEqual(1, len(calls_a))
                    self.assertEqual(1, len(calls_b))
                    with mocked_live_table_transport(
                        repo_root=repo_root,
                        binding=binding_a,
                        response_bytes=_occupancy_response(repo_root=repo_root),
                        calls=calls_a,
                        provider_request_id="request:pending-a",
                    ):
                        resumed_a = qualification.execute_table_qualification_task(
                            **common_a,
                        )
                    self.assertEqual(
                        "EXACT_SUCCESS_NOT_MATERIALIZED",
                        resumed_a["recovery_state"],
                    )
                    self.assertEqual(1, len(calls_a))
                    for run_dir in (run_a, run_b):
                        finalized = finalize_reviewed_direct_results(
                            run_dir=run_dir,
                            repo_root=repo_root,
                        )
                        self.assertTrue(finalized["result_ids"])
                        frozen = validate_and_freeze_run(
                            run_dir=run_dir,
                            repo_root=repo_root,
                        )
                        self.assertEqual("FROZEN", frozen["status"])

    def test_remote_terminal_failures_are_stable_without_second_transport(
        self,
    ) -> None:
        """HTTP/schema terminal outcomes never re-enter success materialization."""
        scenarios = (
            ("http_400", "HTTP_400", 400),
            ("http_402", "HTTP_402", 402),
            ("schema_violation", "SCHEMA_VIOLATION", 200),
        )
        with cloned_synthetic_no_d07_repositories(
            count=len(scenarios),
        ) as roots:
            for (name, error_class, status_code), repo_root in zip(
                scenarios, roots,
            ):
                with self.subTest(terminal=name):
                    (repo_root / "outputs/active_publication.json.lock").touch()
                    clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
                    authorization = qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                    )
                    binding = authorization.as_mapping()
                    calls: list[bytes] = []
                    with mock.patch.object(
                        ai_adapter,
                        "_REPOSITORY_ROOT",
                        repo_root,
                    ), mock.patch.dict(
                        os.environ,
                        {"DEEPSEEK_API_KEY": "synthetic-only"},
                        clear=False,
                    ):
                        adapter = ai_adapter.build_invocation_controlled_transport_adapter(
                            release_input_plan_id=binding[
                                "qualification_task_plan_id"
                            ],
                            workspace_dir=(
                                repo_root / binding[
                                    "wb3_workspace_relative_path"
                                ]
                            ),
                            owner_token="synthetic-owner",
                        )

                        def terminal_transport(
                            *, prepared_request: object,
                            egress_capability: object,
                        ) -> TransportResult:
                            outbound, schema = build_provider_request_body(
                                policy=adapter.policy,
                                reader_request_bytes=(
                                    prepared_request.prepared_request.request_bytes
                                ),
                            )
                            calls.append(outbound)
                            policy = adapter.policy
                            observation = TransportObservation(
                                egress_attempted=True,
                                provider=policy.provider,
                                model=policy.model,
                                model_requested=policy.model,
                                model_returned=(
                                    policy.model
                                    if error_class == "SCHEMA_VIOLATION"
                                    else "none"
                                ),
                                api=policy.api,
                                store=False,
                                endpoint_host=policy.endpoint_host,
                                region=policy.region,
                                retention=policy.retention,
                                data_use=policy.data_use,
                                timeout_seconds=policy.timeout_seconds,
                                retry_count=policy.retry_count,
                                retries_performed=0,
                                maximum_payload_bytes=(
                                    policy.maximum_payload_bytes
                                ),
                                filing_egress_policy=(
                                    policy.filing_egress_policy
                                ),
                                request_body_bytes=len(outbound),
                            )
                            if error_class == "SCHEMA_VIOLATION":
                                return TransportResult(
                                    response_bytes=b"{}",
                                    provider_request_id=(
                                        "request:" + name
                                    ),
                                    observation=observation,
                                    raw_response_bytes=b"{}",
                                    outbound_request_bytes=outbound,
                                    output_schema_bytes=schema,
                                )
                            raise TransportAttemptError(
                                "synthetic terminal failure",
                                observation=observation,
                                provider_request_id="request:" + name,
                                raw_response_bytes=None,
                                error_class=error_class,
                                outbound_request_bytes=outbound,
                                output_schema_bytes=schema,
                            )

                        common = {
                            "repo_root": repo_root,
                            "family_id": "lodging_kpi_table",
                            "task_contract_id": "lodging_occupancy_table_v2",
                            "qualification_ordinal": 1,
                            "target_period": binding["target_period"],
                            "owner_token": "synthetic-owner",
                            "clock": clock,
                        }
                        with mock.patch.object(
                            ai_adapter._InvocationControllerTransport,
                            "transport_kind",
                            "MOCK",
                        ), mock.patch.object(
                            adapter,
                            "_complete_repository_transport",
                            side_effect=terminal_transport,
                        ), mock.patch.object(
                            qualification,
                            "build_invocation_controlled_transport_adapter",
                            return_value=adapter,
                        ):
                            initial = qualification.execute_table_qualification_task(
                                **common,
                            )
                    self.assertEqual("FAILED_TERMINAL", initial["status"])
                    self.assertEqual(1, len(calls))
                    run_dir = repo_root / binding["run_directory_relative_path"]
                    manifest, records, _decisions = load_run_for_status(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    attempts = [
                        record for record in records
                        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                    ]
                    evidence = [
                        record for record in records
                        if record["record_type"]
                        == "TABLE_QUALIFICATION_EVIDENCE"
                    ]
                    self.assertEqual(1, len(attempts))
                    self.assertEqual("FAILED", attempts[0]["status"])
                    self.assertEqual(error_class, attempts[0]["error_class"])
                    self.assertEqual(1, len(evidence))
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=run_dir,
                        manifest=manifest,
                        records=records,
                    )
                    wb3_terminals = qualification.qualification_remote_egress_terminals(
                        workspace_dir=(
                            repo_root / binding["wb3_workspace_relative_path"]
                        ),
                    )
                    self.assertEqual(1, len(wb3_terminals))
                    self.assertEqual("FAILED_TERMINAL", wb3_terminals[0]["status"])
                    self.assertTrue(wb3_terminals[0]["batch_terminal"])
                    mismatched_terminal = {
                        **wb3_terminals[0],
                        "status": "SUCCEEDED",
                        "batch_terminal": False,
                    }
                    mismatched_terminal[
                        "qualification_wb3_remote_egress_terminal_id"
                    ] = content_hash(value={
                        field: mismatched_terminal[field]
                        for field in mismatched_terminal
                        if field != "qualification_wb3_remote_egress_terminal_id"
                    })
                    with mock.patch.object(
                        qualification,
                        "qualification_remote_egress_terminals",
                        return_value=[mismatched_terminal],
                    ), self.assertRaisesRegex(
                        qualification.QualificationError,
                        "Run attempt differs from WB-3 terminal",
                    ):
                        qualification.validate_table_qualification_cycle_exact_set(
                            repo_root=repo_root,
                            binding=binding,
                        )
                    records_before = (run_dir / "records.jsonl").read_bytes()
                    ledger_path = repo_root / binding[
                        "qualification_provider_ledger_path"
                    ]
                    ledger_before = ledger_path.read_bytes()
                    with mock.patch.object(
                        qualification,
                        "build_invocation_controlled_transport_adapter",
                        side_effect=AssertionError("transport path reached"),
                    ):
                        for _ in range(2):
                            resumed = qualification.execute_table_qualification_task(
                                **common,
                            )
                            self.assertEqual("FAILED_TERMINAL", resumed["status"])
                    self.assertEqual(1, len(calls))
                    self.assertEqual(
                        records_before, (run_dir / "records.jsonl").read_bytes(),
                    )
                    self.assertEqual(ledger_before, ledger_path.read_bytes())

    def test_interrupted_remote_terminals_materialize_without_second_transport(
        self,
    ) -> None:
        """Recover failed/UNKNOWN terminal closure at every Run write boundary."""
        phases = (
            "AFTER_ATTEMPT_PAYLOAD",
            "AFTER_ATTEMPT_RECORD",
            "AFTER_LEDGER",
            "AFTER_QUALIFICATION_EVIDENCE",
        )
        scenarios = (
            ("http_400", (("HTTP_400", 400),), "FAILED_TERMINAL", 1),
            ("http_402", (("HTTP_402", 402),), "FAILED_TERMINAL", 1),
            (
                "unknown",
                (("UNKNOWN_REMOTE_OUTCOME", 0),),
                "UNKNOWN_REMOTE_OUTCOME",
                1,
            ),
            (
                "retry_exhausted",
                (("HTTP_429", 429), ("HTTP_429", 429)),
                "FAILED_TERMINAL",
                2,
            ),
        )

        class InjectedCrash(RuntimeError):
            """Stop after one durable Run materialization boundary."""

        with cloned_synthetic_no_d07_repositories(
            count=len(phases) * len(scenarios),
        ) as roots:
            for index, ((name, outcomes, expected, call_count), phase) in enumerate(
                (
                    (scenario, phase)
                    for scenario in scenarios
                    for phase in phases
                )
            ):
                repo_root = roots[index]
                with self.subTest(terminal=name, phase=phase):
                    (repo_root / "outputs/active_publication.json.lock").touch()
                    clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
                    binding = qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                    ).as_mapping()
                    common = {
                        "repo_root": repo_root,
                        "family_id": "lodging_kpi_table",
                        "task_contract_id": "lodging_occupancy_table_v2",
                        "qualification_ordinal": 1,
                        "target_period": binding["target_period"],
                        "owner_token": "synthetic-owner",
                        "clock": clock,
                    }
                    calls: list[bytes] = []

                    def crash_here(observed: str) -> None:
                        if observed == phase:
                            raise InjectedCrash(observed)

                    with mocked_live_table_failure_transport(
                        repo_root=repo_root,
                        binding=binding,
                        outcomes=outcomes,
                        calls=calls,
                        request_label="{}:{}".format(name, phase),
                    ), mock.patch.object(
                        workflow,
                        "_TABLE_QUALIFICATION_RECOVERY_HOOK",
                        side_effect=crash_here,
                    ):
                        with self.assertRaises(InjectedCrash):
                            qualification.execute_table_qualification_task(
                                **common,
                            )
                    self.assertEqual(call_count, len(calls))

                    with mocked_live_table_failure_transport(
                        repo_root=repo_root,
                        binding=binding,
                        outcomes=(),
                        calls=calls,
                        request_label="resume:" + name,
                    ):
                        if expected == "UNKNOWN_REMOTE_OUTCOME":
                            with self.assertRaises(
                                qualification.QualificationError,
                            ) as resumed_error:
                                qualification.execute_table_qualification_task(
                                    **common,
                                )
                            self.assertEqual(
                                "TABLE_QUALIFICATION_UNKNOWN_REMOTE_OUTCOME",
                                resumed_error.exception.code,
                            )
                        else:
                            resumed = qualification.execute_table_qualification_task(
                                **common,
                            )
                            self.assertEqual(expected, resumed["status"])
                    self.assertEqual(call_count, len(calls))
                    run_dir = repo_root / binding["run_directory_relative_path"]
                    manifest, records, _decisions = load_run_for_status(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=run_dir,
                        manifest=manifest,
                        records=records,
                    )
                    attempts = [
                        record for record in records
                        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                    ]
                    evidence = [
                        record for record in records
                        if record["record_type"]
                        == "TABLE_QUALIFICATION_EVIDENCE"
                    ]
                    self.assertEqual(1, len(attempts))
                    self.assertEqual(1, len(evidence))
                    records_before = (run_dir / "records.jsonl").read_bytes()
                    ledger_path = repo_root / binding[
                        "qualification_provider_ledger_path"
                    ]
                    ledger_before = ledger_path.read_bytes()
                    with mock.patch.object(
                        qualification,
                        "build_invocation_controlled_transport_adapter",
                        side_effect=AssertionError("provider path reached"),
                    ):
                        if expected == "UNKNOWN_REMOTE_OUTCOME":
                            with self.assertRaises(
                                qualification.QualificationError,
                            ):
                                qualification.execute_table_qualification_task(
                                    **common,
                                )
                        else:
                            third = qualification.execute_table_qualification_task(
                                **common,
                            )
                            self.assertEqual(expected, third["status"])
                    self.assertEqual(records_before, (run_dir / "records.jsonl").read_bytes())
                    self.assertEqual(ledger_before, ledger_path.read_bytes())
                    self.assertEqual(call_count, len(calls))

    def test_pre_egress_failure_leaves_ordinal_recoverable(self) -> None:
        """A local credential/preflight error creates no remote terminal closure."""
        with synthetic_no_d07_repository() as repo_root:
            (repo_root / "outputs/active_publication.json.lock").touch()
            clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
            binding = qualification.issue_table_qualification_authorization(
                repo_root=repo_root,
                family_id="lodging_kpi_table",
                task_contract_id="lodging_occupancy_table_v2",
                qualification_ordinal=1,
            ).as_mapping()
            common = {
                "repo_root": repo_root,
                "family_id": "lodging_kpi_table",
                "task_contract_id": "lodging_occupancy_table_v2",
                "qualification_ordinal": 1,
                "target_period": binding["target_period"],
                "owner_token": "synthetic-owner",
                "clock": clock,
            }
            with mock.patch.object(
                ai_adapter,
                "_REPOSITORY_ROOT",
                repo_root,
            ), mock.patch.dict(os.environ, {}, clear=True):
                pre_egress = qualification.execute_table_qualification_task(
                    **common,
                )
            self.assertEqual("PRE_EGRESS_FAILURE", pre_egress["status"])
            run_dir = repo_root / binding["run_directory_relative_path"]
            _manifest, records, _decisions = load_run_for_status(
                run_dir=run_dir,
                repo_root=repo_root,
            )
            self.assertEqual([], [
                record for record in records
                if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            ])
            self.assertEqual([], [
                record for record in records
                if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
            ])
            ledger_path = repo_root / binding["qualification_provider_ledger_path"]
            self.assertEqual(b"", ledger_path.read_bytes())
            calls: list[bytes] = []
            with mocked_live_table_transport(
                repo_root=repo_root,
                binding=binding,
                response_bytes=_occupancy_response(repo_root=repo_root),
                calls=calls,
                provider_request_id="request:repaired-pre-egress",
            ):
                repaired = qualification.execute_table_qualification_task(
                    **common,
                )
            self.assertEqual("PENDING_HUMAN_REVIEW", repaired["status"])
            self.assertEqual(1, len(calls))

    def test_exhausted_retryable_terminals_bind_cycle_evidence(self) -> None:
        """D-35 retry exhaustion remains one fully bound qualification terminal."""
        scenarios = (
            ("http_429", "HTTP_429", 429),
            ("timeout", "TIMEOUT", 0),
            ("recoverable_5xx", "RECOVERABLE_5XX", 500),
        )
        with cloned_synthetic_no_d07_repositories(
            count=len(scenarios),
        ) as roots:
            for (name, error_class, status_code), repo_root in zip(
                scenarios, roots,
            ):
                with self.subTest(terminal=name):
                    (repo_root / "outputs/active_publication.json.lock").touch()
                    clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
                    binding = qualification.issue_table_qualification_authorization(
                        repo_root=repo_root,
                        family_id="lodging_kpi_table",
                        task_contract_id="lodging_occupancy_table_v2",
                        qualification_ordinal=1,
                    ).as_mapping()
                    common = {
                        "repo_root": repo_root,
                        "family_id": "lodging_kpi_table",
                        "task_contract_id": "lodging_occupancy_table_v2",
                        "qualification_ordinal": 1,
                        "target_period": binding["target_period"],
                        "owner_token": "synthetic-owner",
                        "clock": clock,
                    }
                    calls: list[bytes] = []
                    with mocked_live_table_failure_transport(
                        repo_root=repo_root,
                        binding=binding,
                        outcomes=((error_class, status_code),) * 2,
                        calls=calls,
                        request_label="retry:" + name,
                    ):
                        initial = qualification.execute_table_qualification_task(
                            **common,
                        )
                    self.assertEqual("FAILED_TERMINAL", initial["status"])
                    self.assertEqual(2, len(calls))
                    run_dir = repo_root / binding["run_directory_relative_path"]
                    manifest, records, _decisions = load_run_for_status(
                        run_dir=run_dir,
                        repo_root=repo_root,
                    )
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=run_dir,
                        manifest=manifest,
                        records=records,
                    )
                    terminals = qualification.qualification_remote_egress_terminals(
                        workspace_dir=(
                            repo_root / binding["wb3_workspace_relative_path"]
                        ),
                    )
                    self.assertEqual(1, len(terminals))
                    terminal = terminals[0]
                    self.assertEqual("FAILED_RETRYABLE_FINAL", terminal["status"])
                    self.assertTrue(terminal["batch_terminal"])
                    self.assertEqual(2, len(terminal["egress_marker_ids"]))
                    self.assertEqual(2, len(terminal["provider_request_ids"]))
                    self.assertEqual(
                        ["FAILED_RETRYABLE", "FAILED_RETRYABLE_FINAL"],
                        terminal["attempt_statuses"],
                    )
                    self.assertEqual(
                        [error_class, error_class],
                        terminal["attempt_error_classes"],
                    )
                    mismatched_terminal = {
                        **terminal,
                        "provider_request_ids": list(reversed(
                            terminal["provider_request_ids"]
                        )),
                    }
                    mismatched_terminal[
                        "qualification_wb3_remote_egress_terminal_id"
                    ] = content_hash(value={
                        field: mismatched_terminal[field]
                        for field in mismatched_terminal
                        if field != "qualification_wb3_remote_egress_terminal_id"
                    })
                    with mock.patch.object(
                        qualification,
                        "qualification_remote_egress_terminals",
                        return_value=[mismatched_terminal],
                    ), self.assertRaises(qualification.QualificationError):
                        qualification.validate_table_qualification_cycle_exact_set(
                            repo_root=repo_root,
                            binding=binding,
                        )
                    records_before = (run_dir / "records.jsonl").read_bytes()
                    ledger_path = repo_root / binding[
                        "qualification_provider_ledger_path"
                    ]
                    ledger_before = ledger_path.read_bytes()
                    with mock.patch.object(
                        qualification,
                        "build_invocation_controlled_transport_adapter",
                        side_effect=AssertionError("provider path reached"),
                    ):
                        repeated = qualification.execute_table_qualification_task(
                            **common,
                        )
                    self.assertEqual("FAILED_TERMINAL", repeated["status"])
                    self.assertEqual(2, len(calls))
                    self.assertEqual(records_before, (run_dir / "records.jsonl").read_bytes())
                    self.assertEqual(ledger_before, ledger_path.read_bytes())

    def test_cycle_exact_set_uses_complete_concurrent_authorized_terminals(
        self,
    ) -> None:
        """Concurrent ledger appends must be owned by complete Run closures."""
        with synthetic_no_d07_repository() as repo_root:
            clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
            issued = [
                qualification.issue_table_qualification_authorization(
                    repo_root=repo_root,
                    family_id="lodging_kpi_table",
                    task_contract_id=task_contract_id,
                    qualification_ordinal=1,
                )
                for task_contract_id in (
                    "lodging_occupancy_table_v2",
                    "lodging_revpar_table_v2",
                )
            ]
            bindings = [value.as_mapping() for value in issued]
            responses = [
                _occupancy_response(repo_root=repo_root),
                _revpar_response(repo_root=repo_root),
            ]
            calls: list[bytes] = []
            with mock.patch.object(
                ai_adapter,
                "_REPOSITORY_ROOT",
                repo_root,
            ), mock.patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "synthetic-only"},
                clear=False,
            ):
                adapters = [
                    ai_adapter.build_invocation_controlled_transport_adapter(
                        release_input_plan_id=binding[
                            "qualification_task_plan_id"
                        ],
                        workspace_dir=(
                            repo_root / binding["wb3_workspace_relative_path"]
                        ),
                        owner_token="synthetic-owner",
                    )
                    for binding in bindings
                ]

                def transport_for(
                    *, adapter: object, response: bytes, request_id: str,
                ) -> object:
                    def transport(
                        *, prepared_request: object, egress_capability: object,
                    ) -> TransportResult:
                        outbound, schema = build_provider_request_body(
                            policy=adapter.policy,
                            reader_request_bytes=(
                                prepared_request.prepared_request.request_bytes
                            ),
                        )
                        calls.append(outbound)
                        policy = adapter.policy
                        return TransportResult(
                            response_bytes=response,
                            provider_request_id=request_id,
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
                                maximum_payload_bytes=(
                                    policy.maximum_payload_bytes
                                ),
                                filing_egress_policy=(
                                    policy.filing_egress_policy
                                ),
                                request_body_bytes=len(outbound),
                            ),
                            raw_response_bytes=(
                                b'{"usage":{"prompt_tokens":10,'
                                b'"completion_tokens":2}}'
                            ),
                            outbound_request_bytes=outbound,
                            output_schema_bytes=schema,
                        )
                    return transport

                side_effects = [
                    transport_for(
                        adapter=adapter,
                        response=response,
                        request_id="request:concurrent:{}".format(index),
                    )
                    for index, (adapter, response) in enumerate(
                        zip(adapters, responses), start=1,
                    )
                ]

                def create(index: int) -> Dict[str, object]:
                    binding = bindings[index]
                    source = binding["source_binding"]
                    declaration = source["source_declaration"]
                    return workflow.create_table_task_review_run(
                        repo_root=repo_root,
                        run_dir=(
                            repo_root / binding["run_directory_relative_path"]
                        ),
                        run_id=binding["run_id"],
                        company_id=declaration["company_id"],
                        target_period=binding["target_period"],
                        source_repo_relative_path=(
                            declaration["source_repo_relative_path"]
                        ),
                        source_media_type=binding["source_media_type"],
                        source_url=source["source_url"],
                        accession=declaration["accession"],
                        document_name=declaration["document_name"],
                        source_role=source["source_role"],
                        request_attempt_id=source["request_attempt_id"],
                        task_contract_id=binding["task_contract_id"],
                        adapter=adapters[index],
                        clock=clock,
                        qualification_authorization=issued[index],
                    )

                with mock.patch.object(
                    ai_adapter._InvocationControllerTransport,
                    "transport_kind",
                    "MOCK",
                ), mock.patch.object(
                    adapters[0],
                    "_complete_repository_transport",
                    side_effect=side_effects[0],
                ), mock.patch.object(
                    adapters[1],
                    "_complete_repository_transport",
                    side_effect=side_effects[1],
                ), concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    created = [future.result() for future in (
                        pool.submit(create, index) for index in range(2)
                    )]
            self.assertEqual(
                ["PENDING_HUMAN_REVIEW", "PENDING_HUMAN_REVIEW"],
                sorted(value["status"] for value in created),
            )
            self.assertEqual(2, len(calls))
            ledger_path = repo_root / bindings[0][
                "qualification_provider_ledger_path"
            ]
            rows = [
                json.loads(line) for line in ledger_path.read_text(
                    encoding="utf-8",
                ).splitlines()
            ]
            self.assertEqual(2, len(rows))
            self.assertEqual(
                2,
                len({
                    row["qualification_provider_ledger_entry_id"]
                    for row in rows
                }),
            )
            cycle_attempt_ids = set()
            cycle_evidence_ids = set()
            for binding in bindings:
                run_dir = repo_root / binding["run_directory_relative_path"]
                manifest, records, _decisions = load_run_for_status(
                    run_dir=run_dir,
                    repo_root=repo_root,
                )
                qualification.validate_table_qualification_run_bindings(
                    repo_root=repo_root,
                    run_dir=run_dir,
                    manifest=manifest,
                    records=records,
                )
                cycle_attempt_ids.update(
                    record["attempt_id"] for record in records
                    if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                    and record["transport_observation"]["egress_attempted"]
                )
                cycle_evidence_ids.update(
                    record["qualification_evidence_id"] for record in records
                    if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
                )
            self.assertEqual(2, len(cycle_attempt_ids))
            self.assertEqual(2, len(cycle_evidence_ids))
            ledger_before = ledger_path.read_bytes()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(
                        qualification._append_qualification_ledger_entry,
                        repo_root=repo_root,
                        binding=binding,
                        entry=next(
                            row for row in rows
                            if row["qualification_authorization_id"]
                            == binding["qualification_authorization_id"]
                        ),
                    )
                    for binding in bindings
                ]
                for future in futures:
                    future.result()
            self.assertEqual(ledger_before, ledger_path.read_bytes())
            divergent = copy.deepcopy(rows[0])
            divergent["provider_request_id"] = "request:divergent"
            divergent["qualification_provider_ledger_entry_id"] = (
                qualification._expected_ledger_entry_identifier(entry=divergent)
            )
            with self.assertRaises(qualification.QualificationError):
                qualification._append_qualification_ledger_entry(
                    repo_root=repo_root,
                    binding=bindings[0],
                    entry=divergent,
                )
            second_run_dir = repo_root / bindings[1][
                "run_directory_relative_path"
            ]
            hidden_run_dir = repo_root / "synthetic-hidden-terminal"
            second_run_dir.rename(hidden_run_dir)
            try:
                first_run_dir = repo_root / bindings[0][
                    "run_directory_relative_path"
                ]
                first_manifest, first_records, _decisions = load_run_for_status(
                    run_dir=first_run_dir,
                    repo_root=repo_root,
                )
                with self.assertRaises(qualification.QualificationError):
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=first_run_dir,
                        manifest=first_manifest,
                        records=first_records,
                    )
            finally:
                hidden_run_dir.rename(second_run_dir)
            second_records_path = second_run_dir / "records.jsonl"
            first_records_path = (
                repo_root / bindings[0]["run_directory_relative_path"]
                / "records.jsonl"
            )
            original_second_records = second_records_path.read_bytes()
            original_first_records = first_records_path.read_bytes()
            second_records = [
                json.loads(line)
                for line in original_second_records.decode("utf-8").splitlines()
            ]
            second_evidence = next(
                record for record in second_records
                if record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE"
            )
            try:
                # Real evidence is moved, never invented: the second terminal
                # becomes evidence-less while the first has an orphan extra.
                atomic_write_bytes(
                    path=second_records_path,
                    content=(
                        "\n".join(json.dumps(
                            record,
                            ensure_ascii=False,
                            sort_keys=True,
                        ) for record in second_records if record is not second_evidence)
                        + "\n"
                    ).encode("utf-8"),
                )
                atomic_write_bytes(
                    path=first_records_path,
                    content=(
                        original_first_records
                        + json.dumps(
                            second_evidence,
                            ensure_ascii=False,
                            sort_keys=True,
                        ).encode("utf-8")
                        + b"\n"
                    ),
                )
                first_manifest, first_records, _decisions = load_run_for_status(
                    run_dir=(
                        repo_root / bindings[0]["run_directory_relative_path"]
                    ),
                    repo_root=repo_root,
                )
                with self.assertRaises(qualification.QualificationError):
                    qualification.validate_table_qualification_run_bindings(
                        repo_root=repo_root,
                        run_dir=(
                            repo_root / bindings[0][
                                "run_directory_relative_path"
                            ]
                        ),
                        manifest=first_manifest,
                        records=first_records,
                    )
            finally:
                atomic_write_bytes(
                    path=second_records_path,
                    content=original_second_records,
                )
                atomic_write_bytes(
                    path=first_records_path,
                    content=original_first_records,
                )

    def test_unknown_remote_outcome_is_terminal_and_never_reinvokes(
        self,
    ) -> None:
        """An egress marker without terminal response cannot be retried."""
        with synthetic_no_d07_repository() as repo_root:
            clock = lambda: datetime(2026, 8, 21, tzinfo=timezone.utc)
            authorization = qualification.issue_table_qualification_authorization(
                repo_root=repo_root,
                family_id="lodging_kpi_table",
                task_contract_id="lodging_occupancy_table_v2",
                qualification_ordinal=1,
            )
            binding = authorization.as_mapping()
            calls: list[bytes] = []

            class InjectedCrash(RuntimeError):
                """Stop after WB-3 has persisted UNKNOWN but before Run writes."""
            with mock.patch.object(
                ai_adapter,
                "_REPOSITORY_ROOT",
                repo_root,
            ), mock.patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "synthetic-only"},
                clear=False,
            ):
                adapter = ai_adapter.build_invocation_controlled_transport_adapter(
                    release_input_plan_id=binding["qualification_task_plan_id"],
                    workspace_dir=(
                        repo_root / binding["wb3_workspace_relative_path"]
                    ),
                    owner_token="synthetic-owner",
                )

                def unknown_transport(
                    *, prepared_request: object, egress_capability: object,
                ) -> TransportResult:
                    outbound, schema = build_provider_request_body(
                        policy=adapter.policy,
                        reader_request_bytes=(
                            prepared_request.prepared_request.request_bytes
                        ),
                    )
                    calls.append(outbound)
                    policy = adapter.policy
                    raise TransportAttemptError(
                        "synthetic unknown remote outcome",
                        observation=TransportObservation(
                            egress_attempted=True,
                            provider=policy.provider,
                            model=policy.model,
                            model_requested=policy.model,
                            model_returned="none",
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
                        provider_request_id="request:unknown",
                        raw_response_bytes=None,
                        error_class="UNKNOWN_REMOTE_OUTCOME",
                        outbound_request_bytes=outbound,
                        output_schema_bytes=schema,
                    )

                common = {
                    "repo_root": repo_root,
                    "family_id": "lodging_kpi_table",
                    "task_contract_id": "lodging_occupancy_table_v2",
                    "qualification_ordinal": 1,
                    "target_period": binding["target_period"],
                    "owner_token": "synthetic-owner",
                    "clock": clock,
                }

                def crash_after_wb3(phase: str) -> None:
                    if phase == "AFTER_EXACT_SUCCESS":
                        raise InjectedCrash(phase)

                with mock.patch.object(
                    ai_adapter._InvocationControllerTransport,
                    "transport_kind",
                    "MOCK",
                ), mock.patch.object(
                    adapter,
                    "_complete_repository_transport",
                    side_effect=unknown_transport,
                ), mock.patch.object(
                    qualification,
                    "build_invocation_controlled_transport_adapter",
                    return_value=adapter,
                ), mock.patch.object(
                    workflow,
                    "_TABLE_QUALIFICATION_RECOVERY_HOOK",
                    side_effect=crash_after_wb3,
                ):
                    with self.assertRaises(InjectedCrash):
                        qualification.execute_table_qualification_task(**common)
                self.assertEqual(1, len(calls))
                run_dir = repo_root / binding["run_directory_relative_path"]
                with self.assertRaises(qualification.QualificationError) as pending:
                    qualification.validate_table_qualification_cycle_exact_set(
                        repo_root=repo_root,
                        binding=binding,
                    )
                self.assertEqual(
                    "TABLE_QUALIFICATION_CYCLE_PENDING_MATERIALIZATION",
                    pending.exception.code,
                )
                with mock.patch.object(
                    ai_adapter._InvocationControllerTransport,
                    "transport_kind",
                    "MOCK",
                ), mock.patch.object(
                    adapter,
                    "_complete_repository_transport",
                    side_effect=AssertionError("transport reinvoked"),
                ), mock.patch.object(
                    qualification,
                    "build_invocation_controlled_transport_adapter",
                    return_value=adapter,
                ):
                    with self.assertRaises(qualification.QualificationError) as error:
                        qualification.execute_table_qualification_task(**common)
                self.assertEqual("TABLE_QUALIFICATION_UNKNOWN_REMOTE_OUTCOME", error.exception.code)
                self.assertEqual(1, len(calls))
                manifest, records, _decisions = load_run_for_status(
                    run_dir=run_dir,
                    repo_root=repo_root,
                )
                qualification.validate_table_qualification_run_bindings(
                    repo_root=repo_root,
                    run_dir=run_dir,
                    manifest=manifest,
                    records=records,
                )
                unknown_attempt = next(
                    record for record in records
                    if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                )
                self.assertEqual("", unknown_attempt["provider_request_id"])
                unknown_terminal = qualification.qualification_remote_egress_terminals(
                    workspace_dir=(
                        repo_root / binding["wb3_workspace_relative_path"]
                    ),
                )[0]
                self.assertEqual([], unknown_terminal["provider_request_ids"])
                with mock.patch.object(
                    qualification,
                    "build_invocation_controlled_transport_adapter",
                    side_effect=AssertionError("provider path reached"),
                ):
                    with self.assertRaises(qualification.QualificationError) as resumed:
                        qualification.execute_table_qualification_task(**common)
                self.assertEqual(
                    "TABLE_QUALIFICATION_UNKNOWN_REMOTE_OUTCOME",
                    resumed.exception.code,
                )
                self.assertEqual(1, len(calls))


if __name__ == "__main__":
    unittest.main()
