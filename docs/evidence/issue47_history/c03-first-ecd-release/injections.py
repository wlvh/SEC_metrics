"""Undo each part of the ECD release widening and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Each injection edits the rule file in place (exactly one match, must compile),
runs the module holding the case written for it with a fresh bytecode prefix,
and restores the bytes. The control run must pass first; the script exits 1
unless every injection is caught by its case. Zero calls.

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
SOURCE = "scripts/vnext/historical_dei.py"
NOTE = "scripts/vnext/historical_amendment_note.py"
CASES = "tests.vnext.test_historical_ecd_release"
DEI = "tests.vnext.test_historical_dei"
MODULES = (CASES, DEI)

# name: (file, old, new, the case written for it[, the module that holds it])
INJECTIONS = {
    "THE_ECD_QUESTION_IS_NOT_WIDENED": (
        SOURCE,
        "            **{p: ECD_NAMESPACE_PATTERN for p in FROZEN_ECD_NAMESPACE_PATTERNS}}",
        "            }",
        "test_the_view_reads_the_first_release_and_the_next_proxy_is_recorded_as_it_comes_out"),
    "ANY_ECD_SUFFIX_IS_ACCEPTED": (
        SOURCE,
        'ECD_NAMESPACE_PATTERN = r"https?://xbrl\\.sec\\.gov/ecd/\\d{4}(?:q[1-4]|-\\d{2}-\\d{2})?"',
        'ECD_NAMESPACE_PATTERN = r"https?://xbrl\\.sec\\.gov/ecd/\\d{4}\\w*"',
        "test_the_three_release_forms_and_nothing_else"),
    "THE_ECD_QUESTION_IS_ANSWERED_WITH_THE_DEI_PATTERN": (
        SOURCE,
        "            **{p: ECD_NAMESPACE_PATTERN for p in FROZEN_ECD_NAMESPACE_PATTERNS}}",
        "            **{p: DEI_NAMESPACE_PATTERN for p in FROZEN_ECD_NAMESPACE_PATTERNS}}",
        "test_each_frozen_pattern_is_answered_by_its_own_widened_pattern"),
    "ONLY_ONE_FROZEN_ECD_SPELLING_IS_WIDENED": (
        SOURCE,
        'FROZEN_ECD_NAMESPACE_PATTERNS = (r"https?://xbrl\\.sec\\.gov/ecd/\\d{4}",\n'
        '                                 r"https?://xbrl\\.sec\\.gov/ecd/[0-9]{4}")',
        'FROZEN_ECD_NAMESPACE_PATTERNS = (r"https?://xbrl\\.sec\\.gov/ecd/\\d{4}",)',
        "test_every_ecd_spelling_in_the_frozen_readers_is_widened"),
    "THE_AMENDMENT_NOTE_ASKS_WITH_THE_FROZEN_PATTERN": (
        NOTE,
        '    governance = all(is_ecd_namespace(fact["concept"][0])',
        '    governance = all(re.fullmatch(r"https?://xbrl\\.sec\\.gov/ecd/[0-9]{4}", fact["concept"][0])',
        "test_no_historical_function_reaches_the_question_without_a_view", DEI),
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
    originals = {target: (REPO / target).read_bytes() for target in (SOURCE, NOTE)}
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
