"""Run M6 MD&A, KPI, risk, and legal text extraction.

Purpose:
    Extract text evidence from target 10-K primary documents for MD&A industry
    KPIs, risk factors, legal proceedings, regulatory investigations, and going
    concern statements.

Call relationships:
    main calls sec_pipeline.run_stage for 09_extract_mda_and_risk_text.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the MD&A and risk text extraction stage."""
    run_stage(stage_name="09_extract_mda_and_risk_text")


if __name__ == "__main__":
    main()
