"""Run M5 DEF 14A governance extraction.

Purpose:
    Fetch latest DEF 14A primary documents, dump ecd facts when present, and
    capture board and compensation evidence snippets.

Call relationships:
    main calls sec_pipeline.run_stage for 08_extract_def14a.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the DEF 14A extraction stage."""
    run_stage(stage_name="08_extract_def14a")


if __name__ == "__main__":
    main()
