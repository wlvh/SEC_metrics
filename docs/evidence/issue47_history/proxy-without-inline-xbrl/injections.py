"""Undo each part of the no-inline-XBRL proxy handling and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Each injection edits one file in place (exactly one match, must compile), runs
the module holding the case written for it with a fresh bytecode prefix, and
restores the bytes. The control run of both modules must pass first; the
script exits 1 unless every injection is caught by its case, except those
listed in NOT_CAUGHT_BY_A_CASE, which must NOT be caught (their check is the
end-to-end run, and a case that caught them would mean this list is wrong).
Zero calls.

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
IDENTITY = "scripts/vnext/historical_proxy_identity.py"
GOVERNANCE = "scripts/vnext/historical_governance_results.py"
DEI = "scripts/vnext/historical_dei.py"
TEXT_INPUT = "scripts/vnext/historical_text_input.py"
PROXY_CASES = "tests.vnext.test_historical_proxy_identity"
DEI_CASES = "tests.vnext.test_historical_dei"
MODULES = (PROXY_CASES, DEI_CASES)

# name: (file, old, new, the case written for it[, the module that holds it])
INJECTIONS = {
    "ANY_ROUTER_ERROR_REACHES_THE_COVER": (
        IDENTITY,
        """        if str(error) != NO_CONTEXTS or carries_inline_xbrl(raw_bytes):""",
        """        if carries_inline_xbrl(raw_bytes):""",
        "test_another_router_error_keeps_its_error"),
    "AN_INLINE_DOCUMENT_REACHES_THE_COVER": (
        IDENTITY,
        """        if str(error) != NO_CONTEXTS or carries_inline_xbrl(raw_bytes):""",
        """        if str(error) != NO_CONTEXTS:""",
        "test_a_broken_inline_document_keeps_its_error"),
    "ANOTHER_BOX_MAY_ALSO_BE_CHECKED": (
        IDENTITY,
        """    _need(marks["DEFINITIVE"] in CHECKED
          and all(mark in UNCHECKED for option, mark in marks.items() if option != "DEFINITIVE"),""",
        """    _need(marks["DEFINITIVE"] in CHECKED,""",
        "test_two_checked_boxes_are_refused"),
    "ANY_GLYPH_IS_A_MARK": (
        IDENTITY,
        """        _need(found[0] in CHECKED | UNCHECKED,""",
        """        _need(True,""",
        "test_an_unknown_glyph_is_refused_not_guessed"),
    "THE_CURRENT_NAME_COUNTS_ON_ANY_DATE": (
        IDENTITY,
        """    if not renamed or on_date >= max(renamed):""",
        """    if True:""",
        "test_the_record_s_dates_decide_which_name_counts"),
    "A_FORMER_NAME_COUNTS_ON_ANY_DATE": (
        IDENTITY,
        """    names = {entry["name"] for entry in former
             if entry["from"][:10] <= on_date <= entry["to"][:10]}""",
        """    names = {entry["name"] for entry in former}""",
        "test_a_former_name_does_not_count_after_the_rename"),
    "NAMES_ARE_COMPARED_WITH_THEIR_LEGAL_SUFFIXES": (
        IDENTITY,
        """    _need(_name_core(cover["registrant_name"]) in {_name_core(name) for name in names},""",
        """    _need(re.sub(r"\\W", "", cover["registrant_name"]).casefold()
          in {re.sub(r"\\W", "", name).casefold() for name in names},""",
        "test_the_name_is_the_sec_name_on_the_filing_date"),
    "THE_COVERAGE_DOES_NOT_SAY_HOW_THE_PROXY_WAS_IDENTIFIED": (
        IDENTITY,
        """    if (document["source_filing"]["form"] != "DEF 14A\"""",
        """    if True or (document["source_filing"]["form"] != "DEF 14A\"""",
        "test_the_coverage_says_the_cover_identified_the_proxy"),
    "C03_TAKES_ANY_ROUTER_ERROR_AS_THE_GAP": (
        GOVERNANCE,
        """            if (source is None or str(error) != NO_CONTEXTS
                    or carries_inline_xbrl(source["raw_bytes"])):""",
        """            if source is None:""",
        "test_an_inline_document_that_fails_the_parse_keeps_its_error"),
    "C03_DOES_NOT_NAME_THE_GAP": (
        GOVERNANCE,
        """        return blocked(PROXY_TABLE_NOT_READ, failures, category="IMPLEMENTATION_GAP")""",
        """        return blocked("C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND", failures)""",
        "test_the_withhold_names_the_gap_and_the_proxy"),
    "AN_OVERRIDE_MAY_NAME_WHAT_THE_CODE_DOES_NOT_READ": (
        DEI,
        """    if unread:
        raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_NAME_NOT_READ:\"""",
        """    if False:
        raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_NAME_NOT_READ:\"""",
        "test_a_name_the_code_does_not_read_is_refused", DEI_CASES),
    "AN_OVERRIDE_MAY_ASK_THE_QUESTION_WITHOUT_A_VIEW": (
        DEI,
        """        if not _is_view(value) and reaches_the_dei_question(value):
            raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_REACHES_THE_QUESTION:" + name)""",
        """        if False:
            raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_REACHES_THE_QUESTION:" + name)""",
        "test_a_replacement_that_asks_the_question_without_a_view_is_refused", DEI_CASES),
    "THE_OVERRIDE_IS_NOT_APPLIED": (
        DEI,
        """        namespace.update(overrides)""",
        """        None""",
        "test_the_named_global_is_replaced_and_nothing_else", DEI_CASES),
    # The input admission's call is checked by the end-to-end runs, whose
    # bindings record proxy_cover_identity; no case in these modules sees it.
    "THE_INPUT_DOES_NOT_CHECK_THE_COVER_NAME": (
        TEXT_INPUT,
        """            elif (governance["form"] == "DEF 14A"
                  and not carries_inline_xbrl(selected["raw_bytes"])):""",
        """            elif False:""",
        None),
}
NOT_CAUGHT_BY_A_CASE = {"THE_INPUT_DOES_NOT_CHECK_THE_COVER_NAME"}


def run(modules):
    """Each module in its own process; the failed case names across them."""
    failed, codes, started = set(), [], time.time()
    for module in modules:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
        done = subprocess.run([sys.executable, "-m", "unittest", module], cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=3600)
        codes.append(done.returncode)
        failed |= {line.split(" ")[1] for line in done.stderr.splitlines()
                   if line.startswith(("FAIL: ", "ERROR: "))}
    return codes, sorted(failed), int(time.time() - started)


def main(out, names):
    chosen = {name: INJECTIONS[name] for name in (names or INJECTIONS)}
    targets = sorted({spec[0] for spec in INJECTIONS.values()})
    originals = {name: (REPO / name).read_bytes() for name in targets}
    for name, (target, old, *_rest) in chosen.items():
        if originals[target].decode("utf-8").count(old) != 1:
            raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
    results = {}
    codes, failed, seconds = run(MODULES)
    if any(codes) or failed:
        raise SystemExit("CONTROL_FAILED:%s %s" % (codes, failed))
    results["CONTROL"] = {"returncodes": codes, "seconds": seconds}
    try:
        for name, (target, old, new, expected, *module) in chosen.items():
            path = REPO / target
            path.write_bytes(originals[target].decode("utf-8").replace(old, new).encode("utf-8"))
            py_compile.compile(str(path), doraise=True, cfile=tempfile.mktemp())
            modules = module or ([PROXY_CASES] if expected else list(MODULES))
            codes, failed, seconds = run(modules)
            path.write_bytes(originals[target])
            caught = expected in failed if expected else bool(failed)
            results[name] = {"file": target, "modules": modules, "returncodes": codes,
                             "seconds": seconds, "failed_cases": failed, "expected_case": expected,
                             "caught_by_the_case_written_for_it": caught,
                             "as_expected": caught != (name in NOT_CAUGHT_BY_A_CASE)}
            print(name, caught, failed, flush=True)
    finally:
        for target, data in originals.items():
            (REPO / target).write_bytes(data)
    for target, data in originals.items():
        if (REPO / target).read_bytes() != data:
            raise SystemExit("TARGET_NOT_RESTORED:" + target)
    results["all_as_expected"] = all(results[name]["as_expected"] for name in chosen)
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_as_expected": results["all_as_expected"]}), flush=True)
    return 0 if results["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
