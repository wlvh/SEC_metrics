"""Undo each part of the accession route's dated-release reading and require its case to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../c03-first-ecd-release/injections.py: each injection edits a
file in place (exactly one match, must compile), runs the module holding its
case with a fresh bytecode prefix, and restores the bytes. The control run must
pass first. It edits the tree it lives in, so run it from a clone or worktree
nothing else reads. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parent / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

VIEW = "scripts/vnext/historical_dei.py"
ROUTE = "scripts/vnext/historical_accession_results.py"
CASES = "tests.vnext.test_historical_accession_releases"
harness.SOURCE, harness.NOTE = VIEW, ROUTE
harness.MODULES, harness.CASES = (CASES,), CASES
harness.INJECTIONS = {
    "THE_SRT_RELEASE_IS_NOT_IN_THE_VIEW": (
        VIEW,
        "            **{p: SRT_NAMESPACE_PATTERN for p in FROZEN_SRT_NAMESPACE_PATTERNS}}",
        "            }",
        "test_the_fy2021_capital_ratios_are_read_after_the_frozen_refusal"),
    "ANY_SRT_SUFFIX_IS_ACCEPTED": (
        VIEW,
        'SRT_NAMESPACE_PATTERN = r"https?://fasb\\.org/srt/[0-9]{4}(?:-\\d{2}-\\d{2})?"',
        'SRT_NAMESPACE_PATTERN = r"https?://fasb\\.org/srt/[0-9]{4}.*"',
        "test_a_namespace_that_is_not_a_fasb_release_is_still_refused"),
    "AN_UNKNOWN_PATTERN_IS_PASSED_THROUGH": (
        VIEW,
        '        raise HistoricalDeiError("HISTORICAL_DEI_NOT_A_FROZEN_NAMESPACE_PATTERN:" + repr(pattern)[:120])\n',
        "        return pattern\n",
        "test_a_pattern_that_is_not_frozen_is_refused"),
    "THE_POLICY_IS_WIDENED_FOR_EVERY_REPORT": (
        ROUTE,
        "        if not refused:\n"
        "            return inspection, arguments[\"policy\"]\n",
        "        pass\n",
        "test_a_year_alone_report_is_the_frozen_inspection"),
    "THE_CONCEPT_NAMESPACE_REFUSAL_IS_NOT_A_RELEASE_REFUSAL": (
        ROUTE,
        "DATED_RELEASE_REFUSALS = (\"NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED\",\n"
        "                          \"NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED\")\n",
        "DATED_RELEASE_REFUSALS = (\"NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED\",)\n",
        "test_the_fy2022_rpo_is_read_after_the_frozen_refusal"),
    "ANOTHER_REFUSAL_IS_SWALLOWED": (
        ROUTE,
        "        if str(error) not in DATED_RELEASE_REFUSALS:\n"
        "            raise\n",
        "        if str(error) not in DATED_RELEASE_REFUSALS:\n"
        "            return {\"status\": \"UNRESOLVED\", \"conflicts\": [], \"selected_claims\": [],\n"
        "                    \"facts\": []}, arguments[\"policy\"]\n",
        "test_another_refusal_is_the_frozen_one"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
