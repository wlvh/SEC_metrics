"""Run terminal repair validation and publish snapshot provenance.

The underlying stage still owns Golden/repair/report semantics. This wrapper
adds the final source/artifact binding: a zero exit is not returned until the
source-input tree and the acceptance artifacts have been hashed, persisted and
verified independently.
"""

from pathlib import Path

from validation_provenance import (
    capture_source_snapshot,
    fail_validation_snapshot,
    ensure_report_provenance_notice,
    invalidate_validation_snapshot,
    pin_validation_publication_transaction,
    publish_validation_snapshot,
)


WORKDIR = Path(__file__).resolve().parents[1]


def _active_pointer_exists() -> bool:
    """Return whether Stage 12 must enter the formal active read path.

    Returns:
        ``True`` for a regular or symlinked pointer. Unsafe pointers enter the
        active verifier and fail closed rather than falling back to legacy.
    """
    pointer = WORKDIR / "outputs" / "active_publication.json"
    return pointer.exists() or pointer.is_symlink()


def _run_active_validation(*, source_snapshot: object) -> None:
    """Validate one pinned active view and publish only its provenance sidecar.

    Args:
        source_snapshot: Clean source closure captured before active read-back.

    Expected output:
        Root compatibility mirrors remain byte-identical to the verified
        bundle; only the validation snapshot sidecar may be replaced.
    """
    from vnext.publication import recover_publication_mirrors
    from vnext.report import validate_active_publication

    transaction = pin_validation_publication_transaction(workdir=WORKDIR)
    view = transaction.publication_view
    if view is None:
        raise SystemExit(1)
    try:
        # A mirror can be interrupted after its bytes move but before a pointer
        # commit.  Keep the first bundle-to-root comparison inside the recovery
        # boundary so Stage 12 restores official bytes and exits nonzero instead
        # of leaking a traceback or leaving divergent compatibility mirrors.
        result = validate_active_publication(
            publication_view=view,
            publication_root=WORKDIR,
        )
        publish_validation_snapshot(
            workdir=WORKDIR,
            source_snapshot=source_snapshot,
            publication_transaction=transaction,
        )
    except Exception as error:
        # An active failure may invalidate only the new sidecar. Reconcile root
        # mirrors from the official pointer; never rewrite bundle-derived
        # report/manifest bytes into a synthetic legacy FAILED view.
        try:
            invalidate_validation_snapshot(workdir=WORKDIR)
            recover_publication_mirrors(publication_root=WORKDIR)
        except Exception as recovery_error:
            print(
                "Active provenance failed and mirror recovery also failed: "
                "{}; recovery_error={}".format(error, recovery_error)
            )
        raise SystemExit(1) from error
    print(
        "Stage 12 active publication validation complete; "
        "publication_id={}; golden_assertions={}".format(
            result["publication_id"], result["golden_assertion_count"],
        )
    )


def main() -> None:
    """Execute stage 12 and fail closed if provenance cannot be published."""
    invalidate_validation_snapshot(workdir=WORKDIR)
    source_snapshot = capture_source_snapshot(workdir=WORKDIR)
    if _active_pointer_exists():
        _run_active_validation(source_snapshot=source_snapshot)
        return
    from sec_pipeline import run_stage

    run_stage(stage_name="12_validate_repair")
    try:
        ensure_report_provenance_notice(workdir=WORKDIR)
        publish_validation_snapshot(
            workdir=WORKDIR,
            source_snapshot=source_snapshot,
        )
    except Exception as error:
        # Any post-stage exception must fail closed. Restricting this boundary to
        # ValidationProvenanceError would leave a PASSED manifest observable when
        # an unexpected filesystem/encoding error interrupted sidecar publication.
        try:
            fail_validation_snapshot(workdir=WORKDIR, reason=str(error))
        except Exception as fail_error:
            print(
                "Validation provenance failed and the fail-closed rewrite also "
                "failed: {}; rewrite_error={}".format(error, fail_error)
            )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
