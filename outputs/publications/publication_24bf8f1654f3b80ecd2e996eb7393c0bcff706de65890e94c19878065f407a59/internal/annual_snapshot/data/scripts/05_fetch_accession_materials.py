"""Run M3 accession material fetch.

Purpose:
    Download target 10-K accession index, filing detail page, FilingSummary,
    primary document, and candidate XBRL instance XML files.

Call relationships:
    main calls sec_pipeline.run_stage for 05_fetch_accession_materials.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the accession-material fetch stage."""
    run_stage(stage_name="05_fetch_accession_materials")


if __name__ == "__main__":
    main()
