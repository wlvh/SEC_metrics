"""Undo each part of the older lodging introduction forms and require the case written for it to fail.

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
SOURCE = "scripts/vnext/historical_lodging_results.py"
CASES = "tests.vnext.test_historical_lodging_introduction"
MODULES = (CASES,)

# name: (file, old, new, the case written for it[, the module that holds it])
INJECTIONS = {
    "ANY_REFUSAL_TRIES_THE_OLDER_FORMS": (
        SOURCE,
        '        if not message.startswith("LODGING_MATCHING_TABLE_NOT_UNIQUE:") \\\n'
        '                or INTRODUCTION_REFUSAL not in message:\n',
        '        if not message.startswith("LODGING_MATCHING_TABLE_NOT_UNIQUE:"):\n',
        "test_another_refusal_is_raised_unchanged_and_the_older_forms_are_not_tried"),
    "THE_OLDER_FORMS_ARE_ALWAYS_USED": (
        SOURCE,
        '        return inspect_lodging_table_source(**arguments)\n    except LodgingSourceError as error:',
        '        return inspect_older_introduction(**arguments)\n    except LodgingSourceError as error:',
        "test_a_report_the_frozen_inspector_accepts_is_unchanged"),
    "A_THIRD_FORM_IS_ACCEPTED": (
        SOURCE,
        '"The following (?:table presents|tables present) "',
        '"The following (?:tables? presents?) "',
        "test_nothing_else_is_accepted"),
    "THE_COMMA_IS_NOT_OPTIONAL": (
        SOURCE,
        '"(?P<year>[0-9]{4}),? and (?P=year)"',
        '"(?P<year>[0-9]{4}), and (?P=year)"',
        "test_the_older_pattern_accepts_the_three_printed_forms_and_the_frozen_one_only_the_newest"),
    "THE_POLICY_HASH_IS_THE_FROZEN_ONE": (
        SOURCE,
        '    frozen_lodging.inspect_lodging_table_source, POLICY=OLDER_INTRODUCTION_POLICY,\n'
        '    _source_context=_OLDER_CONTEXT)',
        '    frozen_lodging.inspect_lodging_table_source,\n    _source_context=_OLDER_CONTEXT)',
        "test_the_older_reports_resolve_one_table_under_the_older_forms"),
    "A_REPLACEMENT_MAY_MISS": (
        SOURCE,
        '        if pattern.count(old) != 1:\n            raise ValueError',
        '        if False:\n            raise ValueError',
        "test_a_frozen_pattern_without_the_replaced_text_stops_the_successor"),
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
    originals = {target: (REPO / target).read_bytes() for target in (SOURCE,)}
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
