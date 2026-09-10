#!/usr/bin/env python3
"""Run one pinned formal report/Stage10/11/12/snapshot terminal cycle.

The command is the supported acceptance entrypoint after a new publication,
rollback, or restore.  It returns structured output and never opens AI, SEC,
legacy repair, or a second active-publication view.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validation_provenance import ValidationProvenanceError  # noqa: E402
from vnext.canonical import atomic_write_json  # noqa: E402
from vnext.publication import PublicationError  # noqa: E402
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS  # noqa: E402
from vnext.terminal_cycle import TerminalCycleError  # noqa: E402
from vnext.terminal_cycle import (  # noqa: E402
    execute_terminal_publication_cycle,
)


def _parser() -> argparse.ArgumentParser:
    """Build the explicit terminal-cycle command-line contract.

    Returns:
        Parser requiring publication root and expected committed identity.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Validate report, Stage 10/11/12, and snapshot through one "
            "pinned PublicationView"
        )
    )
    parser.add_argument("--publication-root", required=True)
    parser.add_argument("--expected-publication-id", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def _emit(*, envelope: dict, output: Optional[str], as_json: bool) -> None:
    """Persist optional structured evidence and print one public response.

    Args:
        envelope: Complete success or failure response.
        output: Optional explicit JSON receipt path.
        as_json: Whether stdout must contain the complete JSON envelope.

    Expected output:
        Optional atomic JSON bytes plus either JSON or one concise status line.
    """
    if output is not None:
        atomic_write_json(path=Path(output), value=envelope)
    if as_json:
        print(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
        return
    if envelope["ok"] is True:
        result = envelope["result"]
        print(
            "Terminal cycle PASSED; publication_id={}; cycle_id={}".format(
                result["publication_id"],
                result["terminal_cycle_id"],
            )
        )
        return
    error = envelope["error"]
    print("{}: {}".format(error["code"], error["message"]))


def _safe_output_path(
    *, publication_root: Path, output: Optional[str]
) -> Optional[Path]:
    """Restrict an optional receipt away from source and formal authority.

    Args:
        publication_root: Verified repository/publication root.
        output: Caller-requested JSON receipt locator, when present.

    Returns:
        Safe path below ``outputs/`` or ``None``.

    Raises:
        TerminalCycleError: The path escapes, aliases, or overlaps the active
            pointer, bundle store, provenance, or any root mirror.
    """
    if output is None:
        return None
    root = publication_root.resolve(strict=True)
    path = Path(output)
    if not path.is_absolute():
        path = root / path
    try:
        relative = path.resolve(strict=False).relative_to(root)
    except ValueError as error:
        raise TerminalCycleError(
            "TERMINAL_OUTPUT_ESCAPES_PUBLICATION_ROOT"
        ) from error
    if not relative.parts or relative.parts[0] != "outputs":
        raise TerminalCycleError("TERMINAL_OUTPUT_MUST_BE_UNDER_OUTPUTS")
    protected = {
        Path("outputs/active_publication.json"),
        Path("outputs/active_publication.json.lock"),
        Path("outputs/validation_snapshot_provenance.json"),
        *(Path(value) for value in ROOT_MIRROR_RELATIVE_PATHS.values()),
    }
    if (
        relative in protected
        or relative.parts[:2] == ("outputs", "publications")
    ):
        raise TerminalCycleError("TERMINAL_OUTPUT_OVERLAPS_AUTHORITY")
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise TerminalCycleError("TERMINAL_OUTPUT_PARENT_IS_SYMLINK")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise TerminalCycleError("TERMINAL_OUTPUT_IS_UNSAFE")
    return path


def main(*, argv: Optional[Sequence[str]] = None) -> int:
    """Execute the pinned terminal cycle and hide traceback by default.

    Args:
        argv: Optional argument sequence used by tests; ``None`` reads process
            arguments through :mod:`argparse`.

    Returns:
        Zero only after every pinned consumer and snapshot check passes.
    """
    arguments = _parser().parse_args(args=argv)
    try:
        publication_root = Path(arguments.publication_root).resolve(
            strict=True
        )
        output_path = _safe_output_path(
            publication_root=publication_root,
            output=arguments.output,
        )
        result = execute_terminal_publication_cycle(
            publication_root=publication_root,
            expected_publication_id=arguments.expected_publication_id,
        )
    except (
        OSError,
        PublicationError,
        TerminalCycleError,
        ValidationProvenanceError,
        ValueError,
    ) as error:
        if arguments.debug:
            traceback.print_exc()
        envelope = {
            "ok": False,
            "error": {
                "code": "TERMINAL_CYCLE_FAILED",
                "message": str(error),
            },
        }
        _emit(
            envelope=envelope,
            output=None,
            as_json=arguments.json,
        )
        return 1
    envelope = {"ok": True, "result": result}
    _emit(
        envelope=envelope,
        output=(str(output_path) if output_path is not None else None),
        as_json=arguments.json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
