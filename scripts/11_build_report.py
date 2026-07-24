"""Run stage 11 bounded repair and report generation.

Stage 11 may build a report even when the terminal validation later fails. It
therefore invalidates any older validation-snapshot provenance before changing
artifacts and re-injects the task-oriented reading routes into the generated
README after the monolithic stage returns.
"""

from pathlib import Path

from validation_provenance import (
    ensure_readme_routes,
    ensure_report_provenance_notice,
    invalidate_validation_snapshot,
)


WORKDIR = Path(__file__).resolve().parents[1]


def main() -> None:
    """Execute report build without leaving an older success proof reusable."""
    invalidate_validation_snapshot(workdir=WORKDIR)
    from sec_pipeline import run_stage

    run_stage(stage_name="11_build_report")
    ensure_readme_routes(workdir=WORKDIR)
    ensure_report_provenance_notice(workdir=WORKDIR)


if __name__ == "__main__":
    main()
