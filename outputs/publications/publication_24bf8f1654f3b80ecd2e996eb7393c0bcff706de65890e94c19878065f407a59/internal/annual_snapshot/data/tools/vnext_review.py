"""Inspect and append context-bound HUMAN decisions for one OPEN vNext Run.

The public helpers and CLI share one implementation for list, show, and
decide. A decision is appended only after the rendered/canonical review bytes
and the immutable supersedes chain are revalidated under a Run-scoped lock.
APPROVE claims are always derived from the ReviewUnit; REJECT claims are empty.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import shlex
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.canonical import sha256_file, strict_json_file  # noqa: E402
from vnext.review import (  # noqa: E402
    ReviewError,
    create_review_decision,
    effective_review_decision,
)
from vnext.run_store import (  # noqa: E402
    RunStoreError,
    append_review_decision,
    load_open_run,
)


class ReviewCliError(RuntimeError):
    """Carry one stable operator error code and structured recovery context."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Optional[Mapping[str, object]] = None,
    ) -> None:
        """Create a stable review error.

        Args:
            code: Machine-stable uppercase error code.
            message: Concise human-readable explanation.
            details: Optional JSON-compatible diagnostic and recovery fields.
        """
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else dict(details)


def _best_effort_run_id(*, run_dir: Path) -> str:
    """Read a diagnostic Run ID without treating unverified bytes as authority.

    Args:
        run_dir: Candidate Run directory.

    Returns:
        Text Run ID when visibly present, otherwise the explicit unknown label.
    """
    path = run_dir / "manifest.json"
    try:
        value = strict_json_file(path=path)
    except (OSError, ValueError):
        return "UNKNOWN"
    if isinstance(value, dict) and "run_id" in value:
        run_id = value["run_id"]
        if isinstance(run_id, str) and run_id:
            return run_id
    return "UNKNOWN"


def _load_open_review_run(
    *, run_dir: Path
) -> Tuple[
    Dict[str, object],
    List[Dict[str, object]],
    List[Dict[str, object]],
]:
    """Load an OPEN Run and translate state/path failures to one stable code.

    Args:
        run_dir: Run directory selected by the operator.

    Returns:
        Verified manifest, records, and immutable review decisions.

    Raises:
        ReviewCliError: When the Run is missing, invalid, or not OPEN.
    """
    try:
        return load_open_run(run_dir=run_dir)
    except (OSError, ValueError, RunStoreError) as error:
        raise ReviewCliError(
            code="RUN_NOT_OPEN",
            message="Review operation requires one valid OPEN Run.",
            details={
                "run_id": _best_effort_run_id(run_dir=run_dir),
                "run_dir": str(run_dir),
            },
        ) from error


def _review_units(
    *, records: Sequence[Mapping[str, object]]
) -> List[Dict[str, object]]:
    """Return isolated ReviewUnit records in their persisted order.

    Args:
        records: Verified OPEN Run records.

    Returns:
        ReviewUnit mappings only.
    """
    return [
        dict(record)
        for record in records
        if record["record_type"] == "REVIEW_UNIT"
    ]


def _select_review_unit(
    *,
    run_id: str,
    records: Sequence[Mapping[str, object]],
    review_unit_hash: str,
) -> Dict[str, object]:
    """Select exactly one immutable ReviewUnit by content identity.

    Args:
        run_id: Verified Run identity for diagnostics.
        records: Verified Run records.
        review_unit_hash: Exact requested ReviewUnit hash.

    Returns:
        The unique matching ReviewUnit.
    """
    matches = [
        unit
        for unit in _review_units(records=records)
        if unit["review_unit_hash"] == review_unit_hash
    ]
    details = {"run_id": run_id, "review_unit_hash": review_unit_hash}
    if not matches:
        raise ReviewCliError(
            code="REVIEW_UNIT_NOT_FOUND",
            message="The requested ReviewUnit is absent from this Run.",
            details=details,
        )
    if len(matches) != 1:
        raise ReviewCliError(
            code="REVIEW_UNIT_AMBIGUOUS",
            message="The requested ReviewUnit is duplicated in this Run.",
            details={**details, "match_count": len(matches)},
        )
    return matches[0]


def _review_paths(
    *, run_dir: Path, review_unit_hash: str
) -> Tuple[Path, Path, Path]:
    """Derive the fixed review directory and two bound artifact paths.

    Args:
        run_dir: OPEN Run root.
        review_unit_hash: Exact ReviewUnit identity.

    Returns:
        Review directory, canonical context path, and rendered Markdown path.
    """
    review_dir = run_dir / "review" / review_unit_hash
    return (
        review_dir,
        review_dir / "review_context.json",
        review_dir / "review.md",
    )


def _verify_review_context(
    *, run_dir: Path, run_id: str, review_unit: Mapping[str, object]
) -> Dict[str, object]:
    """Re-read exact HUMAN-visible bytes before show or decide.

    Args:
        run_dir: OPEN Run root.
        run_id: Verified Run identity for diagnostics.
        review_unit: Selected ReviewUnit carrying the expected hashes.

    Returns:
        Paths, exact hashes, and rendered Markdown text.

    Raises:
        ReviewCliError: When an asset is missing, unsafe, extra, or changed.
    """
    unit_hash = str(review_unit["review_unit_hash"])
    review_dir, context_path, markdown_path = _review_paths(
        run_dir=run_dir, review_unit_hash=unit_hash,
    )
    details = {"run_id": run_id, "review_unit_hash": unit_hash}
    try:
        actual_files = {
            path.name
            for path in review_dir.iterdir()
            if path.is_file() and not path.is_symlink()
        }
        if (
            review_dir.is_symlink()
            or not review_dir.is_dir()
            or actual_files != {"review_context.json", "review.md"}
            or context_path.is_symlink()
            or markdown_path.is_symlink()
            or sha256_file(path=context_path)
            != review_unit["review_context_hash"]
            or sha256_file(path=markdown_path)
            != review_unit["rendered_review_hash"]
        ):
            raise ValueError("review asset exact set or hash differs")
        markdown = markdown_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ReviewCliError(
            code="REVIEW_CONTEXT_STALE",
            message="Review context bytes no longer match the ReviewUnit.",
            details=details,
        ) from error
    return {
        "review_context_path": str(context_path.resolve()),
        "review_context_hash": str(review_unit["review_context_hash"]),
        "review_path": str(markdown_path.resolve()),
        "rendered_review_hash": str(review_unit["rendered_review_hash"]),
        "review_markdown": markdown,
    }


def _chain_summary(
    *, decisions: Sequence[Mapping[str, object]]
) -> List[Dict[str, object]]:
    """Build a compact immutable decision-chain summary.

    Args:
        decisions: Decisions already filtered to one ReviewUnit.

    Returns:
        Ordered IDs, choices, and supersedes links.
    """
    return [
        {
            "review_decision_id": decision["review_decision_id"],
            "decision": decision["decision"],
            "supersedes_decision_id": decision["supersedes_decision_id"],
        }
        for decision in decisions
    ]


def _effective_tip(
    *,
    run_id: str,
    review_unit: Mapping[str, object],
    decisions: Sequence[Mapping[str, object]],
) -> Optional[Mapping[str, object]]:
    """Resolve one decision tip or return ``None`` before HUMAN review.

    Args:
        run_id: Verified Run identity.
        review_unit: Selected ReviewUnit.
        decisions: Decisions bound to this unit.

    Returns:
        Effective decision or ``None`` when the chain is empty.
    """
    if not decisions:
        return None
    try:
        return effective_review_decision(
            review_unit=review_unit, decisions=decisions,
        )
    except ReviewError as error:
        message = str(error)
        code = (
            "PARALLEL_EFFECTIVE_DECISIONS"
            if "Parallel" in message or "one root" in message
            else "REVIEW_DECISION_CHAIN_INVALID"
        )
        raise ReviewCliError(
            code=code,
            message="Review decision chain has no unique effective tip.",
            details={
                "run_id": run_id,
                "review_unit_hash": review_unit["review_unit_hash"],
                "decision_chain": _chain_summary(decisions=decisions),
            },
        ) from error


def _bound_decisions(
    *,
    decisions: Sequence[Mapping[str, object]],
    review_unit_hash: str,
) -> List[Dict[str, object]]:
    """Filter immutable decisions to one exact ReviewUnit.

    Args:
        decisions: Complete OPEN Run decision sequence.
        review_unit_hash: Target unit identity.

    Returns:
        Isolated decisions in persisted order.
    """
    return [
        dict(decision)
        for decision in decisions
        if decision["review_unit_hash"] == review_unit_hash
    ]


def build_review_decision_command(
    *, run_dir: Path, review_unit_hash: str
) -> str:
    """Return a copyable command template for the pending HUMAN decision.

    Args:
        run_dir: OPEN Run root.
        review_unit_hash: ReviewUnit the human must inspect.

    Returns:
        Shell-safe command template with explicit placeholders.
    """
    return shlex.join(
        [
            "python3",
            "tools/vnext_operator.py",
            "review",
            "decide",
            "--run-dir",
            str(run_dir),
            "--review-unit-hash",
            review_unit_hash,
            "--decision",
            "APPROVE_OR_REJECT",
            "--reviewer-id",
            "HUMAN_REVIEWER_ID",
            "--decided-at-utc",
            "UTC_TIMESTAMP",
            "--reason",
            "HUMAN_REASON",
        ]
    )


def _recovery_command(
    *,
    run_dir: Path,
    review_unit_hash: str,
    decision: str,
    reviewer_id: str,
    decided_at_utc: str,
    reason: str,
    current_tip: Optional[str],
) -> str:
    """Return the exact corrected decide command for a stale caller tip.

    Args:
        run_dir: OPEN Run root.
        review_unit_hash: Target ReviewUnit.
        decision: Requested HUMAN choice.
        reviewer_id: Explicit HUMAN identity.
        decided_at_utc: Explicit UTC decision time.
        reason: HUMAN rationale.
        current_tip: Verified effective tip, if one exists.

    Returns:
        Shell-safe command using the current effective tip.
    """
    argv = [
        "python3",
        "tools/vnext_operator.py",
        "review",
        "decide",
        "--run-dir",
        str(run_dir),
        "--review-unit-hash",
        review_unit_hash,
        "--decision",
        decision,
        "--reviewer-id",
        reviewer_id,
        "--decided-at-utc",
        decided_at_utc,
        "--reason",
        reason,
    ]
    if current_tip is not None:
        argv.extend(["--supersedes-decision-id", current_tip])
    return shlex.join(argv)


@contextmanager
def review_run_lock(*, run_dir: Path) -> Iterator[None]:
    """Serialize review read-check-append on the existing Run manifest inode.

    Args:
        run_dir: OPEN Run whose decision chain is being changed.

    Yields:
        Control while this CLI excludes other conforming review writers.
    """
    manifest_path = run_dir / "manifest.json"
    try:
        lock_file = manifest_path.open(mode="rb")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    except OSError as error:
        raise ReviewCliError(
            code="RUN_NOT_OPEN",
            message="Review operation cannot lock the selected Run.",
            details={
                "run_id": _best_effort_run_id(run_dir=run_dir),
                "run_dir": str(run_dir),
            },
        ) from error
    try:
        yield
    finally:
        lock_file.close()


def list_human_reviews(*, run_dir: Path) -> Dict[str, object]:
    """List all ReviewUnits and their unique effective decision state.

    Args:
        run_dir: OPEN Run root.

    Returns:
        Run identity plus ordered review summaries and copyable paths.
    """
    manifest, records, decisions = _load_open_review_run(run_dir=run_dir)
    summaries = []
    for unit in _review_units(records=records):
        unit_hash = str(unit["review_unit_hash"])
        assets = _verify_review_context(
            run_dir=run_dir, run_id=str(manifest["run_id"]), review_unit=unit,
        )
        bound = _bound_decisions(
            decisions=decisions, review_unit_hash=unit_hash,
        )
        tip = _effective_tip(
            run_id=str(manifest["run_id"]),
            review_unit=unit,
            decisions=bound,
        )
        summaries.append(
            {
                "review_unit_hash": unit_hash,
                "status": "PENDING" if tip is None else tip["decision"],
                "current_effective_tip": (
                    None if tip is None else tip["review_decision_id"]
                ),
                "review_path": assets["review_path"],
                "decision_chain": _chain_summary(decisions=bound),
            }
        )
    return {"run_id": manifest["run_id"], "review_units": summaries}


def show_human_review(
    *, run_dir: Path, review_unit_hash: str
) -> Dict[str, object]:
    """Return one exact rendered ReviewUnit and current decision chain.

    Args:
        run_dir: OPEN Run root.
        review_unit_hash: Exact ReviewUnit identity.

    Returns:
        Hash/path-bound HUMAN context and decision state.
    """
    manifest, records, decisions = _load_open_review_run(run_dir=run_dir)
    unit = _select_review_unit(
        run_id=str(manifest["run_id"]),
        records=records,
        review_unit_hash=review_unit_hash,
    )
    assets = _verify_review_context(
        run_dir=run_dir, run_id=str(manifest["run_id"]), review_unit=unit,
    )
    bound = _bound_decisions(
        decisions=decisions, review_unit_hash=review_unit_hash,
    )
    tip = _effective_tip(
        run_id=str(manifest["run_id"]),
        review_unit=unit,
        decisions=bound,
    )
    return {
        "run_id": manifest["run_id"],
        "review_unit_hash": review_unit_hash,
        "required_claims": unit["required_claims"],
        "current_effective_tip": (
            None if tip is None else tip["review_decision_id"]
        ),
        "effective_decision": None if tip is None else tip["decision"],
        "decision_chain": _chain_summary(decisions=bound),
        **assets,
    }


def append_human_decision(
    *,
    run_dir: Path,
    review_unit_hash: str,
    decision: str,
    reviewer_id: str,
    decided_at_utc: str,
    reason: str,
    supersedes_decision_id: Optional[str],
) -> Dict[str, object]:
    """Validate and append one immutable HUMAN decision under a Run lock.

    Args:
        run_dir: OPEN Run root.
        review_unit_hash: Exact immutable unit reviewed by the human.
        decision: APPROVE or REJECT.
        reviewer_id: Stable opaque HUMAN ID.
        decided_at_utc: Explicit UTC timestamp.
        reason: Human rationale.
        supersedes_decision_id: Existing effective tip or ``None``.

    Returns:
        Appended strict ReviewDecision.

    Raises:
        ReviewCliError: On Run/unit/context/chain drift or a repeated decision.
    """
    with review_run_lock(run_dir=run_dir):
        manifest, records, decisions = _load_open_review_run(run_dir=run_dir)
        run_id = str(manifest["run_id"])
        unit = _select_review_unit(
            run_id=run_id,
            records=records,
            review_unit_hash=review_unit_hash,
        )
        # The HUMAN choice must bind the bytes visible now, not only hashes
        # copied into an earlier ReviewUnit record.
        _verify_review_context(
            run_dir=run_dir, run_id=run_id, review_unit=unit,
        )
        bound = _bound_decisions(
            decisions=decisions, review_unit_hash=review_unit_hash,
        )
        tip = _effective_tip(
            run_id=run_id, review_unit=unit, decisions=bound,
        )
        current_tip = (
            None if tip is None else str(tip["review_decision_id"])
        )
        details = {
            "run_id": run_id,
            "review_unit_hash": review_unit_hash,
            "requested_supersedes_id": supersedes_decision_id,
            "current_effective_tip": current_tip,
            "decision_chain": _chain_summary(decisions=bound),
        }
        if tip is not None and supersedes_decision_id is None:
            raise ReviewCliError(
                code="DECISION_ALREADY_EFFECTIVE",
                message="This ReviewUnit already has an effective decision.",
                details=details,
            )
        if supersedes_decision_id != current_tip:
            details["recovery_command"] = _recovery_command(
                run_dir=run_dir,
                review_unit_hash=review_unit_hash,
                decision=decision,
                reviewer_id=reviewer_id,
                decided_at_utc=decided_at_utc,
                reason=reason,
                current_tip=current_tip,
            )
            raise ReviewCliError(
                code="SUPERSEDES_NOT_EFFECTIVE_TIP",
                message="Requested supersedes ID is not the effective tip.",
                details=details,
            )
        required_claims = dict(unit["required_claims"])
        approved_claims = required_claims if decision == "APPROVE" else {}
        try:
            created = create_review_decision(
                review_unit=unit,
                decision=decision,
                approved_claims=approved_claims,
                required_claims=required_claims,
                reviewer_id=reviewer_id,
                decided_at_utc=decided_at_utc,
                reason=reason,
                supersedes_decision_id=supersedes_decision_id,
            )
            append_review_decision(run_dir=run_dir, decision=created)
        except (ReviewError, RunStoreError, ValueError) as error:
            raise ReviewCliError(
                code="REVIEW_DECISION_INVALID",
                message="HUMAN decision failed semantic binding.",
                details={
                    "run_id": run_id,
                    "review_unit_hash": review_unit_hash,
                },
            ) from error
        return created


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone review CLI parser.

    Returns:
        Parser supporting list, show, and decide subcommands.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="review_action", required=True)
    list_parser = commands.add_parser("list")
    list_parser.add_argument("--run-dir", required=True)
    show_parser = commands.add_parser("show")
    show_parser.add_argument("--run-dir", required=True)
    show_parser.add_argument("--review-unit-hash", required=True)
    decide_parser = commands.add_parser("decide")
    decide_parser.add_argument("--run-dir", required=True)
    decide_parser.add_argument("--review-unit-hash", required=True)
    decide_parser.add_argument(
        "--decision", choices=("APPROVE", "REJECT"), required=True,
    )
    decide_parser.add_argument("--reviewer-id", required=True)
    decide_parser.add_argument("--decided-at-utc", required=True)
    decide_parser.add_argument("--reason", required=True)
    decide_parser.add_argument("--supersedes-decision-id")
    return parser


def _plain_result(*, action: str, result: Mapping[str, object]) -> str:
    """Render concise human output while preserving full JSON on request.

    Args:
        action: Review subcommand.
        result: Successful structured result.

    Returns:
        Human-readable output.
    """
    if action == "show":
        return str(result["review_markdown"])
    if action == "decide":
        return str(result["review_decision_id"])
    return json.dumps(result, ensure_ascii=False, indent=2)


def _normalize_global_flags(*, argv: Sequence[str]) -> Sequence[str]:
    """Allow structured/debug flags before or after a review subcommand.

    Args:
        argv: Original command tokens.

    Returns:
        Tokens with global flags moved before the action.
    """
    flags = [value for value in argv if value in {"--json", "--debug"}]
    remainder = [
        value for value in argv if value not in {"--json", "--debug"}
    ]
    return [*flags, *remainder]


def main(*, argv: Sequence[str]) -> int:
    """Run list/show/decide without tracebacks unless ``--debug`` is present.

    Args:
        argv: CLI arguments excluding executable name.

    Returns:
        Zero on success and two on a stable review failure.
    """
    arguments_list = list(_normalize_global_flags(argv=argv))
    # Preserve the historical decide-only invocation while documenting the
    # explicit subcommand form as the supported operator journey.
    first_business = next(
        (
            value
            for value in arguments_list
            if value not in {"--json", "--debug"}
        ),
        "",
    )
    if first_business.startswith("--") and first_business != "--help":
        insertion = arguments_list.index(first_business)
        arguments_list.insert(insertion, "decide")
    arguments = build_parser().parse_args(arguments_list)
    try:
        if arguments.review_action == "list":
            result = list_human_reviews(run_dir=Path(arguments.run_dir))
        elif arguments.review_action == "show":
            result = show_human_review(
                run_dir=Path(arguments.run_dir),
                review_unit_hash=arguments.review_unit_hash,
            )
        else:
            result = append_human_decision(
                run_dir=Path(arguments.run_dir),
                review_unit_hash=arguments.review_unit_hash,
                decision=arguments.decision,
                reviewer_id=arguments.reviewer_id,
                decided_at_utc=arguments.decided_at_utc,
                reason=arguments.reason,
                supersedes_decision_id=arguments.supersedes_decision_id,
            )
    # The CLI process boundary intentionally converts every ordinary exception
    # so the default operator path never leaks a Python traceback.
    except Exception as error:
        if arguments.debug:
            traceback.print_exc()
        if isinstance(error, ReviewCliError):
            code = error.code
            details = error.details
        else:
            code = "REVIEW_COMMAND_FAILED"
            details = {"error_class": type(error).__name__}
        payload = {
            "ok": False,
            "error": {
                "code": code,
                "message": str(error),
                "details": details,
            },
        }
        if arguments.json_output:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print("{}: {}".format(code, error), file=sys.stderr)
            if "recovery_command" in details:
                print(details["recovery_command"], file=sys.stderr)
        return 2
    if arguments.json_output:
        print(
            json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(_plain_result(action=arguments.review_action, result=result))
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
