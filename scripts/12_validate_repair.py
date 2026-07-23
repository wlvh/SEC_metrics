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
    publish_validation_snapshot,
)


WORKDIR = Path(__file__).resolve().parents[1]


def main() -> None:
    """Execute stage 12 and fail closed if provenance cannot be published."""
    invalidate_validation_snapshot(workdir=WORKDIR)
    source_snapshot = capture_source_snapshot(workdir=WORKDIR)
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
