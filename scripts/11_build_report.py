"""Run stage 11 bounded repair and report generation.

Purpose:
    Primarily use local artifacts for bounded repair, while allowing C04
    AuditorName to conditionally fetch official SEC material when required
    local facts are unavailable. Then build coverage, validation evidence,
    README, and the final Chinese Markdown report.

Call relationships:
    main calls sec_pipeline.run_stage for 11_build_report.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the final report build stage."""
    run_stage(stage_name="11_build_report")


if __name__ == "__main__":
    main()
