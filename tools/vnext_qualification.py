"""Operate the real-layout and post-freeze holdout qualification workflow.

``prepare`` uses a repository fixture and recorded adapter to create the same
Reader/Evidence/Review Run as production, records an authorized optional
SYSTEM review when no HUMAN decision exists, then freezes and writes its
content-addressed receipt.
``freeze`` records production semantics before the independent holdout is
added. ``status`` verifies every fixed receipt without opening a socket.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.ai_adapter import AIAdapterError  # noqa: E402
from vnext.ai_adapter import build_recorded_adapter  # noqa: E402
from vnext.canonical import CanonicalError, sha256_file  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402
from vnext.qualification import QUALIFICATION_ROOT  # noqa: E402
from vnext.qualification import QualificationError  # noqa: E402
from vnext.qualification import reset_qualification_chain  # noqa: E402
from vnext.qualification import validate_cutover_qualifications  # noqa: E402
from vnext.qualification import write_layout_qualification_receipt  # noqa: E402
from vnext.qualification import write_production_freeze_receipt  # noqa: E402
from vnext.qualification import table_qualification_task_plan  # noqa: E402
from vnext.qualification import execute_table_qualification_task  # noqa: E402
from vnext.qualification import issue_table_qualification_authorization  # noqa: E402
from vnext.qualification import write_table_production_semantic_freeze  # noqa: E402
from vnext.qualification import validate_table_production_semantic_freeze  # noqa: E402
from vnext.run_store import load_run_for_status  # noqa: E402
from vnext.run_store import RunStoreError, validate_and_freeze_run  # noqa: E402
from vnext.workflow import create_layout_qualification_run  # noqa: E402
from vnext.workflow import finalize_reviewed_direct_results  # noqa: E402
from vnext.workflow import WorkflowError  # noqa: E402


class QualificationCliError(RuntimeError):
    """Carry one stable CLI code and optional recovery details."""

    def __init__(
        self, *, code: str, message: str,
        details: Optional[Mapping[str, object]] = None,
    ) -> None:
        """Create a structured operator error.

        Args:
            code: Stable machine code.
            message: Concise non-sensitive diagnostic.
            details: Optional JSON-compatible recovery context.
        """
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else dict(details)


def _fixture_manifest(*, fixture_id: str) -> Dict[str, object]:
    """Load the fixed fixture manifest and exact recorded response bytes.

    Args:
        fixture_id: Safe fixture directory identity.

    Returns:
        Strict manifest object with a verified response locator.
    """
    if (
        not fixture_id
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
               for character in fixture_id)
    ):
        raise QualificationCliError(
            code="LAYOUT_FIXTURE_INVALID",
            message="Fixture identity is invalid",
        )
    path = (
        REPO_ROOT / "fixtures" / "vnext" / "layouts" / fixture_id
        / "fixture_manifest.json"
    )
    if path.is_symlink() or not path.is_file():
        raise QualificationCliError(
            code="LAYOUT_FIXTURE_NOT_FOUND",
            message="Fixture manifest is absent",
        )
    manifest = strict_json_file(path=path)
    if not isinstance(manifest, dict) or manifest["fixture_id"] != fixture_id:
        raise QualificationCliError(
            code="LAYOUT_FIXTURE_INVALID",
            message="Fixture manifest identity differs",
        )
    response_relative = Path(
        str(manifest["recorded_response_repo_relative_path"])
    )
    response_path = REPO_ROOT / response_relative
    if (
        response_relative.is_absolute()
        or ".." in response_relative.parts
        or response_path.is_symlink()
        or not response_path.is_file()
        or sha256_file(path=response_path)
        != manifest["recorded_response_sha256"]
    ):
        raise QualificationCliError(
            code="LAYOUT_FIXTURE_INVALID",
            message="Recorded response binding differs",
        )
    return manifest


def _require_catalog_table_qualification_path() -> None:
    """Fail closed before legacy fixture preparation can use schema v1.

    Raises:
        QualificationCliError: Always, because a disclosure-group fixture has
        no family-scoped catalog task identity with which to evaluate gates.
    """
    raise QualificationCliError(
        code="TABLE_TASK_CONTRACT_REQUIRED",
        message="Legacy fixture prepare lacks an explicit catalog task ID",
    )


def prepare_layout(*, fixture_id: str) -> Dict[str, object]:
    """Create or resume one socket-zero layout Run through freeze/receipt.

    Args:
        fixture_id: Repository-owned real filing fixture identity.

    Returns:
        FROZEN Run and content-addressed qualification receipt identities.
    """
    _require_catalog_table_qualification_path()
    fixture = _fixture_manifest(fixture_id=fixture_id)
    run_dir = REPO_ROOT / QUALIFICATION_ROOT / "runs" / fixture_id
    if not run_dir.exists():
        response_path = REPO_ROOT / Path(
            str(fixture["recorded_response_repo_relative_path"])
        )
        result = create_layout_qualification_run(
            repo_root=REPO_ROOT,
            run_dir=run_dir,
            run_id="run:qualification:" + fixture_id,
            fixture_id=fixture_id,
            adapter=build_recorded_adapter(
                response_bytes=response_path.read_bytes(),
                fixture_id="qualification:" + fixture_id,
            ),
            clock=None,
        )
        if result["status"] != "PENDING_HUMAN_REVIEW":
            raise QualificationCliError(
                code="LAYOUT_READER_REJECTED",
                message="Layout did not reach the review boundary",
                details={"status": result["status"]},
            )
    manifest, records, decisions = load_run_for_status(
        run_dir=run_dir, repo_root=REPO_ROOT,
    )
    if manifest["status"] == "OPEN":
        has_results = any(
            record["record_type"] == "METRIC_RESULT" for record in records
        )
        if not has_results:
            finalize_reviewed_direct_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
        manifest = validate_and_freeze_run(
            run_dir=run_dir, repo_root=REPO_ROOT,
        )
    if manifest["status"] != "FROZEN":
        raise QualificationCliError(
            code="LAYOUT_RUN_NOT_FROZEN",
            message="Qualification Run did not reach FROZEN",
        )
    receipt = write_layout_qualification_receipt(
        repo_root=REPO_ROOT, fixture_id=fixture_id,
    )
    return {
        "status": "FROZEN",
        "fixture_id": fixture_id,
        "run_id": manifest["run_id"],
        "receipt_id": receipt["receipt_id"],
        "receipt_path": receipt["receipt_path"],
    }


def main(*, argv: Sequence[str]) -> int:
    """Execute freeze, prepare, or status with stable JSON diagnostics.

    Args:
        argv: Command-line arguments excluding the executable name.

    Returns:
        Zero only when the requested qualification transition succeeds.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--frozen-at-utc", required=True)
    reset = subparsers.add_parser("reset")
    reset.add_argument("--reset-at-utc", required=True)
    reset.add_argument("--reason", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--fixture-id", required=True)
    table_plan = subparsers.add_parser("table-plan")
    table_plan.add_argument("--family-id", required=True)
    table_plan.add_argument("--task-contract-id", required=True)
    table_plan.add_argument("--phase", required=True)
    table_plan.add_argument("--ordinal", required=True, type=int)
    table_execute = subparsers.add_parser("table-execute")
    table_execute.add_argument("--family-id", required=True)
    table_execute.add_argument("--task-contract-id", required=True)
    table_execute.add_argument("--phase", required=True)
    table_execute.add_argument("--ordinal", required=True, type=int)
    table_execute.add_argument("--owner-token", required=True)
    table_freeze = subparsers.add_parser("table-freeze")
    table_freeze.add_argument("--family-id", required=True)
    table_freeze.add_argument("--frozen-at-utc", required=True)
    table_freeze_status = subparsers.add_parser("table-freeze-status")
    table_freeze_status.add_argument("--family-id", required=True)
    subparsers.add_parser("status")
    arguments = parser.parse_args(list(argv))
    try:
        if arguments.command == "freeze":
            receipt = write_production_freeze_receipt(
                repo_root=REPO_ROOT,
                frozen_at_utc=arguments.frozen_at_utc,
            )
            output = {
                "status": "FROZEN",
                "semantic_tree_id": receipt["semantic_tree_id"],
                "receipt_id": receipt["receipt_id"],
                "receipt_path": receipt["receipt_path"],
            }
        elif arguments.command == "reset":
            receipt = reset_qualification_chain(
                repo_root=REPO_ROOT,
                reset_at_utc=arguments.reset_at_utc,
                reason=arguments.reason,
            )
            output = {
                "status": "RESET",
                "reset_id": receipt["reset_id"],
                "receipt_path": receipt["receipt_path"],
                "prior_blocker_code": receipt["prior_blocker_code"],
            }
        elif arguments.command == "prepare":
            output = prepare_layout(fixture_id=arguments.fixture_id)
        elif arguments.command == "table-plan":
            output = {
                "status": "PLANNED",
                **table_qualification_task_plan(
                    repo_root=REPO_ROOT,
                    family_id=arguments.family_id,
                    task_contract_id=arguments.task_contract_id,
                    qualification_phase=arguments.phase,
                    qualification_ordinal=arguments.ordinal,
                ),
            }
        elif arguments.command == "table-execute":
            authorization = issue_table_qualification_authorization(
                repo_root=REPO_ROOT,
                family_id=arguments.family_id,
                task_contract_id=arguments.task_contract_id,
                qualification_phase=arguments.phase,
                qualification_ordinal=arguments.ordinal,
            )
            binding = authorization.as_mapping()
            result = execute_table_qualification_task(
                repo_root=REPO_ROOT,
                family_id=arguments.family_id,
                task_contract_id=arguments.task_contract_id,
                qualification_phase=arguments.phase,
                qualification_ordinal=arguments.ordinal,
                target_period=binding["target_period"],
                owner_token=arguments.owner_token,
            )
            run_dir = REPO_ROOT / binding["run_directory_relative_path"]
            manifest, records, _decisions = load_run_for_status(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            if manifest["status"] == "OPEN" and result.get("status") not in {
                "FAILED_TERMINAL", "PRE_EGRESS_FAILURE",
            }:
                if not any(
                    record["record_type"] == "METRIC_RESULT"
                    for record in records
                ):
                    finalize_reviewed_direct_results(
                        run_dir=run_dir, repo_root=REPO_ROOT,
                    )
                manifest = validate_and_freeze_run(
                    run_dir=run_dir, repo_root=REPO_ROOT,
                )
            output = {
                **result,
                "status": manifest["status"],
                "run_id": manifest["run_id"],
                "qualification_terminal_id": binding[
                    "qualification_terminal_id"
                ],
                "qualification_task_plan_id": binding[
                    "qualification_task_plan_id"
                ],
            }
        elif arguments.command == "table-freeze":
            receipt = write_table_production_semantic_freeze(
                repo_root=REPO_ROOT,
                family_id=arguments.family_id,
                frozen_at_utc=arguments.frozen_at_utc,
            )
            output = {"status": "FROZEN", **receipt}
        elif arguments.command == "table-freeze-status":
            output = {
                "status": "PASSED",
                **validate_table_production_semantic_freeze(
                    repo_root=REPO_ROOT,
                    family_id=arguments.family_id,
                ),
            }
        else:
            output = {
                "status": "PASSED",
                **validate_cutover_qualifications(repo_root=REPO_ROOT),
            }
    # The CLI boundary intentionally catches ordinary exceptions so an unsafe
    # fixture or unexpected implementation failure cannot leak a traceback to
    # a reviewer unless they explicitly request diagnostic output.
    except Exception as error:
        if arguments.debug:
            traceback.print_exc()
        if isinstance(error, QualificationCliError):
            code = error.code
            details = error.details
            message = str(error)
        elif isinstance(error, QualificationError):
            code = error.code
            details = {}
            message = str(error)
        elif isinstance(
            error,
            (AIAdapterError, CanonicalError, RunStoreError, WorkflowError,
             OSError, ValueError),
        ):
            code = type(error).__name__
            details = {}
            message = str(error)
        else:
            code = "QUALIFICATION_COMMAND_FAILED"
            details = {"error_class": type(error).__name__}
            message = "Qualification command failed"
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error_code": code,
                    "message": message,
                    "details": details,
                },
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
