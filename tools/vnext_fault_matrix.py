"""Run the formal publication failure matrix from a completed Cutover.

The CLI fixes publication, receipt, workspace, legacy snapshot, and authority
roots to this repository. No caller locator participates in formal authority.
The mixed-year negative is derived from a config-selected all-structural Run.
Default output hides tracebacks; ``--debug`` restores them for diagnosis.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.fault_matrix import FaultMatrixError  # noqa: E402
from vnext.fault_matrix import (  # noqa: E402
    run_cutover_publication_fault_matrix,
)


def _utc_now() -> str:
    """Return one timezone-aware current UTC timestamp."""
    return datetime.now(tz=timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    """Build the formal fault-matrix argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cutover-workspace-dir",
        help=(
            "Forbidden formal authority override; the workspace is fixed to "
            "artifacts/vnext/cutover."
        ),
    )
    parser.add_argument(
        "--legacy-snapshot-dir",
        help=(
            "Forbidden formal authority override; the snapshot is fixed to "
            "outputs."
        ),
    )
    parser.add_argument(
        "--prepared-successor-publication-id", required=True,
    )
    parser.add_argument("--executed-at-utc")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--debug", action="store_true")
    return parser


def _execute(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Resolve fixed-authority paths and execute the public matrix.

    Args:
        arguments: Parsed CLI namespace.

    Returns:
        PASSED matrix and persisted receipt references.
    """
    if (
        arguments.cutover_workspace_dir is not None
        or arguments.legacy_snapshot_dir is not None
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_AUTHORITY_OVERRIDE_FORBIDDEN",
            message="Formal fault-matrix roots are not caller-selectable",
        )
    executed_at_utc = (
        arguments.executed_at_utc
        if arguments.executed_at_utc is not None
        else _utc_now()
    )
    return run_cutover_publication_fault_matrix(
        repo_root=REPO_ROOT,
        cutover_workspace_dir=REPO_ROOT / "artifacts/vnext/cutover",
        legacy_snapshot_dir=REPO_ROOT / "outputs",
        prepared_successor_publication_id=(
            arguments.prepared_successor_publication_id
        ),
        executed_at_utc=executed_at_utc,
    )


def _error_payload(*, error: Exception) -> Dict[str, object]:
    """Convert one known or unexpected failure to a stable JSON object.

    Args:
        error: CLI-boundary failure.

    Returns:
        Non-sensitive error code and message.
    """
    if isinstance(error, FaultMatrixError):
        return {"code": error.code, "message": str(error)}
    return {
        "code": "FAULT_MATRIX_FAILED",
        "message": str(error),
    }


def main(*, argv: Sequence[str]) -> int:
    """Execute the matrix and suppress tracebacks unless explicitly enabled.

    Args:
        argv: Command arguments excluding the executable name.

    Returns:
        Zero only after every required fault receipt is persisted.
    """
    arguments = build_parser().parse_args(list(argv))
    try:
        result = _execute(arguments=arguments)
    except Exception as error:
        if arguments.debug:
            traceback.print_exc()
        payload = {"ok": False, "error": _error_payload(error=error)}
        if arguments.json_output:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(
                "{}: {}".format(
                    payload["error"]["code"],
                    payload["error"]["message"],
                ),
                file=sys.stderr,
            )
        return 2
    payload = {"ok": True, "result": result}
    if arguments.json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
