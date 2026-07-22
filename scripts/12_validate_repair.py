"""Run repair validation.

Purpose:
    Validate the bounded SEC ten-company repair package after stage 11. The
    script writes the validation run manifest and validation results, refreshes
    the report verdict, and exits nonzero on any blocking P0 status.

Call relationships:
    main calls sec_pipeline.run_stage for 12_validate_repair.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the repair validation stage."""
    run_stage(stage_name="12_validate_repair")


if __name__ == "__main__":
    main()
