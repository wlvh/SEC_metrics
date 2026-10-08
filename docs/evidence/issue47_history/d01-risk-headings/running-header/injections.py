"""Undo each part of the running-header successor and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../../c03-first-ecd-release/injections.py: each injection edits
the route in place (exactly one match, must compile), runs the module holding
its case with a fresh bytecode prefix, and restores the bytes. The control run
- the new module and the D01 chain's existing one - must pass first. It edits
the tree it lives in, so run it from a clone or worktree nothing else reads.
Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parents[1] / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

ROUTE = "scripts/vnext/historical_risk_results.py"
CASES = "tests.vnext.test_historical_running_header"
harness.SOURCE, harness.NOTE = ROUTE, ROUTE
harness.MODULES, harness.CASES = (CASES, "tests.vnext.test_historical_risk_headings"), CASES
harness.INJECTIONS = {
    "THE_TWO_PART_FORM_IS_NOT_ADDED": (
        ROUTE,
        'SEVERAL_PARTS = ((r"part\\s+[ivx]+$)", r"part\\s+[ivx]+$|parts\\s+[ivx]+\\s+and\\s+[ivx]+$)"),)',
        'SEVERAL_PARTS = ((r"part\\s+[ivx]+$)", r"part\\s+[ivx]+$)"),)',
        "test_the_two_part_label_goes_where_the_one_part_label_went"),
    "THE_FORM_IS_NOT_THE_WHOLE_TEXT": (
        ROUTE,
        '|parts\\s+[ivx]+\\s+and\\s+[ivx]+$)"),)',
        '|parts\\s+[ivx]+\\s+and\\s+[ivx]+)"),)',
        "test_a_heading_that_begins_with_a_part_label_is_still_a_heading"),
    "ANY_TEXT_BEGINNING_WITH_PARTS_IS_A_LABEL": (
        ROUTE,
        '|parts\\s+[ivx]+\\s+and\\s+[ivx]+$)"),)',
        '|parts\\b.*$)"),)',
        "test_a_heading_that_begins_with_a_part_label_is_still_a_heading"),
    "THE_DERIVATION_KEEPS_THE_FROZEN_SELECTOR": (
        ROUTE,
        '                    "from .historical_risk_results import risk_factor_headings"),)',
        '                    "from .risk_signals import risk_factor_headings"),)',
        "test_where_the_page_closes_item_1a_the_header_is_the_one_line_dropped"),
    "THE_CANDIDATE_IS_BUILT_BY_THE_FROZEN_DERIVATION": (
        ROUTE,
        "    return _derive_candidate(",
        "    return frozen._derive_deterministic_candidate(",
        "test_the_route_delivers_the_successor_s_candidate_and_replays_it"),
    "THE_EVIDENCE_REPLAYS_WITH_THE_FROZEN_DERIVATION": (
        ROUTE,
        "        expected = _derive_candidate(",
        "        expected = frozen._derive_deterministic_candidate(",
        "test_the_route_delivers_the_successor_s_candidate_and_replays_it"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
