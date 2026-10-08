"""Undo each part of the paired-measure check and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../c03-first-ecd-release/injections.py: each injection edits a
file in place (exactly one match, must compile), runs the module holding its
case with a fresh bytecode prefix, and restores the bytes. The control run
must pass first. It edits the tree it lives in, so nothing else may read that
tree while it runs. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parent / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

SOURCE = "scripts/vnext/historical_results.py"
CASES = "tests.vnext.test_historical_paired_measure"
harness.SOURCE, harness.NOTE, harness.MODULES, harness.CASES = SOURCE, SOURCE, (CASES,), CASES
harness.INJECTIONS = {
    "A_PAIR_ON_TWO_CONCEPTS_IS_NEVER_ASKED": (
        SOURCE,
        "        if current[\"concept\"] == prior[\"concept\"]:\n",
        "        if True:\n",
        "test_product_revenue_over_total_revenue_is_withheld"),
    "ANY_REPORTED_VALUE_BRIDGES": (
        SOURCE,
        "        if reported == [str(Decimal(prior[\"value\"]))]:\n",
        "        if reported:\n",
        "test_product_revenue_over_total_revenue_is_withheld"),
    "THE_BRIDGE_IS_LOOKED_FOR_IN_THE_PRIOR_FILING": (
        SOURCE,
        "                           if claim[\"attributes\"][\"accession\"] == accessions[\"current\"]\n",
        "                           if claim[\"attributes\"][\"accession\"] == accessions[\"prior\"]\n",
        "test_two_concepts_the_target_filing_shows_are_one_quantity_are_kept"),
    "EVERY_CONCEPT_LIST_IS_A_PAIR": (
        SOURCE,
        "                      if {\"current\", \"prior\"} <= seen)\n",
        "                      if seen)\n",
        "test_the_routes_that_read_one_quantity_twice"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
