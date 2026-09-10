"""Run M4 8-K event extraction.

Purpose:
    Download fiscal-window 8-K hdr.sgml files, parse all item codes, and update
    event-backed metric rows.

Call relationships:
    main calls sec_pipeline.run_stage for 07_extract_8k_events.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the 8-K event extraction stage."""
    run_stage(stage_name="07_extract_8k_events")


if __name__ == "__main__":
    main()
