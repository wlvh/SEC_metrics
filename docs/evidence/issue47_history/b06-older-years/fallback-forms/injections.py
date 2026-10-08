"""Undo each part of the B06 fallback successors and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../../c03-first-ecd-release/injections.py: each injection edits
the route in place (exactly one match, must compile), runs the module holding
its case with a fresh bytecode prefix, and restores the bytes. The control run
- the new module and the cascade's existing one - must pass first. It edits
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

ROUTE = "scripts/vnext/historical_debt_results.py"
CASES = "tests.vnext.test_historical_debt_fallback_forms"
ANSWERS = "test_the_successor_answers_with_both_rows_resolved"
harness.SOURCE, harness.NOTE = ROUTE, ROUTE
harness.MODULES, harness.CASES = (CASES, "tests.vnext.test_historical_debt_results"), CASES
harness.INJECTIONS = {
    "PASS_THROUGH_CERTIFICATES_ARE_NOT_AN_INSTRUMENT": (
        ROUTE,
        "     r\"elif re.search(r'\\b(?:notes|debentures|loan|credit agreement|certificates)\\b',lab,re.I):\"),",
        "     r\"elif re.search(r'\\b(?:notes|debentures|loan|credit agreement)\\b',lab,re.I):\"),",
        ANSWERS),
    "A_PENSION_OBLIGATION_IS_LEFT_UNRESOLVED": (
        ROUTE,
        "     \"revenueremainingperformanceobligation|definedbenefitplan',short):\"",
        "     \"revenueremainingperformanceobligation',short):\"",
        ANSWERS),
    "THE_V2_RESOLVER_CALLS_THE_FROZEN_INVENTORY": (
        ROUTE,
        "     \"    from .historical_debt_results import fallback_verify_v1\\n\"\n"
        "     \"    proof = fallback_verify_v1(raw=raw, primary=primary, source=source, spec=spec,\"),)",
        "     \"    proof = prior.verify(raw=raw, primary=primary, source=source, spec=spec,\"),)",
        ANSWERS),
    "THE_RESOLUTION_CALLS_THE_FROZEN_V2": (
        ROUTE,
        "     '        from .historical_debt_results import fallback_verify\\n'\n"
        "     '        measurement = fallback_verify(raw=preparation[\"xml\"][\"raw_bytes\"],'),)",
        "     '        measurement = disclosure.verify(raw=preparation[\"xml\"][\"raw_bytes\"],'),)",
        ANSWERS),
    "THE_FALLBACK_CASE_CALLS_THE_FROZEN_RESOLUTION": (
        ROUTE,
        "    path, resolution = fallback_resolution(data_root=repo_root, preparation=preparation)\n",
        "    from .normal_candidates import _b06_resolution\n"
        "    path, resolution = _b06_resolution(data_root=repo_root, preparation=preparation)\n",
        "test_the_fallback_case_calls_the_successor_resolution"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
