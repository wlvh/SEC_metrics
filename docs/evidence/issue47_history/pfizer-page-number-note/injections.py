"""Undo each part of the page-number-aware note navigation and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Each injection edits one rule file in place (exactly one match, must compile),
runs tests.vnext.test_historical_note_navigation with a fresh bytecode prefix,
and restores the bytes. The control run must pass first; the script exits 1
unless every injection is caught by the case named for it. Zero calls.

It edits the tree it lives in, so nothing else may import from or read that
tree while it runs.
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROUTE = "scripts/vnext/historical_text_results.py"
CASES = "tests.vnext.test_historical_note_navigation"

# name: (file, old, new, the case written for it)
INJECTIONS = {
    "PAGE_NUMBERS_ARE_NOT_BLANKED": (
        ROUTE,
        """    pages = page_number_blocks(document["blocks"])
    if not pages:
        return _note_references(document, ranges)""",
        """    pages = set()
    if not pages:
        return _note_references(document, ranges)""",
        "test_pfizer_fy2024_resolves_note_16a_to_the_real_note"),
    "ANY_NUMBER_BESIDE_A_FOOTER_IS_A_PAGE": (
        ROUTE,
        """            if texts[neighbour] >= 3 and beside[(side, neighbour)] & {number - 1, number + 1}:""",
        """            if texts[neighbour] >= 3:""",
        "test_a_numbered_heading_after_a_running_footer_is_not_a_page"),
    "THE_FOOTER_NEED_NOT_REPEAT": (
        ROUTE,
        """            if texts[neighbour] >= 3 and beside[(side, neighbour)] & {number - 1, number + 1}:""",
        """            if beside[(side, neighbour)] & {number - 1, number + 1}:""",
        "test_a_footer_that_does_not_repeat_three_times_is_not_a_running_footer"),
    "D02_PREPARES_THROUGH_THE_FROZEN_NAVIGATION": (
        ROUTE,
        """    prepared = _D02_PREPARATION(metric_id=metric_id, **source_arguments)""",
        """    prepared = release_aware(frozen).prepare_business_text_sources(metric_id=metric_id,
                                                                   **source_arguments)""",
        "test_the_d02_path_calls_the_successor_preparation"),
    "THE_PREPARATION_KEEPS_THE_FROZEN_LEGAL_SCAN": (
        ROUTE,
        """_D02_PREPARATION = release_aware_with(frozen.prepare_business_text_sources,
                                      legal_risk_candidates=_D02_LEGAL_SCAN)""",
        """_D02_PREPARATION = release_aware_with(frozen.prepare_business_text_sources)""",
        "test_the_successor_preparation_reads_the_successor_navigation"),
    "THE_LEGAL_SCAN_KEEPS_THE_FROZEN_NAVIGATION": (
        ROUTE,
        """_D02_LEGAL_SCAN = release_aware_with(_frozen_candidates.legal_risk_candidates,
                                     _note_references=note_references)""",
        """_D02_LEGAL_SCAN = release_aware_with(_frozen_candidates.legal_risk_candidates,
                                     _note_references=_note_references)""",
        "test_d02_s_legal_scan_now_covers_its_ranges"),
    "THE_REFERENCED_NOTES_KEEP_THE_FROZEN_NAVIGATION": (
        ROUTE,
        """    references = note_references(document, ranges)
    for reference in references:
        if reference["status"] != "LOCATED_NOTE_RANGE":""",
        """    references = _note_references(document, ranges)
    for reference in references:
        if reference["status"] != "LOCATED_NOTE_RANGE":""",
        "test_the_referenced_notes_are_located_with_the_same_navigation"),
}


def run():
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest", CASES], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=3600)
    failed = {line.split(" ")[1] for line in done.stderr.splitlines()
              if line.startswith(("FAIL: ", "ERROR: "))}
    return done.returncode, sorted(failed), int(time.time() - started)


def main(out, names):
    chosen = {name: INJECTIONS[name] for name in (names or INJECTIONS)}
    original = (REPO / ROUTE).read_bytes()
    for name, (_target, old, *_rest) in chosen.items():
        if original.decode("utf-8").count(old) != 1:
            raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
    code, failed, seconds = run()
    if code or failed:
        raise SystemExit("CONTROL_FAILED:%s %s" % (code, failed))
    results = {"CONTROL": {"returncode": code, "seconds": seconds}}
    try:
        for name, (target, old, new, expected) in chosen.items():
            path = REPO / target
            path.write_bytes(original.decode("utf-8").replace(old, new).encode("utf-8"))
            py_compile.compile(str(path), doraise=True, cfile=tempfile.mktemp())
            code, failed, seconds = run()
            path.write_bytes(original)
            results[name] = {"file": target, "returncode": code, "seconds": seconds,
                             "failed_cases": failed, "expected_case": expected,
                             "caught_by_the_case_written_for_it": expected in failed}
            print(name, expected in failed, failed, flush=True)
    finally:
        (REPO / ROUTE).write_bytes(original)
    if (REPO / ROUTE).read_bytes() != original:
        raise SystemExit("TARGET_NOT_RESTORED:" + ROUTE)
    results["all_caught"] = all(results[name]["caught_by_the_case_written_for_it"] for name in chosen)
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_caught": results["all_caught"]}), flush=True)
    return 0 if results["all_caught"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
