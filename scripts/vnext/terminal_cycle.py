"""Run every formal terminal consumer through one pinned publication view.

The public CLI pins one :class:`ValidationPublicationTransaction`, then calls
this module to execute the Stage 10 Golden check, Stage 11 report read-back,
Stage 12 publication validation, snapshot publication, and snapshot checker.
No step reopens the active pointer, calls AI/SEC, repairs data, or rewrites an
authoritative root mirror.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Mapping

from validation_provenance import PROVENANCE_RELATIVE_PATH
from validation_provenance import ValidationProvenanceError
from validation_provenance import ValidationPublicationTransaction
from validation_provenance import capture_source_snapshot
from validation_provenance import invalidate_validation_snapshot
from validation_provenance import pin_validation_publication_transaction
from validation_provenance import publish_validation_snapshot
from validation_provenance import validate_validation_publication_transaction
from validation_provenance import verify_validation_snapshot

from .canonical import content_hash, sha256_bytes, sha256_file
from .publication import ROOT_MIRROR_RELATIVE_PATHS
from .report import read_validated_report, validate_active_publication
from .report import validate_golden_results


ACTIVE_POINTER_RELATIVE_PATH = Path("outputs/active_publication.json")
TERMINAL_GATE_IDS = (
    "STAGE_10_GOLDEN",
    "STAGE_11_REPORT",
    "STAGE_12_PUBLICATION",
    "SNAPSHOT_PUBLISH",
    "SNAPSHOT_VERIFY",
)


class TerminalCycleError(RuntimeError):
    """Report an incomplete or cross-publication terminal validation cycle."""


def _required_regular_file(*, root: Path, relative: Path) -> Path:
    """Resolve one repository-owned regular file without following aliases.

    Args:
        root: Formal publication root.
        relative: Required repository-relative file locator.

    Returns:
        Existing non-symlink regular file below ``root``.

    Raises:
        TerminalCycleError: The locator escapes or is not a safe regular file.
    """
    if relative.is_absolute() or ".." in relative.parts:
        raise TerminalCycleError("Terminal authority path escapes root")
    path = root / relative
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise TerminalCycleError(
                "Terminal authority path contains a symlink"
            )
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise TerminalCycleError(
            "Terminal authority path is unavailable"
        ) from error
    if not path.is_file():
        raise TerminalCycleError(
            "Terminal authority path is not a regular file"
        )
    return path


def _authoritative_hashes(
    *, publication_root: Path,
    transaction: ValidationPublicationTransaction,
) -> Dict[str, str]:
    """Hash the pointer and every user-visible compatibility mirror.

    Args:
        publication_root: Formal publication and root-mirror authority.
        transaction: Single pinned authority for the whole terminal cycle.

    Returns:
        Repository-relative pointer/mirror paths mapped to exact SHA-256.
    """
    validate_validation_publication_transaction(
        workdir=publication_root,
        transaction=transaction,
    )
    relative_paths = {
        ACTIVE_POINTER_RELATIVE_PATH,
        *(Path(value) for value in ROOT_MIRROR_RELATIVE_PATHS.values()),
    }
    return {
        relative.as_posix(): sha256_file(
            path=_required_regular_file(
                root=publication_root,
                relative=relative,
            )
        )
        for relative in sorted(
            relative_paths,
            key=lambda value: value.as_posix(),
        )
    }


def _passed_gate(*, gate_id: str, details: Mapping[str, object]) -> dict:
    """Build one exact successful terminal gate record.

    Args:
        gate_id: Stable member of :data:`TERMINAL_GATE_IDS`.
        details: Gate-specific byte or count binding.

    Returns:
        Serializable gate record with a real ``PASSED`` outcome.
    """
    if gate_id not in TERMINAL_GATE_IDS:
        raise TerminalCycleError("Terminal gate identity is invalid")
    return {
        "gate_id": gate_id,
        "outcome": "PASSED",
        "details": dict(details),
    }


def execute_terminal_publication_cycle(
    *, publication_root: Path,
    expected_publication_id: str,
) -> Dict[str, object]:
    """Execute one formal terminal cycle without reopening active authority.

    Args:
        publication_root: Repository root owning pointer, bundles, and mirrors.
        expected_publication_id: Exact publication selected by the preceding
            Cutover, rollback, or restore transaction.

    Returns:
        Content-addressed result binding pointer bytes, the pinned publication,
        all five gate results, root-authority hashes, and snapshot bytes.

    Raises:
        TerminalCycleError: The expected publication is absent, any gate fails,
            root bytes change, or snapshot verification reports an error.
        ValidationProvenanceError: Source or pointer authority is invalid.
    """
    if not expected_publication_id:
        raise TerminalCycleError("Expected publication identity is required")

    # A prior proof cannot survive a new terminal cycle.  This is the only
    # pre-pin write and it is neither a root mirror nor a publication bundle.
    invalidate_validation_snapshot(workdir=publication_root)
    source_snapshot = capture_source_snapshot(workdir=publication_root)
    transaction = pin_validation_publication_transaction(
        workdir=publication_root
    )
    view = transaction.publication_view
    if view is None or transaction.pointer_bytes is None:
        raise TerminalCycleError("ACTIVE_PUBLICATION_REQUIRED")
    if view.publication_id != expected_publication_id:
        raise TerminalCycleError("ACTIVE_PUBLICATION_IDENTITY_DIFFERS")

    authority_before = _authoritative_hashes(
        publication_root=publication_root,
        transaction=transaction,
    )
    pointer_sha256 = hashlib.sha256(transaction.pointer_bytes).hexdigest()
    gates = []

    # Stage 10 reads only the Golden bytes already bound by the pinned bundle.
    golden_count = validate_golden_results(publication_view=view)
    gates.append(_passed_gate(
        gate_id="STAGE_10_GOLDEN",
        details={"golden_assertion_count": golden_count},
    ))
    validate_validation_publication_transaction(
        workdir=publication_root,
        transaction=transaction,
    )

    # Stage 11 returns the exact immutable report and never runs its legacy
    # builder, repair hooks, or any authoritative writer.
    report = read_validated_report(publication_view=view)
    gates.append(_passed_gate(
        gate_id="STAGE_11_REPORT",
        details={
            "report_sha256": sha256_bytes(
                content=report.encode("utf-8")
            ),
            "report_size": len(report.encode("utf-8")),
        },
    ))
    validate_validation_publication_transaction(
        workdir=publication_root,
        transaction=transaction,
    )

    # Stage 12 verifies Golden, report, validation receipt, and every root
    # mirror again through the same in-memory PublicationView.
    stage_12 = validate_active_publication(
        publication_view=view,
        publication_root=publication_root,
    )
    if stage_12["publication_id"] != view.publication_id:
        raise TerminalCycleError("STAGE_12_PUBLICATION_IDENTITY_DIFFERS")
    gates.append(_passed_gate(
        gate_id="STAGE_12_PUBLICATION",
        details={
            "golden_assertion_count": stage_12[
                "golden_assertion_count"
            ],
            "publication_authority": stage_12["publication_authority"],
            "publication_validation_status": stage_12[
                "publication_validation_status"
            ],
        },
    ))
    validate_validation_publication_transaction(
        workdir=publication_root,
        transaction=transaction,
    )

    try:
        provenance = publish_validation_snapshot(
            workdir=publication_root,
            source_snapshot=source_snapshot,
            publication_transaction=transaction,
        )
        snapshot_path = _required_regular_file(
            root=publication_root,
            relative=PROVENANCE_RELATIVE_PATH,
        )
    except (
        OSError,
        TerminalCycleError,
        ValidationProvenanceError,
        ValueError,
    ) as error:
        # A partially written sidecar is not terminal evidence.  Keep failure
        # cleanup scoped to the generated proof and never touch pointer/mirror
        # authority or rerun a legacy producer.
        try:
            invalidate_validation_snapshot(workdir=publication_root)
        except (OSError, ValidationProvenanceError) as cleanup_error:
            raise TerminalCycleError(
                "SNAPSHOT_PUBLICATION_FAILED_AND_CLEANUP_FAILED: {}".format(
                    cleanup_error
                )
            ) from error
        raise TerminalCycleError(
            "SNAPSHOT_PUBLICATION_FAILED: {}".format(error)
        ) from error
    gates.append(_passed_gate(
        gate_id="SNAPSHOT_PUBLISH",
        details={
            "run_id": provenance["run_id"],
            "snapshot_sha256": sha256_file(path=snapshot_path),
        },
    ))

    checked = verify_validation_snapshot(
        workdir=publication_root,
        allow_equivalent_source_tree=False,
        publication_transaction=transaction,
    )
    if not checked.ok:
        invalidate_validation_snapshot(workdir=publication_root)
        raise TerminalCycleError(
            "SNAPSHOT_VERIFY_FAILED: " + "; ".join(checked.errors)
        )
    gates.append(_passed_gate(
        gate_id="SNAPSHOT_VERIFY",
        details={"warnings": list(checked.warnings)},
    ))

    try:
        authority_after = _authoritative_hashes(
            publication_root=publication_root,
            transaction=transaction,
        )
    except (
        OSError,
        TerminalCycleError,
        ValidationProvenanceError,
        ValueError,
    ) as error:
        invalidate_validation_snapshot(workdir=publication_root)
        raise TerminalCycleError(
            "TERMINAL_AUTHORITY_REVALIDATION_FAILED: {}".format(error)
        ) from error
    if authority_after != authority_before:
        invalidate_validation_snapshot(workdir=publication_root)
        raise TerminalCycleError(
            "TERMINAL_AUTHORITATIVE_BYTES_CHANGED"
        )
    if tuple(gate["gate_id"] for gate in gates) != TERMINAL_GATE_IDS:
        invalidate_validation_snapshot(workdir=publication_root)
        raise TerminalCycleError("TERMINAL_GATE_EXACT_SET_DIFFERS")

    body: Dict[str, object] = {
        "schema_version": 1,
        "status": "PASSED",
        "publication_id": view.publication_id,
        "active_pointer_sha256": pointer_sha256,
        "source_commit": source_snapshot.source_commit,
        "source_input_tree_sha256": source_snapshot.tree_sha256,
        "gates": gates,
        "authority_hashes_before": authority_before,
        "authority_hashes_after": authority_after,
        "validation_snapshot_sha256": sha256_file(path=snapshot_path),
        "side_effects": {
            "ai_socket_count": 0,
            "sec_socket_count": 0,
            "repair_count": 0,
            "report_authoritative_write_count": 0,
        },
    }
    return {
        **body,
        "terminal_cycle_id": content_hash(value=body),
    }
