"""Undo each part of the proxy Summary Compensation Table reader and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Each injection edits one rule file in place (exactly one match, must compile),
runs the module holding the case written for it with a fresh bytecode prefix,
and restores the bytes. The control run of both modules must pass first; the
script exits 1 unless every injection is caught by its case. Zero calls.

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
READER = "scripts/vnext/historical_proxy_compensation.py"
ROUTE = "scripts/vnext/historical_governance_results.py"
CASES = "tests.vnext.test_historical_proxy_compensation"
ROUTE_CASES = "tests.vnext.test_historical_proxy_identity"
MODULES = (CASES, ROUTE_CASES)

# name: (file, old, new, the case written for it[, the module that holds it])
INJECTIONS = {
    "THE_TOTAL_NEED_NOT_BE_THE_SUM": (
        READER,
        """            elif sum(value for value, _ in amounts[:-1]) != amounts[-1][0]:""",
        """            elif False:""",
        "test_a_total_that_is_not_the_sum_is_refused"),
    "ANOTHER_BODY_S_CHIEF_EXECUTIVE_COUNTS": (
        READER,
        """        if _ANOTHER_BODY.match(text[match.end():]):
            continue""",
        """        if False:
            continue""",
        "test_a_subsidiary_s_chief_executive_is_not_the_registrant_s"),
    "A_DEPUTY_COUNTS": (
        READER,
        """        if _NOT_THE_CHIEF.search(text[:match.start()]):
            continue""",
        """        if False:
            continue""",
        "test_not_the_registrant_s_chief_executive"),
    "TWO_CHIEF_EXECUTIVES_TAKE_THE_FIRST": (
        READER,
        """    if len(candidates) == 1 and passing:""",
        """    if passing:""",
        "test_two_chief_executives_are_both_kept_and_withheld"),
    "NO_DOLLAR_SIGN_IS_NEEDED": (
        READER,
        """            elif "$" not in header + " ".join(text for _, text in person["amount_cells"]):""",
        """            elif False:""",
        "test_a_table_without_a_dollar_sign_is_refused"),
    "THE_TITLE_YEAR_IS_NOT_COMPARED": (
        READER,
        """        if years and years != {str(fiscal_year)}:""",
        """        if False:""",
        "test_a_title_for_another_year_is_refused"),
    "A_FOREIGN_CURRENCY_IS_NOT_REFUSED": (
        READER,
        """        elif re.search(_FOREIGN_CURRENCY, context_text, re.I):""",
        """        elif False:""",
        "test_a_foreign_currency_in_the_context_is_refused"),
    "ANY_TABLE_WITH_THE_COLUMNS_IS_THE_SUMMARY_TABLE": (
        READER,
        """        if not titled and not header_titles:""",
        """        if False:""",
        "test_a_table_without_a_title_is_not_the_summary_table"),
    "A_FOOTNOTE_MARK_IS_AN_AMOUNT": (
        READER,
        """        if _FOOTNOTE_ONLY.fullmatch(token):
            continue""",
        """        if False:
            continue""",
        "test_amounts_keep_their_order_and_drop_footnote_marks"),
    "THE_TITLE_ON_THE_NEXT_ROW_IS_NOT_READ": (
        READER,
        """            name_cells.extend(cells if year_at is None else cells[:year_at])""",
        """            name_cells.extend(cells[:year_at] if index == start else [])""",
        "test_six_give_one_chief_executive_s_total"),
    "THE_COVER_NAME_IS_NOT_CHECKED": (
        READER,
        """    identity = cover_name_in_effect(cover=proxy_cover(raw_bytes=raw_bytes, filing=filing),
                                    inventory=inventory, filing=filing)""",
        """    identity = {}""",
        "test_another_registrant_s_cover_is_refused"),
    "A_PROXY_WITH_INLINE_XBRL_IS_READ_HERE": (
        READER,
        """    _need(not carries_inline_xbrl(raw_bytes), "C03_PROXY_SCT_ONLY_FOR_A_PROXY_WITHOUT_INLINE_XBRL")""",
        """    pass""",
        "test_a_proxy_with_inline_xbrl_is_not_read_here"),
    "THE_ROUTE_DOES_NOT_TAKE_THE_PROXY_TABLE_S_ANSWER": (
        ROUTE,
        """            if proxy_resolved["result"]["value"] is not None:
                return PROXY_TABLE_SPEC_PATH, proxy_resolved, None""",
        """            if False:
                return PROXY_TABLE_SPEC_PATH, proxy_resolved, None""",
        "test_the_proxy_table_answers", ROUTE_CASES),
}


def run(modules):
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
    originals = {target: (REPO / target).read_bytes() for target in (READER, ROUTE)}
    for name, (target, old, *_rest) in chosen.items():
        if originals[target].decode("utf-8").count(old) != 1:
            raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
    codes, failed, seconds = run(MODULES)
    if any(codes) or failed:
        raise SystemExit("CONTROL_FAILED:%s %s" % (codes, failed))
    results = {"CONTROL": {"returncodes": codes, "seconds": seconds}}
    try:
        for name, (target, old, new, expected, *module) in chosen.items():
            path = REPO / target
            path.write_bytes(originals[target].decode("utf-8").replace(old, new).encode("utf-8"))
            py_compile.compile(str(path), doraise=True, cfile=tempfile.mktemp())
            modules = module or [CASES]
            codes, failed, seconds = run(modules)
            path.write_bytes(originals[target])
            results[name] = {"file": target, "modules": modules, "returncodes": codes,
                             "seconds": seconds, "failed_cases": failed, "expected_case": expected,
                             "caught_by_the_case_written_for_it": expected in failed}
            print(name, expected in failed, failed, flush=True)
    finally:
        for target, data in originals.items():
            (REPO / target).write_bytes(data)
    for target, data in originals.items():
        if (REPO / target).read_bytes() != data:
            raise SystemExit("TARGET_NOT_RESTORED:" + target)
    results["all_caught"] = all(results[name]["caught_by_the_case_written_for_it"] for name in chosen)
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_caught": results["all_caught"]}), flush=True)
    return 0 if results["all_caught"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
