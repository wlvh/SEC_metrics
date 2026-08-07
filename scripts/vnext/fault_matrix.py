"""Execute the formal publication failure matrix in persistent isolation.

``run_formal_publication_fault_matrix`` first proves that one already committed
successor and its committed predecessor are reproducible from the supplied
Batch/staging authority.  It then clones only those verified immutable bundles
into one retained workspace per scenario and exercises the real publication
prepare, commit, rollback, recovery, CAS, pinned-view, and verification entry
points.  Fault observations are written to the formal receipt root, while no
scenario can switch its official active pointer.
"""

from __future__ import annotations

import csv
import shutil
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, Mapping, Optional, Sequence

from . import publication as publication_module
from .batch_workflow import create_structural_release_run
from .canonical import CanonicalError, atomic_write_bytes, atomic_write_json
from .canonical import content_hash, parse_utc_timestamp, strict_json_file
from .projector import ProjectionError, load_projection_batch_manifest
from .projector import write_projection_batch_manifest
from .publication import LEGACY_BASELINE_IMPORT_MANIFEST
from .publication import METRIC_FIELDS, REQUIRED_BUNDLE_FILES
from .publication import PublicationError, PublicationView
from .publication import _commit_initial_publication_chain
from .publication import _commit_publication, prepare_publication_bundle
from .publication import publication_layout, publication_staging_context
from .publication import publication_state_snapshot
from .publication import recover_publication_mirrors, rollback_publication
from .publication import verify_publication_bundle
from .publication import write_publication_fault_receipt
from .run_store import RunStoreError, load_run_for_status
from .run_store import validate_and_freeze_run


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FAULT_MATRIX_SCENARIO_IDS = frozenset(
    {
        "ISOLATED_ACTIVE_BUNDLE_TAMPER",
        "ISOLATED_CAS_LOSER",
        "ISOLATED_CONCURRENT_PUBLISHERS",
        "ISOLATED_DECISION_TAMPER",
        "ISOLATED_MID_BUNDLE_WRITE",
        "ISOLATED_MID_MIRROR_WRITE",
        "ISOLATED_MIRRORS_BEFORE_POINTER",
        "ISOLATED_MIXED_FISCAL_YEAR",
        "ISOLATED_PINNED_VIEW_POINTER_SWITCH",
        "ISOLATED_RECEIPT_TAMPER",
        "ISOLATED_RUN_TAMPER",
        "ISOLATED_SPEC_TAMPER",
        "ISOLATED_TRACE_TAMPER",
        "ISOLATED_WITHHELD_CANDIDATE",
    }
)
_SCENARIO_EXPECTATIONS = {
    "ISOLATED_ACTIVE_BUNDLE_TAMPER": (
        "BUNDLE_READ_BACK", "TAMPER_REJECTED", True, "SUCCESSOR",
    ),
    "ISOLATED_CAS_LOSER": (
        "CAS_POINTER_LOCK", "CAS_LOST_ACTIVE_PRESERVED", True, "SUCCESSOR",
    ),
    "ISOLATED_CONCURRENT_PUBLISHERS": (
        "CAS_POINTER_LOCK", "EXACTLY_ONE_WINNER", True, "SUCCESSOR",
    ),
    "ISOLATED_DECISION_TAMPER": (
        "DECISION_READ_BACK", "TAMPER_REJECTED", True, "SUCCESSOR",
    ),
    "ISOLATED_MID_BUNDLE_WRITE": (
        "MID_BUNDLE_WRITE", "ABORTED_ACTIVE_PRESERVED", True, "PREDECESSOR",
    ),
    "ISOLATED_MID_MIRROR_WRITE": (
        "MID_MIRROR_WRITE", "ABORTED_ACTIVE_PRESERVED", True, "PREDECESSOR",
    ),
    "ISOLATED_MIRRORS_BEFORE_POINTER": (
        "MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT",
        "RECOVERED_FROM_ACTIVE",
        True,
        "PREDECESSOR",
    ),
    "ISOLATED_MIXED_FISCAL_YEAR": (
        "BATCH_MANIFEST_PERIOD_GATE",
        "MIXED_FISCAL_YEAR_BLOCKED",
        False,
        "PREDECESSOR",
    ),
    "ISOLATED_PINNED_VIEW_POINTER_SWITCH": (
        "POINTER_SWITCH_DURING_PINNED_READ",
        "PINNED_VIEW_STABLE",
        True,
        "PREDECESSOR",
    ),
    "ISOLATED_RECEIPT_TAMPER": (
        "RECEIPT_READ_BACK", "TAMPER_REJECTED", True, "SUCCESSOR",
    ),
    "ISOLATED_RUN_TAMPER": (
        "RUN_READ_BACK", "TAMPER_REJECTED", True, "SUCCESSOR",
    ),
    "ISOLATED_SPEC_TAMPER": (
        "SPEC_READ_BACK", "TAMPER_REJECTED", True, "SUCCESSOR",
    ),
    "ISOLATED_TRACE_TAMPER": (
        "TRACE_READ_BACK", "TAMPER_REJECTED", True, "SUCCESSOR",
    ),
    "ISOLATED_WITHHELD_CANDIDATE": (
        "PREPARE_VALIDATION_GATE", "WITHHELD_BLOCKED", False, "PREDECESSOR",
    ),
}
_FAULT_MATRIX_MANIFEST_FIELDS = {
    "execution_scope",
    "fault_matrix_id",
    "fault_receipt_ids",
    "predecessor_publication_id",
    "scenario_ids",
    "schema_version",
    "successor_publication_id",
    "temporary_namespaces_cleaned",
}
_FAULT_RECEIPT_FIELDS = {
    "active_after",
    "active_before",
    "fault_point",
    "fault_receipt_id",
    "mirror_hashes_after",
    "mirror_hashes_before",
    "outcome",
    "prepared_publication_id",
    "scenario_id",
    "schema_version",
    "temporary_workspace_cleaned",
}


class FaultMatrixError(RuntimeError):
    """Report a stable invalid input or failed fault-matrix postcondition."""

    def __init__(self, *, code: str, message: str) -> None:
        """Create a machine-classifiable matrix failure.

        Args:
            code: Stable uppercase operator error code.
            message: Concise diagnostic without secret or absolute-path data.
        """
        super().__init__("{}: {}".format(code, message))
        self.code = code


class _SimulatedProcessCrash(BaseException):
    """Escape transaction recovery to model termination before pointer CAS."""


@dataclass(frozen=True)
class FaultMatrixPreparation:
    """Name one repository-derived publication preparation view.

    Attributes:
        batch_manifest_path: Complete persisted FROZEN BatchManifest.
        legacy_snapshot_dir: Frozen legacy compatibility input directory.
        staging_dir: Exact formally validated candidate directory.
    """

    batch_manifest_path: Path
    legacy_snapshot_dir: Path
    staging_dir: Path


def _validate_execution_time(*, executed_at_utc: str) -> None:
    """Require one explicit UTC timestamp for every isolated pointer switch.

    Args:
        executed_at_utc: ISO-8601 UTC timestamp supplied by the operator.
    """
    try:
        parsed = parse_utc_timestamp(value=executed_at_utc)
    except CanonicalError as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_TIME_INVALID",
            message="Execution timestamp must be timezone-aware UTC",
        ) from error
    if parsed.utcoffset().total_seconds() != 0:
        raise FaultMatrixError(
            code="FAULT_MATRIX_TIME_INVALID",
            message="Execution timestamp must be UTC",
        )


def _validate_workspace(*, fault_workspace_root: Path) -> None:
    """Create one new persistent workspace without overwriting earlier proof.

    Args:
        fault_workspace_root: Dedicated retained scenario parent.
    """
    if fault_workspace_root.is_symlink():
        raise FaultMatrixError(
            code="FAULT_MATRIX_WORKSPACE_UNSAFE",
            message="Fault workspace must not be a symlink",
        )
    if fault_workspace_root.exists():
        if not fault_workspace_root.is_dir():
            raise FaultMatrixError(
                code="FAULT_MATRIX_WORKSPACE_UNSAFE",
                message="Fault workspace must be a real directory",
            )
        if any(fault_workspace_root.iterdir()):
            raise FaultMatrixError(
                code="FAULT_MATRIX_WORKSPACE_NOT_EMPTY",
                message="Fault workspace must be new or empty",
            )
    else:
        fault_workspace_root.mkdir(parents=True)


def _formal_validation_manifest(*, bundle_dir: Path) -> Mapping[str, object]:
    """Require a bundle produced by the formal rather than recorded gate.

    Args:
        bundle_dir: Verified predecessor or successor bundle.

    Returns:
        Exact formal validation manifest.
    """
    path = bundle_dir / "validation_run_manifest.json"
    try:
        payload = strict_json_file(path=path)
    except (CanonicalError, OSError) as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_FORMAL_INPUT_INVALID",
            message="Publication validation manifest is invalid",
        ) from error
    if (
        not isinstance(payload, dict)
        or "mode" not in payload
        or "result" not in payload
        or payload["mode"] != "FULL_VALIDATION"
        or payload["result"] != "PASSED"
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_FORMAL_INPUT_REQUIRED",
            message="Both committed inputs must carry formal PASS evidence",
        )
    return payload


def _preparation_kwargs(
    *, authority_repo_root: Path, preparation: FaultMatrixPreparation,
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Build the exact public prepare call from a fixed repository authority.

    Args:
        authority_repo_root: Repository owning Requirements, Runs, and Specs.
        preparation: Batch, legacy, and staging locators.
        previous_publication_id: Prepared CAS predecessor identity.

    Returns:
        Keyword arguments accepted by ``prepare_publication_bundle``.
    """
    return {
        "repo_root": authority_repo_root,
        "batch_manifest_path": preparation.batch_manifest_path,
        "legacy_snapshot_dir": preparation.legacy_snapshot_dir,
        "staging_dir": preparation.staging_dir,
        "previous_publication_id": previous_publication_id,
    }


def _verify_committed_inputs(
    *, source_publication_root: Path, authority_repo_root: Path,
    fault_workspace_root: Path, successor: FaultMatrixPreparation,
) -> tuple[str, str]:
    """Bind supplied preparation inputs to one committed two-bundle chain.

    Args:
        source_publication_root: Formal root whose active pointer is successor.
        authority_repo_root: Fixed repository authority for both candidates.
        fault_workspace_root: Retained root for idempotent prepare
            verification.
        successor: Preparation inputs for the committed active successor.

    Returns:
        Predecessor and successor publication IDs.
    """
    active = PublicationView.open(publication_root=source_publication_root)
    successor_id = active.publication_id
    predecessor_id = active.manifest["previous_publication_id"]
    if not isinstance(predecessor_id, str) or not predecessor_id:
        raise FaultMatrixError(
            code="FAULT_MATRIX_PREDECESSOR_REQUIRED",
            message="Active successor has no committed predecessor",
        )
    source_layout = publication_layout(
        publication_root=source_publication_root
    )
    predecessor_bundle = (
        Path(source_layout["publications_dir"]) / predecessor_id
    )
    verify_publication_bundle(
        bundle_dir=predecessor_bundle
    )
    # Updates require a formal predecessor, while the first Cutover must keep
    # the frozen legacy root as its rollback predecessor.  Bundle verification
    # already replays the strict legacy import marker and baseline hashes; only
    # a predecessor without that marker needs the ordinary formal PASS gate.
    if not (
        predecessor_bundle / LEGACY_BASELINE_IMPORT_MANIFEST
    ).is_file():
        _formal_validation_manifest(bundle_dir=predecessor_bundle)
    _formal_validation_manifest(bundle_dir=active.bundle_dir)
    verification_root = fault_workspace_root / "input_binding"
    verification_root.mkdir()
    reproduced_successor = prepare_publication_bundle(
        publication_root=verification_root,
        **_preparation_kwargs(
            authority_repo_root=authority_repo_root,
            preparation=successor,
            previous_publication_id=predecessor_id,
        ),
    )
    if (
        reproduced_successor["publication_id"] != successor_id
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_INPUT_BINDING_DIFFERS",
            message="Batch/staging inputs do not reproduce committed IDs",
        )
    return predecessor_id, successor_id


def _copy_file(*, source: Path, destination: Path) -> None:
    """Copy exact regular bytes without propagating filesystem metadata.

    Args:
        source: Verified source file.
        destination: New isolated destination.
    """
    if source.is_symlink() or not source.is_file():
        raise FaultMatrixError(
            code="FAULT_MATRIX_SOURCE_UNSAFE",
            message="Committed source file is absent or unsafe",
        )
    atomic_write_bytes(path=destination, content=source.read_bytes())


def _copy_switch_history(
    *, source_layout: Mapping[str, object],
    target_layout: Mapping[str, object]
) -> None:
    """Copy the complete committed switch chain with an isolated pointer.

    Args:
        source_layout: Verified source publication layout.
        target_layout: Empty isolated publication layout.
    """
    source = Path(source_layout["switch_receipts_dir"])
    target = Path(target_layout["switch_receipts_dir"])
    if source.is_symlink() or not source.is_dir() or target.exists():
        raise FaultMatrixError(
            code="FAULT_MATRIX_SWITCH_HISTORY_INVALID",
            message="Committed switch history cannot be isolated",
        )
    shutil.copytree(source, target)


def _copy_authority_lock(
    *, source_layout: Mapping[str, object],
    target_layout: Mapping[str, object],
) -> None:
    """Copy the required empty lock inode into an isolated committed view.

    Args:
        source_layout: Verified committed publication layout.
        target_layout: Isolated layout receiving the same read authority.

    Why:
        ``PublicationView`` is deliberately read-only and cannot manufacture a
        missing lock.  A fault scenario that clones pointer/history/mirrors
        must therefore clone the writer-created lock before its first read.
    """
    source_pointer = Path(source_layout["pointer_path"])
    target_pointer = Path(target_layout["pointer_path"])
    _copy_file(
        source=source_pointer.with_suffix(source_pointer.suffix + ".lock"),
        destination=target_pointer.with_suffix(
            target_pointer.suffix + ".lock"
        ),
    )


def _scenario_at_predecessor(
    *, fault_workspace_root: Path, scenario_id: str,
    source_publication_root: Path, predecessor_id: str,
    successor_id: str, executed_at_utc: str,
) -> Path:
    """Clone a committed chain and publicly roll it back to predecessor.

    Args:
        fault_workspace_root: Retained matrix root.
        scenario_id: Unique isolated scenario name.
        source_publication_root: Verified committed source chain.
        predecessor_id: Source active's committed predecessor.
        successor_id: Source active publication.
        executed_at_utc: Explicit rollback observation time.

    Returns:
        Isolated publication root with predecessor active.
    """
    scenario_root = fault_workspace_root / scenario_id.lower()
    if scenario_root.exists():
        raise FaultMatrixError(
            code="FAULT_MATRIX_SCENARIO_EXISTS",
            message="Isolated scenario path already exists",
        )
    scenario_root.mkdir()
    source_layout = publication_layout(
        publication_root=source_publication_root
    )
    target_layout = publication_layout(publication_root=scenario_root)
    target_publications = Path(target_layout["publications_dir"])
    target_publications.mkdir(parents=True)
    for publication_id in (predecessor_id, successor_id):
        source_bundle = (
            Path(source_layout["publications_dir"]) / publication_id
        )
        verify_publication_bundle(bundle_dir=source_bundle)
        shutil.copytree(
            source_bundle, target_publications / publication_id,
        )
    _copy_switch_history(
        source_layout=source_layout,
        target_layout=target_layout,
    )
    _copy_file(
        source=Path(source_layout["pointer_path"]),
        destination=Path(target_layout["pointer_path"]),
    )
    _copy_authority_lock(
        source_layout=source_layout,
        target_layout=target_layout,
    )
    source_mirrors = source_layout["mirror_paths"]
    target_mirrors = target_layout["mirror_paths"]
    for relative in source_mirrors:
        _copy_file(
            source=Path(source_mirrors[relative]),
            destination=Path(target_mirrors[relative]),
        )
    opened = PublicationView.open(publication_root=scenario_root)
    if opened.publication_id != successor_id:
        raise FaultMatrixError(
            code="FAULT_MATRIX_SOURCE_ACTIVE_DIFFERS",
            message="Cloned active pointer is not the committed successor",
        )
    rollback_publication(
        publication_root=scenario_root,
        target_publication_id=predecessor_id,
        expected_active_publication_id=successor_id,
        committed_at_utc=executed_at_utc,
    )
    if (
        PublicationView.open(
            publication_root=scenario_root
        ).publication_id != predecessor_id
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_ROLLBACK_POSTCONDITION_FAILED",
            message="Isolated rollback did not activate predecessor",
        )
    return scenario_root


def _temporary_namespace_cleaned(*, scenario_root: Path) -> bool:
    """Report whether prepare left no hidden temporary bundle directory.

    Args:
        scenario_root: Isolated publication root after the fault.

    Returns:
        ``True`` only when every publication temporary directory is absent.
    """
    publications = Path(
        publication_layout(publication_root=scenario_root)[
            "publications_dir"
        ]
    )
    return not any(
        path.name.startswith(".") and path.name.endswith(".tmp")
        for path in publications.iterdir()
    )


@contextmanager
def _injected_checkpoint(
    *, fault_point: str, process_crash: bool,
) -> Iterator[None]:
    """Install one deterministic publication checkpoint fault temporarily.

    Args:
        fault_point: Exact internal transaction checkpoint identity.
        process_crash: Whether the fault must escape normal recovery.

    Yields:
        Control to one real public publication operation.
    """
    original = publication_module._fault_injection_checkpoint

    def inject(*, fault_point: str) -> None:
        """Raise only at the configured checkpoint.

        Args:
            fault_point: Checkpoint reached by the transaction.
        """
        if fault_point != configured:
            return
        if process_crash:
            raise _SimulatedProcessCrash(configured)
        raise OSError("Injected publication fault: " + configured)

    configured = fault_point
    publication_module._fault_injection_checkpoint = inject
    try:
        yield
    finally:
        publication_module._fault_injection_checkpoint = original


def _write_receipt(
    *, receipt_publication_root: Path, scenario_id: str,
    prepared_publication_id: Optional[str], fault_point: str,
    before: Mapping[str, object], after: Mapping[str, object],
    outcome: str, scenario_root: Path,
) -> Dict[str, object]:
    """Persist one observation after checking the isolated temp namespace.

    Args:
        receipt_publication_root: Formal repository receipt destination.
        scenario_id: Explicit isolated scenario identity.
        prepared_publication_id: Exercised candidate or ``None`` pre-prepare.
        fault_point: Exact gate or transaction boundary.
        before: Verified state before the fault.
        after: Verified terminal state.
        outcome: Stable public receipt classification.
        scenario_root: Retained workspace used by this observation.

    Returns:
        Content-addressed formal fault receipt.
    """
    return write_publication_fault_receipt(
        publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=prepared_publication_id,
        fault_point=fault_point,
        before=before,
        after=after,
        outcome=outcome,
        temporary_workspace_cleaned=_temporary_namespace_cleaned(
            scenario_root=scenario_root
        ),
    )


def _mid_bundle_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    authority_repo_root: Path, fault_workspace_root: Path,
    successor: FaultMatrixPreparation, predecessor_id: str,
    successor_id: str, executed_at_utc: str,
) -> Dict[str, object]:
    """Inject a partial bundle write and prove active state is preserved."""
    scenario_id = "ISOLATED_MID_BUNDLE_WRITE"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    successor_bundle = (
        Path(publication_layout(publication_root=root)["publications_dir"])
        / successor_id
    )
    shutil.rmtree(successor_bundle)
    before = publication_state_snapshot(publication_root=root)
    try:
        with _injected_checkpoint(
            fault_point="MID_BUNDLE_WRITE", process_crash=False,
        ):
            prepare_publication_bundle(
                publication_root=root,
                **_preparation_kwargs(
                    authority_repo_root=authority_repo_root,
                    preparation=successor,
                    previous_publication_id=predecessor_id,
                ),
            )
    except PublicationError:
        pass
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_INJECTION_NOT_OBSERVED",
            message="Mid-bundle failure unexpectedly prepared a bundle",
        )
    after = publication_state_snapshot(publication_root=root)
    if before != after or successor_bundle.exists():
        raise FaultMatrixError(
            code="FAULT_MATRIX_ACTIVE_CHANGED",
            message="Mid-bundle failure changed active state",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="MID_BUNDLE_WRITE",
        before=before,
        after=after,
        outcome="ABORTED_ACTIVE_PRESERVED",
        scenario_root=root,
    )


def _mid_mirror_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    executed_at_utc: str,
) -> Dict[str, object]:
    """Inject a partial mirror write and prove full restoration."""
    scenario_id = "ISOLATED_MID_MIRROR_WRITE"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    try:
        with _injected_checkpoint(
            fault_point="MID_MIRROR_WRITE", process_crash=False,
        ):
            _commit_publication(
                publication_root=root,
                publication_id=successor_id,
                expected_active_publication_id=predecessor_id,
                committed_at_utc=executed_at_utc,
            )
    except PublicationError:
        pass
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_INJECTION_NOT_OBSERVED",
            message="Mid-mirror failure unexpectedly committed",
        )
    after = publication_state_snapshot(publication_root=root)
    if before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_ACTIVE_CHANGED",
            message="Mid-mirror failure did not restore prior bytes",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="MID_MIRROR_WRITE",
        before=before,
        after=after,
        outcome="ABORTED_ACTIVE_PRESERVED",
        scenario_root=root,
    )


def _pre_pointer_recovery_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    executed_at_utc: str,
) -> Dict[str, object]:
    """Crash after mirror writes and recover them from official pointer."""
    scenario_id = "ISOLATED_MIRRORS_BEFORE_POINTER"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    try:
        with _injected_checkpoint(
            fault_point="MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT",
            process_crash=True,
        ):
            _commit_publication(
                publication_root=root,
                publication_id=successor_id,
                expected_active_publication_id=predecessor_id,
                committed_at_utc=executed_at_utc,
            )
    except _SimulatedProcessCrash:
        pass
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_INJECTION_NOT_OBSERVED",
            message="Pre-pointer crash unexpectedly committed",
        )
    crashed = publication_state_snapshot(publication_root=root)
    if (
        crashed["active_publication_id"] != predecessor_id
        or crashed["mirror_hashes"] == before["mirror_hashes"]
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_CRASH_STATE_DIFFERS",
            message="Pre-pointer crash did not expose recoverable mirrors",
        )
    recovered = recover_publication_mirrors(publication_root=root)
    after = publication_state_snapshot(publication_root=root)
    if recovered != predecessor_id or before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RECOVERY_FAILED",
            message="Official pointer did not restore all mirrors",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT",
        before=before,
        after=after,
        outcome="RECOVERED_FROM_ACTIVE",
        scenario_root=root,
    )


def _cas_loser_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    executed_at_utc: str,
) -> Dict[str, object]:
    """Commit once, then prove a stale predecessor loses without drift."""
    scenario_id = "ISOLATED_CAS_LOSER"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    _commit_publication(
        publication_root=root,
        publication_id=successor_id,
        expected_active_publication_id=predecessor_id,
        committed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    try:
        _commit_publication(
            publication_root=root,
            publication_id=successor_id,
            expected_active_publication_id=predecessor_id,
            committed_at_utc=executed_at_utc,
        )
    except PublicationError:
        pass
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_CAS_NOT_ENFORCED",
            message="Stale CAS publisher unexpectedly committed",
        )
    after = publication_state_snapshot(publication_root=root)
    if before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_ACTIVE_CHANGED",
            message="CAS loser changed active state",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="CAS_POINTER_LOCK",
        before=before,
        after=after,
        outcome="CAS_LOST_ACTIVE_PRESERVED",
        scenario_root=root,
    )


def _concurrent_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    executed_at_utc: str,
) -> Dict[str, object]:
    """Race two real CAS commits and require exactly one winner."""
    scenario_id = "ISOLATED_CONCURRENT_PUBLISHERS"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)

    def publish() -> str:
        """Attempt one CAS commit from the same predecessor.

        Returns:
            Successor identity for the unique winner.
        """
        _commit_publication(
            publication_root=root,
            publication_id=successor_id,
            expected_active_publication_id=predecessor_id,
            committed_at_utc=executed_at_utc,
        )
        return successor_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish) for _index in range(2)]
        successes = []
        failures = []
        for future in futures:
            try:
                successes.append(future.result())
            except PublicationError as error:
                failures.append(str(error))
    if len(successes) != 1 or len(failures) != 1:
        raise FaultMatrixError(
            code="FAULT_MATRIX_CONCURRENCY_FAILED",
            message="Concurrent publishers did not produce one winner",
        )
    after = publication_state_snapshot(publication_root=root)
    if after["active_publication_id"] != successor_id:
        raise FaultMatrixError(
            code="FAULT_MATRIX_CONCURRENCY_FAILED",
            message="Concurrent winner is not the prepared successor",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="CAS_POINTER_LOCK",
        before=before,
        after=after,
        outcome="EXACTLY_ONE_WINNER",
        scenario_root=root,
    )


def _pinned_view_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    executed_at_utc: str,
) -> Dict[str, object]:
    """Keep both predecessor/successor views stable across two switches."""
    scenario_id = "ISOLATED_PINNED_VIEW_POINTER_SWITCH"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    pinned_predecessor = PublicationView.open(publication_root=root)
    predecessor_bytes = pinned_predecessor.read_bytes(
        relative_path="metrics_matrix.csv"
    )
    _commit_publication(
        publication_root=root,
        publication_id=successor_id,
        expected_active_publication_id=predecessor_id,
        committed_at_utc=executed_at_utc,
    )
    pinned_successor = PublicationView.open(publication_root=root)
    successor_bytes = pinned_successor.read_bytes(
        relative_path="metrics_matrix.csv"
    )
    rollback_publication(
        publication_root=root,
        target_publication_id=predecessor_id,
        expected_active_publication_id=successor_id,
        committed_at_utc=executed_at_utc,
    )
    if (
        pinned_predecessor.read_bytes(relative_path="metrics_matrix.csv")
        != predecessor_bytes
        or pinned_successor.read_bytes(relative_path="metrics_matrix.csv")
        != successor_bytes
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_PINNED_VIEW_CHANGED",
            message="Pinned view changed after pointer switch",
        )
    after = publication_state_snapshot(publication_root=root)
    if before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_ROLLBACK_POSTCONDITION_FAILED",
            message="Pinned-view scenario did not restore predecessor",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="POINTER_SWITCH_DURING_PINNED_READ",
        before=before,
        after=after,
        outcome="PINNED_VIEW_STABLE",
        scenario_root=root,
    )


def _mutate_withheld_candidate(*, staging_dir: Path) -> None:
    """Create one applicable WITHHELD negative from verified candidate bytes.

    Args:
        staging_dir: Isolated copy of the formally validated successor view.
    """
    projection = strict_json_file(
        path=staging_dir / "projection_manifest.json"
    )
    if not isinstance(projection, dict):
        raise FaultMatrixError(
            code="FAULT_MATRIX_WITHHELD_INPUT_INVALID",
            message="Projection manifest is not an object",
        )
    migrated_ids = set(projection["migrated_metric_ids"])
    metrics_path = staging_dir / "metrics_matrix.csv"
    with metrics_path.open(
        mode="r", encoding="utf-8", newline=""
    ) as file_obj:
        reader = csv.DictReader(file_obj)
        if tuple(reader.fieldnames or ()) != METRIC_FIELDS:
            raise FaultMatrixError(
                code="FAULT_MATRIX_WITHHELD_INPUT_INVALID",
                message="Metrics schema differs",
            )
        rows = [dict(row) for row in reader]
    candidates = [
        row for row in rows
        if row["metric_id"] in migrated_ids
        and row["value"]
        and row["status"] != "N_A_STRUCTURAL"
    ]
    if not candidates:
        raise FaultMatrixError(
            code="FAULT_MATRIX_WITHHELD_INPUT_INVALID",
            message="No applicable migrated row is available",
        )
    candidates[0]["value"] = ""
    candidates[0]["status"] = "WITHHELD"
    with metrics_path.open(
        mode="w", encoding="utf-8", newline=""
    ) as file_obj:
        writer = csv.DictWriter(
            file_obj, fieldnames=list(METRIC_FIELDS), lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _withheld_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    authority_repo_root: Path, fault_workspace_root: Path,
    successor: FaultMatrixPreparation, predecessor_id: str,
    successor_id: str, executed_at_utc: str,
) -> Dict[str, object]:
    """Send a real applicable WITHHELD candidate through the public gate."""
    scenario_id = "ISOLATED_WITHHELD_CANDIDATE"
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    staging = root / "withheld_staging"
    shutil.copytree(successor.staging_dir, staging)
    receipt_path = staging / "publication_validation_receipt.json"
    if receipt_path.exists():
        receipt_path.unlink()
    _mutate_withheld_candidate(staging_dir=staging)
    try:
        publication_staging_context(
            repo_root=authority_repo_root,
            batch_manifest_path=successor.batch_manifest_path,
            legacy_snapshot_dir=successor.legacy_snapshot_dir,
            staging_dir=staging,
        )
    except PublicationError:
        pass
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_WITHHELD_NOT_BLOCKED",
            message="Applicable WITHHELD candidate passed the public gate",
        )
    after = publication_state_snapshot(publication_root=root)
    if before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_ACTIVE_CHANGED",
            message="WITHHELD candidate changed active state",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=None,
        fault_point="PREPARE_VALIDATION_GATE",
        before=before,
        after=after,
        outcome="WITHHELD_BLOCKED",
        scenario_root=root,
    )


def _mixed_year_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    authority_repo_root: Path, fault_workspace_root: Path,
    mixed_fiscal_year_run_dirs: Sequence[Path], predecessor_id: str,
    successor_id: str, executed_at_utc: str,
) -> Dict[str, object]:
    """Submit verified different-year Runs to the public BatchManifest gate."""
    scenario_id = "ISOLATED_MIXED_FISCAL_YEAR"
    if len(mixed_fiscal_year_run_dirs) < 2:
        raise FaultMatrixError(
            code="FAULT_MATRIX_MIXED_YEAR_INPUT_REQUIRED",
            message="At least two verified mixed-year Runs are required",
        )
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    probe_root = root / "mixed_year_probe"
    probe_root.mkdir()
    copied_runs = []
    for index, source in enumerate(mixed_fiscal_year_run_dirs):
        if source.is_symlink() or not source.is_dir():
            raise FaultMatrixError(
                code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
                message="Mixed-year Run is absent or unsafe",
            )
        destination = probe_root / "run-{}".format(index)
        shutil.copytree(source, destination)
        copied_runs.append(destination)
    batch_path = probe_root / "batch_manifest.json"
    try:
        write_projection_batch_manifest(
            repo_root=authority_repo_root,
            batch_manifest_path=batch_path,
            run_dirs=copied_runs,
        )
    except ProjectionError as error:
        if "period" not in str(error).lower():
            raise FaultMatrixError(
                code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
                message="Probe failed before the mixed-period invariant",
            ) from error
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_MIXED_YEAR_NOT_BLOCKED",
            message="Mixed-fiscal-year BatchManifest unexpectedly passed",
        )
    if batch_path.exists():
        raise FaultMatrixError(
            code="FAULT_MATRIX_MIXED_YEAR_PARTIAL_WRITE",
            message="Rejected mixed-year BatchManifest was persisted",
        )
    after = publication_state_snapshot(publication_root=root)
    if before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_ACTIVE_CHANGED",
            message="Mixed-year candidate changed active state",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=None,
        fault_point="BATCH_MANIFEST_PERIOD_GATE",
        before=before,
        after=after,
        outcome="MIXED_FISCAL_YEAR_BLOCKED",
        scenario_root=root,
    )


def _first_path(*, paths: Sequence[Path], label: str) -> Path:
    """Choose the first deterministic tamper target from a complete batch.

    Args:
        paths: Candidate paths in one verified closure.
        label: Stable target type for diagnostics.

    Returns:
        First sorted unique path.
    """
    candidates = sorted(set(paths))
    if not candidates:
        raise FaultMatrixError(
            code="FAULT_MATRIX_TAMPER_TARGET_AMBIGUOUS",
            message="{} target is absent".format(label),
        )
    return candidates[0]


def _tamper_target(*, bundle_dir: Path, target_kind: str) -> Path:
    """Resolve one bundle, Run, Decision, Trace, Spec, or receipt byte target.

    Args:
        bundle_dir: Verified active successor bundle.
        target_kind: Stable target class.

    Returns:
        Exact file whose bytes are covered by Publication verification.
    """
    if target_kind == "BUNDLE":
        return bundle_dir / "metrics_matrix.csv"
    if target_kind == "RUN":
        paths = [
            path for path in (bundle_dir / "internal" / "batch").rglob(
                "manifest.json"
            )
            if path.parent.name != "batch"
        ]
        return _first_path(paths=paths, label=target_kind)
    if target_kind == "DECISION":
        return _first_path(
            paths=list(
                (bundle_dir / "internal" / "batch").rglob(
                    "review_decisions.jsonl"
                )
            ),
            label=target_kind,
        )
    if target_kind == "TRACE":
        paths = [
            path for path in (bundle_dir / "internal" / "batch").rglob(
                "records.jsonl"
            )
            if b"EXECUTION_TRACE" in path.read_bytes()
        ]
        return _first_path(paths=paths, label=target_kind)
    if target_kind == "SPEC":
        paths = list(
            (
                bundle_dir
                / "internal"
                / "authority"
                / "catalog"
                / "metrics"
            ).glob("*.md")
        )
        if not paths:
            raise FaultMatrixError(
                code="FAULT_MATRIX_TAMPER_TARGET_AMBIGUOUS",
                message="SPEC target is absent",
            )
        return sorted(paths)[0]
    if target_kind == "RECEIPT":
        return _first_path(
            paths=list(
                (bundle_dir / "internal" / "batch").rglob(
                    "validation.json"
                )
            ),
            label=target_kind,
        )
    raise FaultMatrixError(
        code="FAULT_MATRIX_TAMPER_TARGET_INVALID",
        message="Unknown tamper target kind",
    )


def _tamper_receipt(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    executed_at_utc: str, target_kind: str,
) -> Dict[str, object]:
    """Change one bound byte, require read-back failure, then restore it."""
    scenario_id = "ISOLATED_{}_TAMPER".format(
        "ACTIVE_BUNDLE" if target_kind == "BUNDLE" else target_kind
    )
    root = _scenario_at_predecessor(
        fault_workspace_root=fault_workspace_root,
        scenario_id=scenario_id,
        source_publication_root=source_publication_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        executed_at_utc=executed_at_utc,
    )
    _commit_publication(
        publication_root=root,
        publication_id=successor_id,
        expected_active_publication_id=predecessor_id,
        committed_at_utc=executed_at_utc,
    )
    before = publication_state_snapshot(publication_root=root)
    bundle_dir = (
        Path(publication_layout(publication_root=root)["publications_dir"])
        / successor_id
    )
    target = _tamper_target(
        bundle_dir=bundle_dir, target_kind=target_kind
    )
    original = target.read_bytes()
    target.write_bytes(original + b"\nFAULT_MATRIX_TAMPER\n")
    try:
        if target_kind == "BUNDLE":
            PublicationView.open(publication_root=root)
        else:
            verify_publication_bundle(bundle_dir=bundle_dir)
    except PublicationError:
        pass
    else:
        raise FaultMatrixError(
            code="FAULT_MATRIX_TAMPER_NOT_REJECTED",
            message="{} tamper passed read-back".format(target_kind),
        )
    finally:
        atomic_write_bytes(path=target, content=original)
    verify_publication_bundle(bundle_dir=bundle_dir)
    after = publication_state_snapshot(publication_root=root)
    if before != after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_ACTIVE_CHANGED",
            message="Tamper scenario changed restored active state",
        )
    return _write_receipt(
        receipt_publication_root=receipt_publication_root,
        scenario_id=scenario_id,
        prepared_publication_id=successor_id,
        fault_point="{}_READ_BACK".format(target_kind),
        before=before,
        after=after,
        outcome="TAMPER_REJECTED",
        scenario_root=root,
    )


def _write_workspace_manifest(
    *, fault_workspace_root: Path, predecessor_id: str, successor_id: str,
    receipts: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Index retained isolated scenarios without persisting host paths.

    Args:
        fault_workspace_root: Persistent scenario root.
        predecessor_id: Verified committed predecessor.
        successor_id: Verified committed successor.
        receipts: Ordered formal fault receipts.

    Returns:
        Content-addressed workspace manifest.
    """
    body = {
        "schema_version": 1,
        "execution_scope": "ISOLATED_PERSISTENT_FAULT_WORKSPACE",
        "predecessor_publication_id": predecessor_id,
        "successor_publication_id": successor_id,
        "scenario_ids": sorted(
            str(receipt["scenario_id"]) for receipt in receipts
        ),
        "fault_receipt_ids": sorted(
            str(receipt["fault_receipt_id"]) for receipt in receipts
        ),
        "temporary_namespaces_cleaned": all(
            receipt["temporary_workspace_cleaned"] is True
            for receipt in receipts
        ),
    }
    manifest = {**body, "fault_matrix_id": content_hash(value=body)}
    atomic_write_json(
        path=fault_workspace_root / "fault_matrix_manifest.json",
        value=manifest,
    )
    return manifest


def _receipt_references(
    *, receipts: Sequence[Mapping[str, object]],
) -> list[Dict[str, object]]:
    """Build stable repository-relative references for persisted receipts.

    Args:
        receipts: Verified content-addressed fault receipts.

    Returns:
        Scenario, receipt identity, and formal repository-relative path rows.
    """
    ordered = sorted(
        receipts, key=lambda item: str(item["scenario_id"])
    )
    return [
        {
            "scenario_id": receipt["scenario_id"],
            "fault_receipt_id": receipt["fault_receipt_id"],
            "fault_receipt_path": (
                "outputs/publication_fault_receipts/{}.json".format(
                    str(receipt["fault_receipt_id"]).split(
                        ":", maxsplit=1
                    )[1]
                )
            ),
        }
        for receipt in ordered
    ]


def _matrix_result(
    *, manifest: Mapping[str, object],
    receipts: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Return the common fresh/resumed result envelope.

    Args:
        manifest: Verified persistent workspace manifest.
        receipts: Verified fault receipts in any order.

    Returns:
        PASSED matrix identity and exact receipt references.
    """
    ordered = sorted(
        (dict(receipt) for receipt in receipts),
        key=lambda receipt: str(receipt["scenario_id"]),
    )
    return {
        "status": "PASSED",
        "fault_matrix_id": manifest["fault_matrix_id"],
        "predecessor_publication_id": manifest[
            "predecessor_publication_id"
        ],
        "successor_publication_id": manifest[
            "successor_publication_id"
        ],
        "fault_receipts": ordered,
        "fault_receipt_references": _receipt_references(
            receipts=ordered
        ),
        "workspace_manifest": dict(manifest),
    }


def _bundle_mirror_hashes(
    *, manifest: Mapping[str, object],
) -> Dict[str, object]:
    """Derive the exact root-mirror digest map from one verified bundle.

    Args:
        manifest: PublicationManifest returned by bundle verification.

    Returns:
        One digest for every formal root compatibility mirror.
    """
    hashes = {}
    for record in manifest["files"]:
        relative = str(record["path"])
        if relative in REQUIRED_BUNDLE_FILES:
            hashes[relative] = record["sha256"]
    if set(hashes) != REQUIRED_BUNDLE_FILES:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_BUNDLE_INVALID",
            message="Source bundle root-mirror exact set differs",
        )
    return hashes


def _validate_resumed_fault_receipt(
    *, receipt_publication_root: Path, fault_workspace_root: Path,
    receipt_id: str, predecessor_id: str, successor_id: str,
    predecessor_mirror_hashes: Mapping[str, object],
    successor_mirror_hashes: Mapping[str, object],
) -> Dict[str, object]:
    """Recompute one persisted receipt and its retained terminal state.

    Args:
        receipt_publication_root: Formal root containing durable receipts.
        fault_workspace_root: Retained isolated scenario parent.
        receipt_id: Content identity declared by the matrix manifest.
        predecessor_id: Matrix source predecessor identity.
        successor_id: Matrix source successor identity.
        predecessor_mirror_hashes: Verified predecessor bundle mirror map.
        successor_mirror_hashes: Verified successor bundle mirror map.

    Returns:
        Strict receipt mapping.
    """
    if (
        type(receipt_id) is not str
        or not receipt_id.startswith("sha256:")
        or len(receipt_id) != 71
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_RECEIPT_INVALID",
            message="Fault receipt identity is invalid",
        )
    digest = receipt_id.split(":", maxsplit=1)[1]
    path = (
        receipt_publication_root
        / "outputs"
        / "publication_fault_receipts"
        / (digest + ".json")
    )
    try:
        payload = strict_json_file(path=path)
    except (CanonicalError, OSError) as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_RECEIPT_INVALID",
            message="Fault receipt bytes are absent or invalid",
        ) from error
    if not isinstance(payload, dict) or set(payload) != _FAULT_RECEIPT_FIELDS:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_RECEIPT_INVALID",
            message="Fault receipt fields are not exact",
        )
    receipt = dict(payload)
    body = {
        field: receipt[field]
        for field in receipt
        if field != "fault_receipt_id"
    }
    if (
        receipt["schema_version"] != 1
        or receipt["fault_receipt_id"] != receipt_id
        or content_hash(value=body) != receipt_id
        or receipt["temporary_workspace_cleaned"] is not True
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_RECEIPT_INVALID",
            message="Fault receipt identity or cleanup result differs",
        )
    scenario_id = str(receipt["scenario_id"])
    if scenario_id not in _SCENARIO_EXPECTATIONS:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_EXACT_SET_DIFFERS",
            message="Fault receipt scenario is unknown",
        )
    fault_point, outcome, prepared, terminal_role = (
        _SCENARIO_EXPECTATIONS[scenario_id]
    )
    terminal_id = (
        successor_id if terminal_role == "SUCCESSOR" else predecessor_id
    )
    active_before_id = (
        predecessor_id
        if scenario_id == "ISOLATED_CONCURRENT_PUBLISHERS"
        else terminal_id
    )
    before_hashes = (
        predecessor_mirror_hashes
        if active_before_id == predecessor_id
        else successor_mirror_hashes
    )
    after_hashes = (
        predecessor_mirror_hashes
        if terminal_id == predecessor_id
        else successor_mirror_hashes
    )
    if (
        receipt["fault_point"] != fault_point
        or receipt["outcome"] != outcome
        or receipt["prepared_publication_id"]
        != (successor_id if prepared else None)
        or receipt["active_before"] != active_before_id
        or receipt["active_after"] != terminal_id
        or receipt["mirror_hashes_before"] != before_hashes
        or receipt["mirror_hashes_after"] != after_hashes
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_RECEIPT_INVALID",
            message="Fault receipt scenario semantics differ",
        )
    scenario_root = fault_workspace_root / scenario_id.lower()
    if not scenario_root.is_dir() or scenario_root.is_symlink():
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_WORKSPACE_INVALID",
            message="Retained scenario workspace is absent or unsafe",
        )
    state = publication_state_snapshot(publication_root=scenario_root)
    if (
        state["active_publication_id"] != receipt["active_after"]
        or state["mirror_hashes"] != receipt["mirror_hashes_after"]
        or not _temporary_namespace_cleaned(scenario_root=scenario_root)
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_STATE_DIFFERS",
            message="Retained scenario terminal state differs",
        )
    return receipt


def resume_formal_publication_fault_matrix(
    *, receipt_publication_root: Path, source_publication_root: Path,
    fault_workspace_root: Path,
) -> Dict[str, object]:
    """Revalidate and reuse one completed persistent fault matrix.

    Args:
        receipt_publication_root: Formal root containing durable receipts.
        source_publication_root: Formal active pointer and immutable bundles.
        fault_workspace_root: Existing retained scenario workspace.

    Returns:
        Same result envelope as a fresh successful matrix execution.
    """
    manifest_path = fault_workspace_root / "fault_matrix_manifest.json"
    try:
        payload = strict_json_file(path=manifest_path)
    except (CanonicalError, OSError) as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_MANIFEST_INVALID",
            message="Fault matrix manifest is absent or invalid",
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != _FAULT_MATRIX_MANIFEST_FIELDS
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_MANIFEST_INVALID",
            message="Fault matrix manifest fields are not exact",
        )
    manifest = dict(payload)
    body = {
        field: manifest[field]
        for field in manifest
        if field != "fault_matrix_id"
    }
    if (
        manifest["schema_version"] != 1
        or manifest["execution_scope"]
        != "ISOLATED_PERSISTENT_FAULT_WORKSPACE"
        or manifest["fault_matrix_id"] != content_hash(value=body)
        or manifest["temporary_namespaces_cleaned"] is not True
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_MANIFEST_INVALID",
            message="Fault matrix manifest identity differs",
        )
    scenario_ids = manifest["scenario_ids"]
    receipt_ids = manifest["fault_receipt_ids"]
    predecessor_id = manifest["predecessor_publication_id"]
    successor_id = manifest["successor_publication_id"]
    if (
        type(predecessor_id) is not str
        or type(successor_id) is not str
        or type(scenario_ids) is not list
        or scenario_ids != sorted(FAULT_MATRIX_SCENARIO_IDS)
        or type(receipt_ids) is not list
        or len(receipt_ids) != len(FAULT_MATRIX_SCENARIO_IDS)
        or receipt_ids != sorted(set(receipt_ids))
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_EXACT_SET_DIFFERS",
            message="Fault matrix scenario or receipt exact set differs",
        )
    active = PublicationView.open(
        publication_root=source_publication_root
    )
    if (
        active.publication_id != successor_id
        or active.manifest["previous_publication_id"] != predecessor_id
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_ACTIVE_DIFFERS",
            message="Formal active publication differs from matrix source",
        )
    source_layout = publication_layout(
        publication_root=source_publication_root
    )
    predecessor_manifest = verify_publication_bundle(
        bundle_dir=(
            Path(source_layout["publications_dir"]) / str(predecessor_id)
        )
    )
    predecessor_hashes = _bundle_mirror_hashes(
        manifest=predecessor_manifest
    )
    successor_hashes = _bundle_mirror_hashes(manifest=active.manifest)
    source_state = publication_state_snapshot(
        publication_root=source_publication_root
    )
    if (
        source_state["active_publication_id"] != successor_id
        or source_state["mirror_hashes"] != successor_hashes
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_ACTIVE_DIFFERS",
            message="Formal active successor mirrors differ",
        )
    receipts = [
        _validate_resumed_fault_receipt(
            receipt_publication_root=receipt_publication_root,
            fault_workspace_root=fault_workspace_root,
            receipt_id=str(receipt_id),
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            predecessor_mirror_hashes=predecessor_hashes,
            successor_mirror_hashes=successor_hashes,
        )
        for receipt_id in receipt_ids
    ]
    if {
        str(receipt["scenario_id"]) for receipt in receipts
    } != FAULT_MATRIX_SCENARIO_IDS:
        raise FaultMatrixError(
            code="FAULT_MATRIX_RESUME_EXACT_SET_DIFFERS",
            message="Fault receipt scenario exact set differs",
        )
    return _matrix_result(manifest=manifest, receipts=receipts)


def run_formal_publication_fault_matrix(
    *, receipt_publication_root: Path, source_publication_root: Path,
    authority_repo_root: Path, fault_workspace_root: Path,
    successor: FaultMatrixPreparation,
    mixed_fiscal_year_run_dirs: Sequence[Path],
    executed_at_utc: str,
) -> Dict[str, object]:
    """Execute and persist the complete formal publication failure matrix.

    Args:
        receipt_publication_root: Formal repository that owns durable receipts.
        source_publication_root: Root with committed predecessor and successor.
        authority_repo_root: One fixed Requirement/Run/Spec repository root.
        fault_workspace_root: New retained isolated scenario workspace.
        successor: Reproducible successor Batch/staging inputs.
        mixed_fiscal_year_run_dirs: Valid FROZEN Runs that differ by period.
        executed_at_utc: Explicit UTC timestamp for isolated transitions.

    Returns:
        PASSED matrix identity, committed source IDs, and persisted receipts.

    Raises:
        FaultMatrixError: When an input is not formal or any negative does not
            fail closed with the required terminal state.
    """
    _validate_execution_time(executed_at_utc=executed_at_utc)
    _validate_workspace(fault_workspace_root=fault_workspace_root)
    predecessor_id, successor_id = _verify_committed_inputs(
        source_publication_root=source_publication_root,
        authority_repo_root=authority_repo_root,
        fault_workspace_root=fault_workspace_root,
        successor=successor,
    )
    source_active_before = PublicationView.open(
        publication_root=source_publication_root
    ).publication_id
    receipts = [
        _mid_bundle_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            authority_repo_root=authority_repo_root,
            fault_workspace_root=fault_workspace_root,
            successor=successor,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _mid_mirror_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            fault_workspace_root=fault_workspace_root,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _pre_pointer_recovery_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            fault_workspace_root=fault_workspace_root,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _cas_loser_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            fault_workspace_root=fault_workspace_root,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _concurrent_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            fault_workspace_root=fault_workspace_root,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _pinned_view_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            fault_workspace_root=fault_workspace_root,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _withheld_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            authority_repo_root=authority_repo_root,
            fault_workspace_root=fault_workspace_root,
            successor=successor,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
        _mixed_year_receipt(
            receipt_publication_root=receipt_publication_root,
            source_publication_root=source_publication_root,
            authority_repo_root=authority_repo_root,
            fault_workspace_root=fault_workspace_root,
            mixed_fiscal_year_run_dirs=mixed_fiscal_year_run_dirs,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            executed_at_utc=executed_at_utc,
        ),
    ]
    for target_kind in (
        "BUNDLE", "RUN", "DECISION", "TRACE", "SPEC", "RECEIPT",
    ):
        receipts.append(
            _tamper_receipt(
                receipt_publication_root=receipt_publication_root,
                source_publication_root=source_publication_root,
                fault_workspace_root=fault_workspace_root,
                predecessor_id=predecessor_id,
                successor_id=successor_id,
                executed_at_utc=executed_at_utc,
                target_kind=target_kind,
            )
        )
    source_active_after = PublicationView.open(
        publication_root=source_publication_root
    ).publication_id
    if (
        source_active_before != successor_id
        or source_active_after != successor_id
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_FORMAL_ACTIVE_CHANGED",
            message="Isolated matrix changed the formal active pointer",
        )
    manifest = _write_workspace_manifest(
        fault_workspace_root=fault_workspace_root,
        predecessor_id=predecessor_id,
        successor_id=successor_id,
        receipts=receipts,
    )
    return _matrix_result(manifest=manifest, receipts=receipts)


def _require_repository_descendant(
    *, repo_root: Path, path: Path, label: str,
) -> Path:
    """Require one real path below the fixed formal repository.

    Args:
        repo_root: Module-owned formal repository root.
        path: Caller workflow path already chosen by ``run_cutover``.
        label: Stable diagnostic role.

    Returns:
        Resolved repository-contained path.
    """
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root.resolve(strict=True))
    except ValueError as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_PATH_OUTSIDE_REPOSITORY",
            message="{} must remain below repository authority".format(
                label
            ),
        ) from error
    return resolved


def _shift_period_year(
    *, target_period: Mapping[str, object], year_delta: int,
) -> Dict[str, object]:
    """Shift one structural-only annual period without business inference.

    Args:
        target_period: Verified Run fiscal year and ISO date boundaries.
        year_delta: Non-zero year offset used only for the negative probe.

    Returns:
        Distinct syntactically valid target period.
    """
    if type(year_delta) is not int or year_delta == 0:
        raise FaultMatrixError(
            code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
            message="Mixed-year offset must be a non-zero integer",
        )
    try:
        period_start = date.fromisoformat(str(target_period["period_start"]))
        period_end = date.fromisoformat(str(target_period["period_end"]))
        fiscal_year = int(target_period["fiscal_year"])
    except (KeyError, TypeError, ValueError) as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
            message="Source Run target period is invalid",
        ) from error

    def shifted(*, value: date) -> date:
        """Move one date to the probe year, clamping leap day only.

        Args:
            value: Valid source period boundary.

        Returns:
            Same month/day in the target year, or February 28 for leap day.
        """
        try:
            return value.replace(year=value.year + year_delta)
        except ValueError:
            if value.month != 2 or value.day != 29:
                raise FaultMatrixError(
                    code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
                    message="Period boundary cannot shift by one year",
                )
            return value.replace(
                year=value.year + year_delta, day=28,
            )

    return {
        "fiscal_year": fiscal_year + year_delta,
        "period_start": shifted(value=period_start).isoformat(),
        "period_end": shifted(value=period_end).isoformat(),
    }


def _derive_mixed_fiscal_year_run_dirs(
    *, repo_root: Path, cutover_workspace_dir: Path,
) -> tuple[Path, Path]:
    """Create a valid different-year structural Run from Batch authority.

    Args:
        repo_root: Fixed repository containing registry, Specs, and traits.
        cutover_workspace_dir: Completed workspace with the formal Batch.

    Returns:
        Original and shifted FROZEN Run paths for one same-company negative.
    """
    batch_path = cutover_workspace_dir / "batch_manifest.json"
    try:
        batch = load_projection_batch_manifest(
            repo_root=repo_root, batch_manifest_path=batch_path,
        )
    except ProjectionError as error:
        raise FaultMatrixError(
            code="FAULT_MATRIX_BATCH_INPUT_INVALID",
            message="Cutover BatchManifest cannot be verified",
        ) from error
    candidates = []
    for binding in batch["runs"]:
        run_dir = batch_path.parent / str(binding["run_path"])
        try:
            manifest, records, _decisions = load_run_for_status(
                run_dir=run_dir, repo_root=repo_root,
            )
        except RunStoreError as error:
            raise FaultMatrixError(
                code="FAULT_MATRIX_BATCH_INPUT_INVALID",
                message="Cutover Run cannot be verified",
            ) from error
        results = [
            record for record in records
            if record["record_type"] == "METRIC_RESULT"
        ]
        if results and all(
            result["applicability"] == "N_A_STRUCTURAL"
            for result in results
        ):
            candidates.append((str(manifest["company_id"]), run_dir, manifest))
    if not candidates:
        raise FaultMatrixError(
            code="FAULT_MATRIX_STRUCTURAL_PROBE_REQUIRED",
            message="Batch has no all-structural Run for mixed-year probe",
        )
    company_id, original_run, manifest = sorted(
        candidates, key=lambda item: (item[0], item[1].as_posix())
    )[0]
    probe_root = cutover_workspace_dir / "fault_matrix_inputs"
    probe_root.mkdir(exist_ok=True)
    shifted_run = probe_root / "mixed_fiscal_year_structural_run"
    shifted_period = _shift_period_year(
        target_period=manifest["target_period"], year_delta=1,
    )
    if shifted_run.exists():
        try:
            shifted_manifest, _records, _decisions = load_run_for_status(
                run_dir=shifted_run, repo_root=repo_root,
            )
        except RunStoreError as error:
            raise FaultMatrixError(
                code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
                message="Existing mixed-year Run is invalid",
            ) from error
        if (
            shifted_manifest["status"] != "FROZEN"
            or shifted_manifest["company_id"] != company_id
            or shifted_manifest["target_period"] != shifted_period
        ):
            raise FaultMatrixError(
                code="FAULT_MATRIX_MIXED_YEAR_INPUT_INVALID",
                message="Existing mixed-year Run identity differs",
            )
    else:
        create_structural_release_run(
            repo_root=repo_root,
            run_dir=shifted_run,
            run_id=(
                "run:fault-matrix:mixed-fiscal-year:" + company_id
            ),
            company_id=company_id,
            target_period=shifted_period,
        )
        validate_and_freeze_run(
            run_dir=shifted_run, repo_root=repo_root,
        )
    return original_run, shifted_run


def _copy_prepared_bundle(
    *, official_publications_dir: Path, isolated_publications_dir: Path,
    publication_id: str,
) -> Mapping[str, object]:
    """Copy one verified prepared bundle into precommit isolation.

    Args:
        official_publications_dir: Formal immutable bundle storage.
        isolated_publications_dir: Dedicated fault-source bundle storage.
        publication_id: Existing prepared publication identity.

    Returns:
        Verified PublicationManifest.
    """
    source = official_publications_dir / publication_id
    manifest = verify_publication_bundle(bundle_dir=source)
    destination = isolated_publications_dir / publication_id
    if destination.exists():
        existing = verify_publication_bundle(bundle_dir=destination)
        if existing != manifest:
            raise FaultMatrixError(
                code="FAULT_MATRIX_SOURCE_BUNDLE_DIFFERS",
                message="Isolated prepared bundle bytes differ",
            )
    else:
        shutil.copytree(source, destination)
    return manifest


def _initialize_precommit_source(
    *, official_publication_root: Path, isolated_source_root: Path,
    prepared_successor_publication_id: str, executed_at_utc: str,
) -> tuple[str, str]:
    """Build an isolated committed chain before official pointer mutation.

    Args:
        official_publication_root: Formal storage containing prepared bundles.
        isolated_source_root: Fixed retained Cutover subdirectory.
        prepared_successor_publication_id: Final prepared candidate identity.
        executed_at_utc: Explicit UTC commit observation time.

    Returns:
        Isolated predecessor and active successor identities.
    """
    if isolated_source_root.exists() and any(
        isolated_source_root.iterdir()
    ):
        active = PublicationView.open(
            publication_root=isolated_source_root
        )
        if active.publication_id != prepared_successor_publication_id:
            raise FaultMatrixError(
                code="FAULT_MATRIX_SOURCE_ACTIVE_DIFFERS",
                message="Retained precommit source active identity differs",
            )
        predecessor_id = active.manifest["previous_publication_id"]
        if not isinstance(predecessor_id, str) or not predecessor_id:
            raise FaultMatrixError(
                code="FAULT_MATRIX_PREDECESSOR_REQUIRED",
                message="Retained precommit source lacks predecessor",
            )
        return predecessor_id, active.publication_id
    isolated_source_root.mkdir(parents=True, exist_ok=True)
    official_layout = publication_layout(
        publication_root=official_publication_root
    )
    isolated_layout = publication_layout(
        publication_root=isolated_source_root
    )
    official_publications = Path(official_layout["publications_dir"])
    isolated_publications = Path(isolated_layout["publications_dir"])
    isolated_publications.mkdir(parents=True)
    successor_manifest = _copy_prepared_bundle(
        official_publications_dir=official_publications,
        isolated_publications_dir=isolated_publications,
        publication_id=prepared_successor_publication_id,
    )
    official_state = publication_state_snapshot(
        publication_root=official_publication_root
    )
    official_active = official_state["active_publication_id"]
    if official_active is not None:
        predecessor_id = str(official_active)
        if successor_manifest["previous_publication_id"] != predecessor_id:
            raise FaultMatrixError(
                code="FAULT_MATRIX_PREPARED_PREDECESSOR_DIFFERS",
                message="Prepared successor does not bind official active",
            )
        _copy_prepared_bundle(
            official_publications_dir=official_publications,
            isolated_publications_dir=isolated_publications,
            publication_id=predecessor_id,
        )
        _copy_file(
            source=Path(official_layout["pointer_path"]),
            destination=Path(isolated_layout["pointer_path"]),
        )
        _copy_switch_history(
            source_layout=official_layout,
            target_layout=isolated_layout,
        )
        _copy_authority_lock(
            source_layout=official_layout,
            target_layout=isolated_layout,
        )
        for relative in official_layout["mirror_paths"]:
            _copy_file(
                source=Path(official_layout["mirror_paths"][relative]),
                destination=Path(isolated_layout["mirror_paths"][relative]),
            )
        if (
            PublicationView.open(
                publication_root=isolated_source_root
            ).publication_id != predecessor_id
        ):
            raise FaultMatrixError(
                code="FAULT_MATRIX_SOURCE_ACTIVE_DIFFERS",
                message="Isolated official predecessor differs",
            )
        _commit_publication(
            publication_root=isolated_source_root,
            publication_id=prepared_successor_publication_id,
            expected_active_publication_id=predecessor_id,
            committed_at_utc=executed_at_utc,
        )
    else:
        predecessor = successor_manifest["previous_publication_id"]
        if not isinstance(predecessor, str) or not predecessor:
            raise FaultMatrixError(
                code="FAULT_MATRIX_BOOTSTRAP_REQUIRED",
                message="First Cutover requires prepared bootstrap A before B",
            )
        predecessor_id = predecessor
        bootstrap = _copy_prepared_bundle(
            official_publications_dir=official_publications,
            isolated_publications_dir=isolated_publications,
            publication_id=predecessor_id,
        )
        if bootstrap["previous_publication_id"] is not None:
            raise FaultMatrixError(
                code="FAULT_MATRIX_BOOTSTRAP_PREDECESSOR_INVALID",
                message="Prepared bootstrap A must be first publication",
            )
        # A first Cutover imports the current root as an opaque legacy
        # predecessor.  Only the dedicated single-lock chain transition may
        # activate that non-formal bundle; ordinary forward commit must keep
        # rejecting it so recorded or imported bytes cannot become active by
        # calling the generic primitive directly.
        _commit_initial_publication_chain(
            publication_root=isolated_source_root,
            legacy_predecessor_publication_id=predecessor_id,
            successor_publication_id=prepared_successor_publication_id,
            committed_at_utc=executed_at_utc,
        )
    active = PublicationView.open(publication_root=isolated_source_root)
    if active.publication_id != prepared_successor_publication_id:
        raise FaultMatrixError(
            code="FAULT_MATRIX_SOURCE_ACTIVE_DIFFERS",
            message="Isolated chain did not commit prepared successor",
        )
    return predecessor_id, active.publication_id


def run_cutover_publication_fault_matrix(
    *, repo_root: Path, cutover_workspace_dir: Path,
    legacy_snapshot_dir: Path, prepared_successor_publication_id: str,
    executed_at_utc: str,
) -> Dict[str, object]:
    """Run the matrix before changing the official active pointer.

    Args:
        repo_root: Must equal the module-owned repository authority.
        cutover_workspace_dir: Completed Cutover workspace containing the
            current successor BatchManifest and staging candidate.
        legacy_snapshot_dir: Cutover's pinned compatibility input directory.
        prepared_successor_publication_id: Final prepared B identity already
            stored in formal immutable bundle storage.
        executed_at_utc: Explicit UTC observation timestamp.

    Returns:
        Matrix result with content-addressed receipt IDs and repository-
        relative receipt paths.
    """
    expected_workspace = _REPOSITORY_ROOT / "artifacts/vnext/cutover"
    expected_legacy = _REPOSITORY_ROOT / "outputs"
    if (
        repo_root != _REPOSITORY_ROOT
        or cutover_workspace_dir != expected_workspace
        or legacy_snapshot_dir != expected_legacy
        or any(path.is_symlink() for path in (
            repo_root, cutover_workspace_dir, legacy_snapshot_dir,
        ))
    ):
        raise FaultMatrixError(
            code="FAULT_MATRIX_AUTHORITY_ROOT_MISMATCH",
            message="Formal matrix requires the fixed Cutover authority",
        )
    workspace = _require_repository_descendant(
        repo_root=repo_root,
        path=cutover_workspace_dir,
        label="Cutover workspace",
    )
    legacy = _require_repository_descendant(
        repo_root=repo_root,
        path=legacy_snapshot_dir,
        label="Legacy snapshot",
    )
    fault_workspace = workspace / "publication_fault_matrix"
    isolated_source = workspace / "fault_matrix_source"
    if fault_workspace.exists() and any(fault_workspace.iterdir()):
        resumed = resume_formal_publication_fault_matrix(
            receipt_publication_root=repo_root,
            source_publication_root=isolated_source,
            fault_workspace_root=fault_workspace,
        )
        if (
            resumed["successor_publication_id"]
            != prepared_successor_publication_id
        ):
            raise FaultMatrixError(
                code="FAULT_MATRIX_RESUME_ACTIVE_DIFFERS",
                message="Resumed matrix successor differs from prepared B",
            )
        return resumed
    official_before = publication_state_snapshot(publication_root=repo_root)
    _initialize_precommit_source(
        official_publication_root=repo_root,
        isolated_source_root=isolated_source,
        prepared_successor_publication_id=(
            prepared_successor_publication_id
        ),
        executed_at_utc=executed_at_utc,
    )
    mixed_runs = _derive_mixed_fiscal_year_run_dirs(
        repo_root=repo_root, cutover_workspace_dir=workspace,
    )
    result = run_formal_publication_fault_matrix(
        receipt_publication_root=repo_root,
        source_publication_root=isolated_source,
        authority_repo_root=repo_root,
        fault_workspace_root=fault_workspace,
        successor=FaultMatrixPreparation(
            batch_manifest_path=workspace / "batch_manifest.json",
            legacy_snapshot_dir=legacy,
            staging_dir=workspace / "staging",
        ),
        mixed_fiscal_year_run_dirs=mixed_runs,
        executed_at_utc=executed_at_utc,
    )
    official_after = publication_state_snapshot(publication_root=repo_root)
    if official_before != official_after:
        raise FaultMatrixError(
            code="FAULT_MATRIX_OFFICIAL_STATE_CHANGED",
            message="Precommit matrix changed official pointer or mirrors",
        )
    return result
