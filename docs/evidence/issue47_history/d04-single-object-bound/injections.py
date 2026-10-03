"""Undo each part of D04's wider single-object bound and require the case written for it to fail.

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
SOURCE = "scripts/vnext/historical_semantic_source.py"
CASES = "tests.vnext.test_historical_semantic_bound"
MODULES = (CASES,)

# name: (file, old, new, the case written for it[, the module that holds it])
INJECTIONS = {
    "ANY_FROZEN_REFUSAL_IS_WIDENED": (
        SOURCE,
        """        if str(error) != SINGLE_OBJECT_REFUSAL:
            raise""",
        """        if False:
            raise""",
        "test_another_frozen_refusal_is_raised_unchanged"),
    "EVERY_DOCUMENT_TAKES_THE_WIDER_BOUND": (
        SOURCE,
        """        return (*group(frozen_semantic._group, frozen_semantic._native_units), {})""",
        """        raise frozen_semantic.SemanticSourceError(SINGLE_OBJECT_REFUSAL)""",
        "test_it_is_the_frozen_grouping"),
    "THE_WIDER_BOUND_IS_NOT_RECORDED": (
        SOURCE,
        """    return visible, native, coverage, {"single_object_bound": {""",
        """    return visible, native, coverage, {} if True else {"single_object_bound": {""",
        "test_the_document_says_which_bound_admitted_it_and_names_the_unit"),
    "THE_UNIT_LIMIT_IS_WIDENED_TOO": (
        SOURCE,
        """                        "max_single_object_payload_bytes": REQUEST_PAYLOAD_BYTES}""",
        """                        "max_single_object_payload_bytes": REQUEST_PAYLOAD_BYTES,
                        "max_unit_payload_bytes": REQUEST_PAYLOAD_BYTES}""",
        "test_the_successor_policy_changes_one_number"),
    "THE_NATIVE_UNITS_KEEP_THE_FROZEN_GROUPING": (
        SOURCE,
        """_WIDER_NATIVE_UNITS = release_aware_with(frozen_semantic._native_units, _group=_WIDER_GROUP)""",
        """_WIDER_NATIVE_UNITS = frozen_semantic._native_units""",
        "test_the_successor_policy_changes_one_number"),
    "NO_UNIT_OVER_THE_FROZEN_BOUND_IS_NAMED": (
        SOURCE,
        """            for u in visible + native if u["payload_bytes"] > frozen_bound]
    _need(over, "HISTORICAL_SEMANTIC_WIDER_BOUND_ADMITTED_NOTHING_OVER_THE_FROZEN_ONE")""",
        """            for u in visible + native if u["payload_bytes"] > 10 * frozen_bound]""",
        "test_the_document_says_which_bound_admitted_it_and_names_the_unit"),
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
