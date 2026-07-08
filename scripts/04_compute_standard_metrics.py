"""Run M2 standard metric computation.

Purpose:
    Compute companyfacts-supported financial metrics and initialize full metric
    coverage rows for later text, DEF 14A, and 8-K stages.

Call relationships:
    main calls sec_pipeline.run_stage for 04_compute_standard_metrics.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the standard-metrics stage."""
    run_stage(stage_name="04_compute_standard_metrics")


if __name__ == "__main__":
    main()
