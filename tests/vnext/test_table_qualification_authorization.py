"""Exercise the sole LIVE table-qualification authorization boundary."""

from __future__ import annotations

import copy
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
from vnext.canonical import atomic_write_json, content_hash
from vnext.replay import replay_frozen_results
from vnext.run_store import load_frozen_run, validate_and_freeze_run
from vnext.stage_a_snapshot import write_stage_a_snapshot
from vnext.table_grid import build_table_grid
from vnext.table_qualification_freeze import validate_table_qualification_freeze
from vnext.table_qualification_freeze import write_table_qualification_freeze_receipt
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

    The helper retains the current matrix/task/root/source bindings and changes
    only the test copy's content-addressed receipt flag.  It does not mock the
    qualification gate; the real freeze and Stage-A validators consume the
    synthetic repository artifacts exactly as production code would.
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
            freeze_commit = _run_git(
                workdir=worktree,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            receipt = write_table_qualification_freeze_receipt(
                repo_root=worktree,
                freeze_commit=freeze_commit,
                frozen_at_utc="2026-08-21T08:30:00Z",
            )
            body = {
                key: value
                for key, value in receipt.items()
                if key not in {
                    "table_qualification_freeze_receipt_id",
                    "receipt_path",
                }
            }
            body["d07_decision_required"] = False
            synthetic = {
                "table_qualification_freeze_receipt_id": content_hash(
                    value=body,
                ),
                **body,
            }
            receipt_path = (
                "artifacts/vnext/table_qualification_freeze/receipts/{}.json"
                .format(
                    synthetic["table_qualification_freeze_receipt_id"].split(
                        ":", maxsplit=1,
                    )[1]
                )
            )
            atomic_write_json(path=worktree / receipt_path, value=synthetic)
            atomic_write_json(
                path=worktree / "config/table_qualification_freeze.json",
                value={
                    "schema_version": 1,
                    "qualification_cycle_id": synthetic[
                        "qualification_cycle_id"
                    ],
                    "receipt_id": synthetic[
                        "table_qualification_freeze_receipt_id"
                    ],
                    "receipt_path": receipt_path,
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
                digest = binding["qualification_authorization_id"].split(
                    ":", maxsplit=1,
                )[1]
                run_dir = (
                    repo_root
                    / "artifacts/vnext/qualification/cycles"
                    / binding["qualification_cycle_id"].split(
                        ":", maxsplit=1,
                    )[1]
                    / "runs"
                    / digest
                )
                finalized = finalize_reviewed_direct_results(
                    run_dir=run_dir,
                    repo_root=repo_root,
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
                self.assertEqual("PENDING_HUMAN_REVIEW", created["status"])
                self.assertEqual(1, len(calls))
                self.assertEqual(1, len(finalized["result_ids"]))
                self.assertEqual("FROZEN", frozen["status"])
                self.assertEqual(1, len(replay["results"]))
                self.assertEqual(binding, manifest["qualification_authorization"])
                self.assertEqual(binding, evidence["qualification_authorization"])
                self.assertEqual(binding, ledger_rows[0]["qualification_authorization"])
                self.assertEqual(
                    evidence["provider_ledger_entry_id"],
                    ledger_rows[0]["qualification_provider_ledger_entry_id"],
                )

                source = binding["source_binding"]
                common = {
                    "repo_root": repo_root,
                    "company_id": "marriott_international",
                    "target_period": {
                        "fiscal_year": 2025,
                        "period_start": "2025-01-01",
                        "period_end": "2025-12-31",
                    },
                    "source_repo_relative_path": source["source_declaration"][
                        "source_repo_relative_path"
                    ],
                    "source_media_type": "text/html",
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
                                run_dir=(
                                    repo_root / "synthetic-mutations" / field
                                ),
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
