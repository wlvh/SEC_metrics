"""Run the supported recorded/live vNext Cutover state machine.

The command uses a fixed repository authority, requires ``--execute-live`` for
remote processing and publication, and never creates HUMAN review decisions.
Without live authority it builds the same Run/Batch/staging chain; a catalog
fixture may commit an isolated sandbox view, but never the formal active
pointer or repository root mirrors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from vnext.cutover import CutoverError, run_cutover  # noqa: E402
from vnext.publication import (  # noqa: E402
    PublicationError,
    complete_recorded_publication_sandbox,
    publication_state_snapshot,
)
from vnext.recorded_fixtures import (  # noqa: E402
    RecordedFixtureError,
    load_recorded_fixture,
)


def _utc_now() -> str:
    """Return one timezone-aware current UTC timestamp."""
    return datetime.now(tz=timezone.utc).isoformat()


def _repository_path(*, value: str, label: str) -> Path:
    """Resolve one CLI path while keeping all mutable state in the repository.

    Args:
        value: Absolute or repository-relative candidate path.
        label: Diagnostic path role.

    Returns:
        Resolved path below the fixed repository authority.

    Raises:
        CutoverError: When the candidate escapes the repository.
    """
    candidate = Path(value)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (REPO_ROOT / candidate).resolve()
    )
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as error:
        raise CutoverError(
            code="CUTOVER_PATH_OUTSIDE_REPOSITORY",
            message="{} must remain below the repository.".format(label),
        ) from error
    return resolved


def _recorded_workspace_path(*, value: str) -> Path:
    """Validate a fixture workspace before the shared workflow can write.

    Args:
        value: Absolute or repository-relative workspace path from the CLI.

    Returns:
        Resolved dedicated ``artifacts/vnext/recorded-*`` workspace.

    Raises:
        CutoverError: When the lexical/resolved path leaves the fixed sandbox
            namespace, names that namespace root, or traverses a symlink.
    """
    repository = Path(os.path.abspath(str(REPO_ROOT)))
    candidate = Path(value)
    lexical = Path(os.path.abspath(str(
        candidate if candidate.is_absolute() else repository / candidate
    )))
    allowed_root = repository / "artifacts" / "vnext"
    try:
        relative = lexical.relative_to(allowed_root)
    except ValueError as error:
        raise CutoverError(
            code="RECORDED_SANDBOX_WORKSPACE_INVALID",
            message=(
                "Recorded fixture workspace must be a strict descendant of "
                "artifacts/vnext."
            ),
        ) from error
    if relative == Path("."):
        raise CutoverError(
            code="RECORDED_SANDBOX_WORKSPACE_INVALID",
            message=(
                "Recorded fixture workspace must be a strict descendant of "
                "artifacts/vnext."
            ),
        )
    if not relative.parts[0].startswith("recorded-"):
        raise CutoverError(
            code="RECORDED_SANDBOX_WORKSPACE_INVALID",
            message=(
                "Recorded fixture workspace must use a dedicated "
                "artifacts/vnext/recorded-* namespace."
            ),
        )
    repository_relative = lexical.relative_to(repository)
    current = repository
    for part in repository_relative.parts:
        current = current / part
        if current.is_symlink() or (
            current.exists() and not current.is_dir()
        ):
            raise CutoverError(
                code="RECORDED_SANDBOX_WORKSPACE_INVALID",
                message="Recorded fixture workspace contains an unsafe path.",
            )
    resolved = lexical.resolve(strict=False)
    try:
        resolved_relative = resolved.relative_to(allowed_root.resolve())
    except ValueError as error:
        raise CutoverError(
            code="RECORDED_SANDBOX_WORKSPACE_INVALID",
            message="Recorded fixture workspace resolves outside its sandbox.",
        ) from error
    if resolved_relative == Path("."):
        raise CutoverError(
            code="RECORDED_SANDBOX_WORKSPACE_INVALID",
            message=(
                "Recorded fixture workspace must be a strict descendant of "
                "artifacts/vnext."
            ),
        )
    return resolved


def build_parser() -> argparse.ArgumentParser:
    """Build the single formal Cutover command parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument(
        "--recorded-response", help=argparse.SUPPRESS,
    )
    parser.add_argument("--fixture-id")
    parser.add_argument(
        "--workspace-dir",
        help=(
            "Recorded-only sandbox workspace; live execution uses the fixed "
            "repository-owned artifacts/vnext/cutover authority."
        ),
    )
    parser.add_argument("--legacy-snapshot-dir", default="outputs")
    parser.add_argument("--validated-at-utc")
    parser.add_argument("--committed-at-utc")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--debug", action="store_true")
    return parser


def _assert_formal_state_unchanged(
    *, formal_state_before: Dict[str, object],
) -> None:
    """Verify recorded work did not mutate the formal pointer or mirrors.

    Args:
        formal_state_before: Exact repository publication state captured before
            the recorded workflow started.

    Raises:
        CutoverError: When formal state is unreadable or differs.
    """
    try:
        formal_state_after = publication_state_snapshot(
            publication_root=REPO_ROOT,
        )
    except PublicationError as error:
        raise CutoverError(
            code="RECORDED_FORMAL_STATE_UNREADABLE",
            message="Recorded workflow cannot revalidate formal state.",
        ) from error
    if formal_state_after != formal_state_before:
        raise CutoverError(
            code="RECORDED_FORMAL_STATE_CHANGED",
            message="Recorded workflow changed formal publication state.",
            details={
                "active_before": formal_state_before[
                    "active_publication_id"
                ],
                "active_after": formal_state_after[
                    "active_publication_id"
                ],
            },
        )


def _complete_recorded_sandbox_publication(
    *, workspace_dir: Path, legacy_snapshot_dir: Path,
    cutover_result: Dict[str, object], validated_at_utc: str,
    committed_at_utc: str, formal_state_before: Dict[str, object],
) -> Dict[str, object]:
    """Commit and read back one fixed-root recorded sandbox publication.

    Args:
        workspace_dir: Repository-contained Cutover workspace; the core API
            alone derives its ``recorded-publication`` child authority.
        legacy_snapshot_dir: Frozen compatibility inputs used by projection.
        cutover_result: Completed recorded Batch/staging result.
        validated_at_utc: Explicit recorded validation time.
        committed_at_utc: Explicit sandbox CAS time.
        formal_state_before: Formal pointer/mirror snapshot from preflight.

    Returns:
        Verified sandbox publication, pointer, and read-back hashes.
    """
    required = {
        "batch_manifest_path", "staging_dir", "status",
    }
    if (
        not required.issubset(cutover_result)
        or cutover_result["status"] != "PASSED_RECORDED_ONLY"
    ):
        raise CutoverError(
            code="RECORDED_SANDBOX_INPUT_INVALID",
            message="Recorded sandbox requires a completed candidate.",
        )
    batch_path = _repository_path(
        value=str(cutover_result["batch_manifest_path"]),
        label="Recorded BatchManifest",
    )
    staging_dir = _repository_path(
        value=str(cutover_result["staging_dir"]),
        label="Recorded staging",
    )
    for path in (batch_path, staging_dir):
        try:
            path.relative_to(workspace_dir)
        except ValueError as error:
            raise CutoverError(
                code="RECORDED_SANDBOX_INPUT_INVALID",
                message="Recorded candidate is outside its workspace.",
            ) from error
    try:
        result = complete_recorded_publication_sandbox(
            repo_root=REPO_ROOT,
            workspace_dir=workspace_dir,
            batch_manifest_path=batch_path,
            legacy_snapshot_dir=legacy_snapshot_dir,
            staging_dir=staging_dir,
            validated_at_utc=validated_at_utc,
            committed_at_utc=committed_at_utc,
        )
    except PublicationError as error:
        _assert_formal_state_unchanged(
            formal_state_before=formal_state_before,
        )
        raise CutoverError(
            code="RECORDED_SANDBOX_PUBLICATION_FAILED",
            message="Recorded sandbox publication failed closed.",
        ) from error
    _assert_formal_state_unchanged(
        formal_state_before=formal_state_before,
    )
    expected_root = (
        workspace_dir.relative_to(REPO_ROOT) / "recorded-publication"
    ).as_posix()
    required_result = {
        "previous_publication_id",
        "publication_id",
        "pointer_sha256",
        "publication_root",
        "readback_hashes",
        "root_mirror_hashes",
    }
    if (
        not isinstance(result, dict)
        or not required_result.issubset(result)
        or result["publication_root"] != expected_root
        or type(result["publication_id"]) is not str
        or not str(result["publication_id"]).startswith("publication_")
        or type(result["pointer_sha256"]) is not str
        or len(str(result["pointer_sha256"])) != 64
        or not isinstance(result["readback_hashes"], dict)
        or not result["readback_hashes"]
        or result["root_mirror_hashes"] != result["readback_hashes"]
        or any(
            type(value) is not str or len(value) != 64
            for value in result["readback_hashes"].values()
        )
    ):
        raise CutoverError(
            code="RECORDED_SANDBOX_READBACK_INVALID",
            message="Recorded sandbox read-back fields differ.",
        )
    return dict(result)


def _execute(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Resolve fixed-authority paths and invoke the shared state machine.

    Args:
        arguments: Parsed command arguments.

    Returns:
        Structured Cutover result.
    """
    if arguments.execute_live and arguments.workspace_dir is not None:
        raise CutoverError(
            code="LIVE_WORKSPACE_OVERRIDE_FORBIDDEN",
            message=(
                "Live Cutover uses the fixed repository-owned "
                "artifacts/vnext/cutover workspace."
            ),
        )
    if arguments.recorded_response is not None:
        raise CutoverError(
            code="RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
            message=(
                "Recorded mode requires a repository catalog fixture and "
                "rejects a caller-selected response."
            ),
        )
    recorded_path: Optional[Path] = None
    recorded_fixture = None
    recorded_fixture_id = arguments.fixture_id
    if arguments.recorded_response is not None:
        recorded_path = _repository_path(
            value=arguments.recorded_response, label="Recorded response",
        )
    elif arguments.fixture_id is not None:
        try:
            recorded_fixture = load_recorded_fixture(
                repo_root=REPO_ROOT, fixture_id=arguments.fixture_id,
            )
        except RecordedFixtureError as error:
            raise CutoverError(
                code=error.code, message=str(error),
            ) from error
        recorded_path = REPO_ROOT / str(
            recorded_fixture["response"]["repo_relative_path"]
        )
        recorded_fixture_id = recorded_fixture["fixture_binding_id"]
    validated_at = (
        arguments.validated_at_utc
        if arguments.validated_at_utc is not None
        else _utc_now()
    )
    controlled_recorded = (
        recorded_fixture is not None and not arguments.execute_live
    )
    committed_at = (
        arguments.committed_at_utc
        if arguments.committed_at_utc is not None
        else _utc_now()
        if arguments.execute_live or controlled_recorded
        else None
    )
    workspace_value = (
        arguments.workspace_dir
        if arguments.workspace_dir is not None
        else "artifacts/vnext/recorded-cutover"
        if controlled_recorded
        else "artifacts/vnext/cutover"
    )
    workspace_dir = (
        _recorded_workspace_path(value=workspace_value)
        if controlled_recorded
        else _repository_path(
            value=workspace_value, label="Cutover workspace",
        )
    )
    legacy_snapshot_dir = _repository_path(
        value=arguments.legacy_snapshot_dir, label="Legacy snapshot",
    )
    formal_state_before = None
    if controlled_recorded:
        try:
            formal_state_before = publication_state_snapshot(
                publication_root=REPO_ROOT,
            )
        except PublicationError as error:
            raise CutoverError(
                code="RECORDED_FORMAL_STATE_UNREADABLE",
                message="Recorded preflight cannot read formal state.",
            ) from error
    try:
        result = run_cutover(
            repo_root=REPO_ROOT,
            workspace_dir=workspace_dir,
            legacy_snapshot_dir=legacy_snapshot_dir,
            publication_root=REPO_ROOT,
            execute_live=arguments.execute_live,
            recorded_response_path=recorded_path,
            recorded_fixture_id=recorded_fixture_id,
            commit=arguments.execute_live,
            validated_at_utc=validated_at,
            committed_at_utc=(
                committed_at if arguments.execute_live else None
            ),
        )
    except CutoverError as error:
        if recorded_fixture is None:
            raise
        if controlled_recorded and formal_state_before is not None:
            _assert_formal_state_unchanged(
                formal_state_before=formal_state_before,
            )
        details = dict(error.details)
        details["recorded_fixture"] = recorded_fixture
        raise CutoverError(
            code=error.code, message=str(error), details=details,
        ) from error
    if recorded_fixture is None:
        return result
    output = {**result, "recorded_fixture": recorded_fixture}
    if controlled_recorded:
        if formal_state_before is None or committed_at is None:
            raise CutoverError(
                code="RECORDED_SANDBOX_INPUT_INVALID",
                message="Recorded sandbox preflight is incomplete.",
            )
        if result["status"] == "PASSED_RECORDED_ONLY":
            try:
                output["recorded_publication"] = (
                    _complete_recorded_sandbox_publication(
                        workspace_dir=workspace_dir,
                        legacy_snapshot_dir=legacy_snapshot_dir,
                        cutover_result=dict(result),
                        validated_at_utc=validated_at,
                        committed_at_utc=committed_at,
                        formal_state_before=formal_state_before,
                    )
                )
            except CutoverError as error:
                details = dict(error.details)
                details["recorded_fixture"] = recorded_fixture
                raise CutoverError(
                    code=error.code, message=str(error), details=details,
                ) from error
        else:
            _assert_formal_state_unchanged(
                formal_state_before=formal_state_before,
            )
    return output


def _error_payload(*, error: Exception) -> Dict[str, object]:
    """Convert a known or unexpected exception to a stable JSON envelope.

    Args:
        error: Command-boundary exception.

    Returns:
        Machine-readable code, message, and details.
    """
    if isinstance(error, CutoverError):
        return {
            "code": error.code,
            "message": str(error),
            "details": error.details,
        }
    return {
        "code": "CUTOVER_FAILED",
        "message": str(error),
        "details": {"error_class": type(error).__name__},
    }


def main(*, argv: Sequence[str]) -> int:
    """Execute Cutover and suppress tracebacks unless debug is explicit.

    Args:
        argv: Command arguments excluding the executable name.

    Returns:
        Zero on a completed recorded/live transition and two on any blocker.
    """
    arguments = build_parser().parse_args(list(argv))
    try:
        result = _execute(arguments=arguments)
    # This is the intentional process boundary: expected failures stay concise,
    # while --debug restores the traceback needed for developer diagnosis.
    except Exception as error:
        if arguments.debug:
            traceback.print_exc()
        payload = {"ok": False, "error": _error_payload(error=error)}
        if arguments.json_output:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(
                "{}: {}".format(
                    payload["error"]["code"], payload["error"]["message"]
                ),
                file=sys.stderr,
            )
            details = payload["error"]["details"]
            if "pending_reviews" in details:
                for pending in details["pending_reviews"]:
                    print(pending["review_path"], file=sys.stderr)
                    print(pending["review_command"], file=sys.stderr)
        return 2
    if result["status"] == "BLOCKED":
        payload = {
            "ok": False,
            "error": {
                "code": "CUTOVER_CANDIDATE_BLOCKED",
                "message": (
                    "Strict compatibility blocked publication; active is "
                    "unchanged."
                ),
                "details": {"result": result},
            },
        }
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
