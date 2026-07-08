"""Run M0 company resolution.

Purpose:
    Fetch ten-company submissions JSON, resolve identity fields, and run
    fail-fast structural assertions.

Call relationships:
    main calls sec_pipeline.run_stage for 01_resolve_companies.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the company-resolution stage."""
    run_stage(stage_name="01_resolve_companies")


if __name__ == "__main__":
    main()
