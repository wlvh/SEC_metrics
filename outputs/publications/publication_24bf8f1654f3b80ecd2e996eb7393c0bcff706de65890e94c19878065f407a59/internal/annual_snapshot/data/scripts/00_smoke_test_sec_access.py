"""Run M0 SEC access smoke test.

Purpose:
    Fetch SEC company_tickers_exchange.json with configured User-Agent and
    write audited request evidence.

Call relationships:
    main calls sec_pipeline.run_stage for 00_smoke_test_sec_access.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the smoke-test stage."""
    run_stage(stage_name="00_smoke_test_sec_access")


if __name__ == "__main__":
    main()
