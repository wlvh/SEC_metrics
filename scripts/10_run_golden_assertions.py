"""Run M7 golden assertions.

Purpose:
    Independently recompute structure and numeric assertions from this run's
    SEC evidence, then stop on any failure while reporting actual values.

Call relationships:
    main calls sec_pipeline.run_stage for 10_run_golden_assertions.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the golden assertion stage."""
    run_stage(stage_name="10_run_golden_assertions")


if __name__ == "__main__":
    main()
