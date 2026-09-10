"""Run M1 filing inventory.

Purpose:
    Locate target 10-K, prior 10-K, latest DEF 14A, and fiscal-window 8-K
    filings from saved submissions evidence.

Call relationships:
    main calls sec_pipeline.run_stage for 02_inventory_filings.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the filing-inventory stage."""
    run_stage(stage_name="02_inventory_filings")


if __name__ == "__main__":
    main()
