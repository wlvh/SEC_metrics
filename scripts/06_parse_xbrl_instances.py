"""Run M3 XBRL instance parsing.

Purpose:
    Stream parse saved XBRL/iXBRL instance files into concept inventories with
    context, dimensions, period, unit, and raw value.

Call relationships:
    main calls sec_pipeline.run_stage for 06_parse_xbrl_instances.
"""

from sec_pipeline import run_stage


def main() -> None:
    """Execute the XBRL instance parsing stage."""
    run_stage(stage_name="06_parse_xbrl_instances")


if __name__ == "__main__":
    main()
