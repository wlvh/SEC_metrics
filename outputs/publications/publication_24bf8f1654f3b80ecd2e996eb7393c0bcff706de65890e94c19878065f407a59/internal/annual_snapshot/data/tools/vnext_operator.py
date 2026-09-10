"""Operate the supported vNext Run, review, projection, and publication flow.

This CLI is a thin composition layer over the same production primitives used
by recorded and live execution. It never creates a HUMAN decision implicitly,
never supplies transport authority, and never reads a publication as a loose
set of root files. Expected failures use stable codes; Python tracebacks are
emitted only when the operator explicitly supplies ``--debug``.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
TOOLS_DIR = REPO_ROOT / "tools"
for import_path in (REPO_ROOT, SCRIPTS_DIR, TOOLS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from vnext.ai_adapter import (  # noqa: E402
    build_invocation_controlled_transport_adapter,
    build_recorded_adapter,
)
from vnext.canonical import content_hash, strict_json_file  # noqa: E402
from vnext.projector import (  # noqa: E402
    write_projection_batch_manifest,
    write_projection_candidate,
)
from vnext.recorded_fixtures import (  # noqa: E402
    RecordedFixtureError,
    list_recorded_fixtures,
    load_recorded_fixture,
)
from vnext.publication import (  # noqa: E402
    PublicationView,
    prepare_publication_bundle,
    publication_layout,
    rollback_publication,
    write_publication_validation_receipt,
)
from vnext.replay import replay_frozen_results  # noqa: E402
from vnext.run_store import (  # noqa: E402
    load_open_run,
    load_run_for_status,
    validate_and_freeze_run,
)
from vnext.workflow import (  # noqa: E402
    LiveSourceAuthorityError,
    create_review_run,
    finalize_reviewed_direct_results,
)
from vnext_review import (  # noqa: E402
    ReviewCliError,
    append_human_decision,
    build_review_decision_command,
    list_human_reviews,
    review_run_lock,
    show_human_review,
)
from sec_http import SecIdentityError, load_config  # noqa: E402


class OperatorCliError(RuntimeError):
    """Carry a stable operator error code and structured diagnostic context."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Optional[Mapping[str, object]] = None,
    ) -> None:
        """Create one expected operator failure.

        Args:
            code: Machine-stable uppercase error code.
            message: Concise human explanation.
            details: Optional JSON-compatible recovery context.
        """
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else dict(details)


def _add_run_dir(*, parser: argparse.ArgumentParser) -> None:
    """Add the common explicit Run locator to one subcommand parser.

    Args:
        parser: Parser receiving the required option.
    """
    parser.add_argument("--run-dir", required=True)


def _add_publication_switch_arguments(
    *, parser: argparse.ArgumentParser
) -> None:
    """Add the exact CAS inputs shared by rollback and restore.

    Args:
        parser: Parser receiving publication switch arguments.
    """
    parser.add_argument("--publication-root", required=True)
    parser.add_argument("--target-publication-id", required=True)
    parser.add_argument("--expected-active-publication-id", required=True)
    parser.add_argument("--committed-at-utc", required=True)


def _add_review_commands(*, parent: argparse.ArgumentParser) -> None:
    """Add list/show/decide beneath the operator review command.

    Args:
        parent: Top-level review parser.
    """
    actions = parent.add_subparsers(dest="review_action", required=True)
    list_parser = actions.add_parser("list")
    _add_run_dir(parser=list_parser)
    show_parser = actions.add_parser("show")
    _add_run_dir(parser=show_parser)
    show_parser.add_argument("--review-unit-hash", required=True)
    decide_parser = actions.add_parser("decide")
    _add_run_dir(parser=decide_parser)
    decide_parser.add_argument("--review-unit-hash", required=True)
    decide_parser.add_argument(
        "--decision", choices=("APPROVE", "REJECT"), required=True,
    )
    decide_parser.add_argument("--reviewer-id", required=True)
    decide_parser.add_argument("--decided-at-utc", required=True)
    decide_parser.add_argument("--reason", required=True)
    decide_parser.add_argument("--supersedes-decision-id")


def build_parser() -> argparse.ArgumentParser:
    """Build the single supported operator command surface.

    Returns:
        Parser covering Run preparation through acceptance and rollback.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    fixture = commands.add_parser("fixture")
    fixture_actions = fixture.add_subparsers(
        dest="fixture_action", required=True,
    )
    fixture_actions.add_parser("list")
    fixture_show = fixture_actions.add_parser("show")
    fixture_show.add_argument("--fixture-id", required=True)

    prepare = commands.add_parser("prepare", aliases=["init"])
    prepare.add_argument("--run-dir")
    prepare.add_argument("--run-id")
    prepare.add_argument("--company-id")
    prepare.add_argument("--fiscal-year", type=int)
    prepare.add_argument("--period-start")
    prepare.add_argument("--period-end")
    prepare.add_argument("--source-path")
    prepare.add_argument("--source-media-type")
    prepare.add_argument("--source-url")
    prepare.add_argument("--accession")
    prepare.add_argument("--document-name")
    prepare.add_argument("--source-role")
    prepare.add_argument("--request-attempt-id")
    prepare.add_argument("--disclosure-spec-path")
    mode = prepare.add_mutually_exclusive_group()
    mode.add_argument(
        "--recorded-response", help=argparse.SUPPRESS,
    )
    mode.add_argument("--execute-live", action="store_true")
    prepare.add_argument("--fixture-id")

    status = commands.add_parser("status")
    status_target = status.add_mutually_exclusive_group(required=True)
    status_target.add_argument("--run-dir")
    status_target.add_argument("--publication-root")

    review = commands.add_parser("review")
    _add_review_commands(parent=review)

    for command in ("resume", "finalize"):
        command_parser = commands.add_parser(command)
        _add_run_dir(parser=command_parser)
    freeze = commands.add_parser("freeze")
    _add_run_dir(parser=freeze)

    replay = commands.add_parser("replay")
    _add_run_dir(parser=replay)

    project = commands.add_parser("project")
    project.add_argument("--batch-manifest", required=True)
    project.add_argument("--run-dir", action="append", required=True)
    project.add_argument("--legacy-snapshot-dir", required=True)
    project.add_argument("--staging-dir", required=True)

    publish = commands.add_parser(
        "publish",
        description=(
            "Prepare an offline/recorded publication bundle only. Formal "
            "forward commit requires tools/vnext_cutover.py --execute-live."
        ),
    )
    publish.add_argument("--publication-root", required=True)
    publish.add_argument("--batch-manifest", required=True)
    publish.add_argument("--legacy-snapshot-dir", required=True)
    publish.add_argument("--staging-dir", required=True)
    publish.add_argument("--previous-publication-id")
    publish.add_argument("--validated-at-utc", required=True)
    publish.add_argument(
        "--commit",
        action="store_true",
        help=(
            "Rejected here; use tools/vnext_cutover.py --execute-live for "
            "formal forward publication."
        ),
    )
    publish.add_argument(
        "--committed-at-utc",
        help="Legacy commit input; never authorizes generic publish.",
    )
    publish.add_argument(
        "--expected-active-publication-id",
        help="Legacy commit input; never authorizes generic publish.",
    )

    rollback = commands.add_parser("rollback")
    _add_publication_switch_arguments(parser=rollback)
    restore = commands.add_parser("restore")
    _add_publication_switch_arguments(parser=restore)

    acceptance = commands.add_parser("acceptance")
    acceptance.add_argument(
        "--scope", choices=("recorded", "full"), required=True,
    )
    acceptance.add_argument("--execute-live", action="store_true")
    acceptance.add_argument("--python39")
    acceptance.add_argument("--timeout-seconds", type=int)
    acceptance.add_argument("--output-dir")
    return parser


def _fixture_error(*, error: RecordedFixtureError) -> OperatorCliError:
    """Translate repository fixture failures to the operator envelope.

    Args:
        error: Stable failure raised by the catalog loader.

    Returns:
        Equivalent operator error without internal path details.
    """
    return OperatorCliError(code=error.code, message=str(error))


def _fixture_commands(*, fixture: Mapping[str, object]) -> Dict[str, str]:
    """Build cold-start commands containing only one safe fixture identity.

    Args:
        fixture: Verified normalized fixture record.

    Returns:
        Copyable single-Run prepare and complete recorded Cutover commands.
    """
    fixture_id = str(fixture["fixture_id"])
    return {
        "prepare_command": shlex.join([
            "python3",
            "tools/vnext_operator.py",
            "--json",
            "prepare",
            "--fixture-id",
            fixture_id,
        ]),
        "cutover_command": shlex.join([
            "python3",
            "tools/vnext_cutover.py",
            "--json",
            "--fixture-id",
            fixture_id,
        ]),
    }


def _fixture(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """List or show repository-owned fixture identities and commands.

    Args:
        arguments: Parsed fixture list/show action.

    Returns:
        Verified catalog summaries or one complete normalized fixture.
    """
    try:
        if arguments.fixture_action == "show":
            fixture = load_recorded_fixture(
                repo_root=REPO_ROOT, fixture_id=arguments.fixture_id,
            )
            return {
                "fixture": fixture,
                **_fixture_commands(fixture=fixture),
            }
        catalog = list_recorded_fixtures(repo_root=REPO_ROOT)
    except RecordedFixtureError as error:
        raise _fixture_error(error=error) from error
    fixtures = []
    for fixture in catalog["fixtures"]:
        fixtures.append({
            "display_name": fixture["display_name"],
            "fixture_binding_id": fixture["fixture_binding_id"],
            "fixture_id": fixture["fixture_id"],
            "provenance_id": fixture["provenance"]["id"],
            **_fixture_commands(fixture=fixture),
        })
    return {
        "catalog_id": catalog["catalog_id"],
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
    }


def _fixture_run_dir(
    *, fixture_id: str, requested: Optional[str],
) -> Path:
    """Resolve shortcut workspace state below the fixed repository root.

    Args:
        fixture_id: Safe catalog fixture identity.
        requested: Optional caller workspace locator, never an authority root.

    Returns:
        Real Run directory strictly below ``artifacts/vnext``.

    Raises:
        OperatorCliError: When the lexical or resolved path leaves the
            recorded artifact namespace, names that namespace root, or
            traverses a symlink/non-directory component.
    """
    repository = Path(os.path.abspath(str(REPO_ROOT)))
    candidate = (
        Path(requested)
        if requested is not None
        else Path("artifacts/vnext/runs/open") / fixture_id
    )
    lexical = Path(os.path.abspath(str(
        candidate if candidate.is_absolute() else repository / candidate
    )))
    allowed_root = repository / "artifacts" / "vnext"
    try:
        relative = lexical.relative_to(allowed_root)
    except ValueError as error:
        raise OperatorCliError(
            code="RECORDED_FIXTURE_WORKSPACE_INVALID",
            message=(
                "Recorded fixture Run must be a strict descendant of "
                "artifacts/vnext."
            ),
        ) from error
    if relative == Path("."):
        raise OperatorCliError(
            code="RECORDED_FIXTURE_WORKSPACE_INVALID",
            message=(
                "Recorded fixture Run must be a strict descendant of "
                "artifacts/vnext."
            ),
        )

    # Every lexical component is checked before create_review_run can create
    # bytes, preventing an existing symlink from redirecting Run authority.
    repository_relative = lexical.relative_to(repository)
    current = repository
    for part in repository_relative.parts:
        current = current / part
        if current.is_symlink() or (
            current.exists() and not current.is_dir()
        ):
            raise OperatorCliError(
                code="RECORDED_FIXTURE_WORKSPACE_INVALID",
                message="Recorded fixture Run contains an unsafe path.",
            )
    resolved = lexical.resolve(strict=False)
    try:
        resolved_relative = resolved.relative_to(allowed_root.resolve())
    except ValueError as error:
        raise OperatorCliError(
            code="RECORDED_FIXTURE_WORKSPACE_INVALID",
            message="Recorded fixture Run resolves outside artifacts/vnext.",
        ) from error
    if resolved_relative == Path("."):
        raise OperatorCliError(
            code="RECORDED_FIXTURE_WORKSPACE_INVALID",
            message=(
                "Recorded fixture Run must be a strict descendant of "
                "artifacts/vnext."
            ),
        )
    return resolved


def _explicit_prepare_values(
    *, arguments: argparse.Namespace,
) -> Dict[str, object]:
    """Validate the legacy explicit recorded/live prepare argument set.

    Args:
        arguments: Parsed explicit preparation inputs.

    Returns:
        Complete business/source mapping with no implicit ``None`` values.
    """
    values = {
        "accession": arguments.accession,
        "company_id": arguments.company_id,
        "disclosure_spec_path": arguments.disclosure_spec_path,
        "document_name": arguments.document_name,
        "fiscal_year": arguments.fiscal_year,
        "period_end": arguments.period_end,
        "period_start": arguments.period_start,
        "request_attempt_id": arguments.request_attempt_id,
        "run_dir": arguments.run_dir,
        "run_id": arguments.run_id,
        "source_media_type": arguments.source_media_type,
        "source_path": arguments.source_path,
        "source_role": arguments.source_role,
        "source_url": arguments.source_url,
    }
    missing = sorted(
        field for field, value in values.items() if value is None
    )
    if missing:
        raise OperatorCliError(
            code="PREPARE_ARGUMENTS_REQUIRED",
            message="Explicit prepare inputs are incomplete.",
            details={"missing_fields": missing},
        )
    return values


def _prepare(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Create a real OPEN Run through the shared recorded/live workflow.

    Args:
        arguments: Parsed prepare command inputs.

    Returns:
        Workflow result plus exact review paths when HUMAN review is required.
    """
    fixture = None
    if arguments.recorded_response is not None:
        raise OperatorCliError(
            code="RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
            message=(
                "Recorded mode requires a repository catalog fixture and "
                "rejects a caller-selected response."
            ),
        )
    if arguments.execute_live and arguments.fixture_id is not None:
        raise OperatorCliError(
            code="LIVE_FIXTURE_ID_FORBIDDEN",
            message="Live mode cannot claim a recorded fixture identity.",
        )
    fixture_shortcut = (
        arguments.fixture_id is not None
        and not arguments.execute_live
    )
    if fixture_shortcut:
        overrides = {
            "accession": arguments.accession,
            "company_id": arguments.company_id,
            "disclosure_spec_path": arguments.disclosure_spec_path,
            "document_name": arguments.document_name,
            "fiscal_year": arguments.fiscal_year,
            "period_end": arguments.period_end,
            "period_start": arguments.period_start,
            "request_attempt_id": arguments.request_attempt_id,
            "source_media_type": arguments.source_media_type,
            "source_path": arguments.source_path,
            "source_role": arguments.source_role,
            "source_url": arguments.source_url,
        }
        supplied = sorted(
            field for field, value in overrides.items() if value is not None
        )
        if supplied:
            raise OperatorCliError(
                code="RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
                message="Fixture mode rejects caller business authority.",
                details={"supplied_fields": supplied},
            )
        try:
            fixture = load_recorded_fixture(
                repo_root=REPO_ROOT, fixture_id=arguments.fixture_id,
            )
        except RecordedFixtureError as error:
            raise _fixture_error(error=error) from error
        run_dir = _fixture_run_dir(
            fixture_id=str(fixture["fixture_id"]),
            requested=arguments.run_dir,
        )
        values = {
            "accession": fixture["source"]["accession"],
            "company_id": fixture["company_id"],
            "disclosure_spec_path": fixture["disclosure"]["spec_path"],
            "document_name": fixture["source"]["document_name"],
            "fiscal_year": fixture["target_period"]["fiscal_year"],
            "period_end": fixture["target_period"]["period_end"],
            "period_start": fixture["target_period"]["period_start"],
            "request_attempt_id": fixture["source"]["request_attempt_id"],
            "run_dir": run_dir,
            "run_id": (
                arguments.run_id
                if arguments.run_id is not None
                else "run:recorded:fixture:" + str(fixture["fixture_id"])
            ),
            "source_media_type": fixture["source"]["media_type"],
            "source_path": fixture["source"]["repo_relative_path"],
            "source_role": fixture["source"]["role"],
            "source_url": fixture["source"]["url"],
        }
        response_path = REPO_ROOT / str(
            fixture["response"]["repo_relative_path"]
        )
        adapter = build_recorded_adapter(
            response_bytes=response_path.read_bytes(),
            fixture_id=str(fixture["fixture_binding_id"]),
        )
    else:
        values = _explicit_prepare_values(arguments=arguments)
        run_dir = Path(str(values["run_dir"]))
        if not arguments.execute_live:
            raise OperatorCliError(
                code="PREPARE_MODE_REQUIRED",
                message="Prepare requires a catalog fixture or live mode.",
            )
        # Live preparation cannot open OpenAI while SEC identity is unusable,
        # preserving one shared remote prerequisite boundary.
        try:
            load_config(
                config_path=REPO_ROOT / "config" / "sec_config.json"
            )
        except SecIdentityError as error:
            raise OperatorCliError(
                code=error.code, message=error.detail,
            ) from error
        operator_release_input_plan_id = content_hash(
            value={
                "record_type": "OPERATOR_RELEASE_INPUT_PLAN",
                "run_id": values["run_id"],
                "company_id": values["company_id"],
                "target_period": {
                    "fiscal_year": values["fiscal_year"],
                    "period_start": values["period_start"],
                    "period_end": values["period_end"],
                },
                "source_url": values["source_url"],
                "accession": values["accession"],
                "document_name": values["document_name"],
                "disclosure_spec_path": values["disclosure_spec_path"],
            }
        )
        adapter = build_invocation_controlled_transport_adapter(
            release_input_plan_id=operator_release_input_plan_id,
            workspace_dir=run_dir.parent,
            owner_token=run_dir.name,
        )
    result = create_review_run(
        repo_root=REPO_ROOT,
        run_dir=run_dir,
        run_id=str(values["run_id"]),
        company_id=str(values["company_id"]),
        target_period={
            "fiscal_year": values["fiscal_year"],
            "period_start": values["period_start"],
            "period_end": values["period_end"],
        },
        source_repo_relative_path=str(values["source_path"]),
        source_media_type=str(values["source_media_type"]),
        source_url=str(values["source_url"]),
        accession=str(values["accession"]),
        document_name=str(values["document_name"]),
        source_role=str(values["source_role"]),
        request_attempt_id=str(values["request_attempt_id"]),
        disclosure_spec_path=str(values["disclosure_spec_path"]),
        adapter=adapter,
        clock=None,
    )
    output = dict(result)
    if fixture is not None:
        output["recorded_fixture"] = fixture
    if result["status"] != "PENDING_HUMAN_REVIEW":
        return output
    shown = show_human_review(
        run_dir=run_dir,
        review_unit_hash=str(result["review_unit_hash"]),
    )
    output.update({
        "review_path": shown["review_path"],
        "review_context_path": shown["review_context_path"],
        "review_command": build_review_decision_command(
            run_dir=run_dir,
            review_unit_hash=str(result["review_unit_hash"]),
        ),
    })
    return output


def _run_status(*, run_dir: Path) -> Dict[str, object]:
    """Read one Run through the state-appropriate verifier.

    Args:
        run_dir: Persisted Run locator.

    Returns:
        Verified state and record counts, with OPEN review state when present.
    """
    manifest, records, decisions = load_run_for_status(
        run_dir=run_dir, repo_root=REPO_ROOT,
    )
    result = {
        "run_id": manifest["run_id"],
        "status": manifest["status"],
        "record_count": len(records),
        "decision_count": len(decisions),
    }
    if manifest["status"] == "OPEN":
        result["review"] = list_human_reviews(run_dir=run_dir)
    return result


def _publication_status(*, publication_root: Path) -> Dict[str, object]:
    """Open one pinned active PublicationView and read optional latest status.

    Args:
        publication_root: Single authority root for pointer and bundles.

    Returns:
        Active publication identity, manifest, and separate latest status.
    """
    layout = publication_layout(publication_root=publication_root)
    pointer_path = layout["pointer_path"]
    view = None
    if pointer_path.exists() or pointer_path.is_symlink():
        view = PublicationView.open(publication_root=publication_root)
    latest_path = layout["latest_status_path"]
    latest = None
    if latest_path.is_symlink() or (
        latest_path.exists() and not latest_path.is_file()
    ):
        raise OperatorCliError(
            code="LATEST_RUN_STATUS_INVALID",
            message="Latest Run status is not one regular authority file.",
        )
    if latest_path.is_file():
        latest = strict_json_file(path=latest_path)
    return {
        "active_publication_id": (
            view.publication_id if view is not None else None
        ),
        "active_manifest": (
            dict(view.manifest) if view is not None else None
        ),
        "latest_run_status": latest,
    }


def _review(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Dispatch operator review actions to the standalone shared helpers.

    Args:
        arguments: Parsed nested review command.

    Returns:
        Structured list, show, or immutable decision result.
    """
    run_dir = Path(arguments.run_dir)
    if arguments.review_action == "list":
        return list_human_reviews(run_dir=run_dir)
    if arguments.review_action == "show":
        return show_human_review(
            run_dir=run_dir,
            review_unit_hash=arguments.review_unit_hash,
        )
    return append_human_decision(
        run_dir=run_dir,
        review_unit_hash=arguments.review_unit_hash,
        decision=arguments.decision,
        reviewer_id=arguments.reviewer_id,
        decided_at_utc=arguments.decided_at_utc,
        reason=arguments.reason,
        supersedes_decision_id=arguments.supersedes_decision_id,
    )


def _finalize(*, run_dir: Path) -> Dict[str, object]:
    """Atomically materialize, mechanically validate, and freeze a Run.

    Args:
        run_dir: OPEN Run after HUMAN review.

    Returns:
        Created identities and the mechanically proven FROZEN identity.
    """
    with review_run_lock(run_dir=run_dir):
        manifest, records, _decisions = load_open_run(run_dir=run_dir)
        results = [
            record
            for record in records
            if record["record_type"] == "METRIC_RESULT"
        ]
        if results:
            # The core finalizer writes the entire set in one CAS replacement.
            # Mechanical replay, rather than presence alone, proves whether a
            # process stopped after that replacement but before freeze.
            frozen = validate_and_freeze_run(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            return {
                "run_id": manifest["run_id"],
                "status": frozen["status"],
                "resumed_after_atomic_finalization": True,
                "observation_ids": [
                    record["observation_id"]
                    for record in records
                    if record["record_type"] == "VERIFIED_OBSERVATION"
                ],
                "result_ids": [
                    result["result_id"] for result in results
                ],
                "trace_ids": [
                    record["trace_id"]
                    for record in records
                    if record["record_type"] == "EXECUTION_TRACE"
                ],
                "content_manifest_hash": frozen["content_manifest_hash"],
                "audit_manifest_hash": frozen["audit_manifest_hash"],
            }
        finalized = finalize_reviewed_direct_results(
            run_dir=run_dir, repo_root=REPO_ROOT,
        )
        frozen = validate_and_freeze_run(
            run_dir=run_dir, repo_root=REPO_ROOT,
        )
        return {
            "run_id": manifest["run_id"],
            "status": frozen["status"],
            "content_manifest_hash": frozen["content_manifest_hash"],
            "audit_manifest_hash": frozen["audit_manifest_hash"],
            **finalized,
        }


def _freeze(*, run_dir: Path) -> Dict[str, object]:
    """Mechanically validate and freeze an externally finalized OPEN Run.

    Args:
        run_dir: Finalized OPEN Run.

    Returns:
        Mechanically validated FROZEN manifest.
    """
    with review_run_lock(run_dir=run_dir):
        return validate_and_freeze_run(
            run_dir=run_dir, repo_root=REPO_ROOT,
        )


def _project(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Build a complete BatchManifest and Run-derived staging candidate.

    Args:
        arguments: Parsed batch, Run, legacy, and staging paths.

    Returns:
        Batch identity and projection summary.
    """
    batch = write_projection_batch_manifest(
        repo_root=REPO_ROOT,
        batch_manifest_path=Path(arguments.batch_manifest),
        run_dirs=[Path(value) for value in arguments.run_dir],
    )
    candidate = write_projection_candidate(
        repo_root=REPO_ROOT,
        batch_manifest_path=Path(arguments.batch_manifest),
        legacy_snapshot_dir=Path(arguments.legacy_snapshot_dir),
        staging_dir=Path(arguments.staging_dir),
    )
    return {
        "batch_manifest_id": batch["batch_manifest_id"],
        "candidate": candidate,
    }


def _publish(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Execute recorded staging gates and prepare one inactive bundle.

    Args:
        arguments: Parsed publication authority and concurrency inputs.

    Returns:
        Validation and prepared manifest without changing formal active state.
    """
    if arguments.commit:
        raise OperatorCliError(
            code="FORMAL_COMMIT_REQUIRES_CUTOVER",
            message=(
                "Generic operator publish cannot commit formal active state."
            ),
            details={
                "recovery_command": (
                    "python3 tools/vnext_cutover.py --help"
                ),
                "required_entrypoint": (
                    "tools/vnext_cutover.py --execute-live"
                ),
            },
        )
    publication_root = Path(arguments.publication_root)
    receipt = write_publication_validation_receipt(
        repo_root=REPO_ROOT,
        batch_manifest_path=Path(arguments.batch_manifest),
        legacy_snapshot_dir=Path(arguments.legacy_snapshot_dir),
        staging_dir=Path(arguments.staging_dir),
        previous_publication_id=arguments.previous_publication_id,
        validated_at_utc=arguments.validated_at_utc,
    )
    manifest = prepare_publication_bundle(
        publication_root=publication_root,
        repo_root=REPO_ROOT,
        batch_manifest_path=Path(arguments.batch_manifest),
        legacy_snapshot_dir=Path(arguments.legacy_snapshot_dir),
        staging_dir=Path(arguments.staging_dir),
        previous_publication_id=arguments.previous_publication_id,
    )
    result = {
        "validation_receipt_id": receipt["validation_receipt_id"],
        "publication_id": manifest["publication_id"],
        "publication_manifest": manifest,
        "committed_pointer": None,
    }
    return result


def _switch_publication(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Rollback or restore using the same verified predecessor/CAS primitive.

    Args:
        arguments: Parsed pointer-switch inputs.

    Returns:
        Newly committed active pointer.
    """
    return rollback_publication(
        publication_root=Path(arguments.publication_root),
        target_publication_id=arguments.target_publication_id,
        expected_active_publication_id=(
            arguments.expected_active_publication_id
        ),
        committed_at_utc=arguments.committed_at_utc,
    )


def _acceptance(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Delegate to the authoritative acceptance runner as a real command.

    Args:
        arguments: Parsed scope and optional live execution controls.

    Returns:
        Captured runner result when it exits zero.
    """
    argv = [
        sys.executable,
        str(REPO_ROOT / "tools" / "run_acceptance.py"),
        "--scope",
        arguments.scope,
    ]
    if arguments.execute_live:
        argv.append("--execute-live")
    if arguments.python39 is not None:
        argv.extend(["--python39", arguments.python39])
    if arguments.timeout_seconds is not None:
        argv.extend(["--timeout-seconds", str(arguments.timeout_seconds)])
    if arguments.output_dir is not None:
        argv.extend(["--output-dir", arguments.output_dir])
    completed = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise OperatorCliError(
            code="ACCEPTANCE_NOT_PASSED",
            message="Acceptance runner did not produce a passing receipt.",
            details={
                "return_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
    return {
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _execute(*, arguments: argparse.Namespace) -> Dict[str, object]:
    """Dispatch one parsed command to the corresponding production primitive.

    Args:
        arguments: Parsed operator arguments.

    Returns:
        Structured command result.
    """
    if arguments.command == "fixture":
        return _fixture(arguments=arguments)
    if arguments.command in {"prepare", "init"}:
        return _prepare(arguments=arguments)
    if arguments.command == "status":
        if arguments.run_dir is not None:
            return _run_status(run_dir=Path(arguments.run_dir))
        return _publication_status(
            publication_root=Path(arguments.publication_root)
        )
    if arguments.command == "review":
        return _review(arguments=arguments)
    if arguments.command in {"resume", "finalize"}:
        return _finalize(run_dir=Path(arguments.run_dir))
    if arguments.command == "freeze":
        return _freeze(run_dir=Path(arguments.run_dir))
    if arguments.command == "replay":
        return replay_frozen_results(
            run_dir=Path(arguments.run_dir), repo_root=REPO_ROOT,
        )
    if arguments.command == "project":
        return _project(arguments=arguments)
    if arguments.command == "publish":
        return _publish(arguments=arguments)
    if arguments.command in {"rollback", "restore"}:
        return _switch_publication(arguments=arguments)
    if arguments.command == "acceptance":
        return _acceptance(arguments=arguments)
    raise OperatorCliError(
        code="OPERATOR_COMMAND_UNKNOWN",
        message="Operator command is not implemented.",
    )


def _normalize_global_flags(*, argv: Sequence[str]) -> Sequence[str]:
    """Allow ``--json`` and ``--debug`` before or after nested commands.

    Args:
        argv: Original command tokens.

    Returns:
        Tokens with global flags moved before the command.
    """
    flags = [value for value in argv if value in {"--json", "--debug"}]
    remainder = [value for value in argv if value not in {"--json", "--debug"}]
    return [*flags, *remainder]


def _error_payload(*, error: Exception) -> Dict[str, object]:
    """Convert a known or unexpected failure to the stable output envelope.

    Args:
        error: Raised command exception.

    Returns:
        JSON-compatible error payload.
    """
    if isinstance(error, (OperatorCliError, ReviewCliError)):
        return {
            "code": error.code,
            "message": str(error),
            "details": error.details,
        }
    if isinstance(error, LiveSourceAuthorityError):
        return {
            "code": "LIVE_SOURCE_AUTHORITY_INVALID",
            "message": str(error),
            "details": {},
        }
    return {
        "code": "OPERATOR_COMMAND_FAILED",
        "message": str(error),
        "details": {"error_class": type(error).__name__},
    }


def main(*, argv: Sequence[str]) -> int:
    """Run one operator command with optional structured/debug output.

    Args:
        argv: CLI arguments excluding executable name.

    Returns:
        Zero on success and two on an expected or fail-closed error.
    """
    arguments = build_parser().parse_args(
        list(_normalize_global_flags(argv=argv))
    )
    try:
        result = _execute(arguments=arguments)
    # The CLI process boundary intentionally catches ordinary exceptions so
    # production output never contains a traceback without explicit --debug.
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
            if "recovery_command" in details:
                print(details["recovery_command"], file=sys.stderr)
            if "review_command" in details:
                print(details["review_command"], file=sys.stderr)
        return 2
    payload = {"ok": True, "command": arguments.command, "result": result}
    if arguments.json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
