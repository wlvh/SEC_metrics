"""Run repair validation.

Purpose:
    Validate the bounded SEC ten-company repair package after M7 report build.
    The script writes outputs/repair_validation_results.csv and exits nonzero
    on any P0 validation failure.

Call relationships:
    main calls sec_pipeline.run_stage for 12_validate_repair.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the repair validation stage."""
    run_stage(stage_name="12_validate_repair")


if __name__ == "__main__":
    main()
