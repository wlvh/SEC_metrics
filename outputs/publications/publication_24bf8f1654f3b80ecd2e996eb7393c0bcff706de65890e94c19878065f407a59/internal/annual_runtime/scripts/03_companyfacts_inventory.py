"""Run M2 companyfacts inventory.

Purpose:
    Fetch SEC companyfacts JSON and flatten all concept/unit/fact observations
    into per-company inventories.

Call relationships:
    main calls sec_pipeline.run_stage for 03_companyfacts_inventory.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the companyfacts-inventory stage."""
    run_stage(stage_name="03_companyfacts_inventory")


if __name__ == "__main__":
    main()
