"""Operate the real-layout and post-freeze holdout qualification workflow.

``prepare`` uses a repository fixture and recorded adapter to create the same
Reader/Evidence/Review Run as production, stops for the ordinary HUMAN review
CLI, and on resume freezes the Run and writes its content-addressed receipt.
``freeze`` records production semantics before the independent holdout is
added. ``status`` verifies every fixed receipt without opening a socket.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
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
from vnext.qualification import validate_cutover_qualifications  # noqa: E402
from vnext.qualification import write_layout_qualification_receipt  # noqa: E402
from vnext.qualification import write_production_freeze_receipt  # noqa: E402
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


def _review_blocker(
    *, run_dir: Path, manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
) -> QualificationCliError:
    """Build the exact HUMAN recovery command for one OPEN layout Run.

    Args:
        run_dir: Persisted qualification Run directory.
        manifest: Verified OPEN Run manifest.
        records: Verified Run records.

    Returns:
        Structured ``HUMAN_REVIEW_REQUIRED`` error.
    """
    units = [
        record for record in records if record["record_type"] == "REVIEW_UNIT"
    ]
    if len(units) != 1:
        raise QualificationCliError(
            code="REVIEW_UNIT_NOT_FOUND",
            message="Qualification Run lacks one ReviewUnit",
        )
    unit = units[0]
    review_path = (
        run_dir / "review" / str(unit["review_unit_hash"]) / "review.md"
    )
    command = " ".join(
        shlex.quote(value)
        for value in (
            "python3",
            "tools/vnext_review.py",
            "decide",
            "--run-dir",
            run_dir.relative_to(REPO_ROOT).as_posix(),
            "--review-unit-hash",
            str(unit["review_unit_hash"]),
            "--decision",
            "APPROVE",
            "--reviewer-id",
            "<human-id>",
            "--decided-at-utc",
            "<UTC>",
            "--reason",
            "<reason>",
        )
    )
    return QualificationCliError(
        code="HUMAN_REVIEW_REQUIRED",
        message="Qualification Run remains OPEN for HUMAN review",
        details={
            "run_id": manifest["run_id"],
            "review_unit_hash": unit["review_unit_hash"],
            "review_path": review_path.relative_to(REPO_ROOT).as_posix(),
            "review_command": command,
        },
    )


def prepare_layout(*, fixture_id: str) -> Dict[str, object]:
    """Create or resume one socket-zero layout Run through freeze/receipt.

    Args:
        fixture_id: Repository-owned real filing fixture identity.

    Returns:
        FROZEN Run and content-addressed qualification receipt identities.
    """
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
                message="Layout did not reach HUMAN review",
                details={"status": result["status"]},
            )
    manifest, records, decisions = load_run_for_status(
        run_dir=run_dir, repo_root=REPO_ROOT,
    )
    if manifest["status"] == "OPEN" and not decisions:
        raise _review_blocker(
            run_dir=run_dir, manifest=manifest, records=records,
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
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--fixture-id", required=True)
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
        elif arguments.command == "prepare":
            output = prepare_layout(fixture_id=arguments.fixture_id)
        else:
            output = {
                "status": "PASSED",
                **validate_cutover_qualifications(repo_root=REPO_ROOT),
            }
    except (
        AIAdapterError,
        CanonicalError,
        QualificationCliError,
        QualificationError,
        RunStoreError,
        WorkflowError,
        OSError,
        ValueError,
    ) as error:
        if arguments.debug:
            raise
        code = error.code if hasattr(error, "code") else type(error).__name__
        details = error.details if hasattr(error, "details") else {}
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error_code": code,
                    "message": str(error),
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
