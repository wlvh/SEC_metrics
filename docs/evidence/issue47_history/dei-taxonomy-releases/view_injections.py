"""Fault injections for historical_dei's views: each must be caught by the case written for it.

Usage (from the repository root): python3 docs/evidence/issue47_history/dei-taxonomy-releases/view_injections.py <out.json>

Each fault edits one file in place, runs tests.vnext.test_historical_dei in a
child process with a fresh PYTHONPYCACHEPREFIX (so no bytecode of a fault can
outlive it), and restores the file byte for byte. A fault whose edit does not
match exactly once, or whose edited file does not compile, stops the run before
anything is judged: an injection that cannot reach its target proves nothing.
The control run - no fault - must pass first.
"""
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path.cwd()
DEI = "scripts/vnext/historical_dei.py"
SUITE = "tests.vnext.test_historical_dei"
FAULTS = [
    ("NO_WIDENING", DEI, "            pattern = DEI_NAMESPACE_PATTERN\n",
     "            pattern = pattern\n",
     "test_a_dated_or_quarterly_release_is_read_as_the_same_period"),
    ("WIDEN_EVERYTHING", DEI,
     'DEI_NAMESPACE_PATTERN = r"https?://xbrl\\.sec\\.gov/dei/\\d{4}(?:q[1-4]|-\\d{2}-\\d{2})?"',
     'DEI_NAMESPACE_PATTERN = r"https?://xbrl\\.sec\\.gov/dei/.+"',
     "test_anything_else_is_refused"),
    ("NAMESPACE_READ_ONCE", DEI, "    def view(*args, **kwargs):\n        namespace = dict(vars(module))\n",
     "    snapshot = dict(vars(module))\n\n    def view(*args, **kwargs):\n        namespace = dict(snapshot)\n",
     "test_a_patch_of_the_frozen_module_is_seen_through_the_view"),
    ("CALLEES_NOT_VIEWED", DEI,
     "        for name in names:\n            if name in namespace:\n"
     "                namespace[name] = release_aware(namespace[name])\n",
     "        for name in ():\n            if name in namespace:\n"
     "                namespace[name] = release_aware(namespace[name])\n",
     "test_readers_reached_as_module_globals_are_viewed"),
    ("NO_IMPORT_HOOK", DEI, '            namespace["__builtins__"] = _VIEW_BUILTINS\n',
     "            pass\n",
     "test_a_reader_reached_through_a_local_import_is_viewed"),
    ("NO_CLASS_VIEW", DEI, "        view = _class_view(obj)\n", "        view = obj\n",
     "test_the_fiscal_label_scan_finds_the_same_dei_spans"),
    ("DEFAULTS_NOT_REFUSED", DEI,
     "        if not _is_view(value) and reaches_the_dei_question(value):\n",
     "        if False:\n",
     "test_a_default_argument_on_the_frozen_path_is_refused"),
    ("QUESTION_OTHER_WAYS_ANSWERED_FROZEN", DEI,
     "        if not callable(value) or isinstance(value, type):\n            return value\n",
     "        return value\n",
     "test_the_question_asked_any_other_way_is_refused"),
    ("ATTRIBUTE_CHAINS_NOT_FOLLOWED", DEI, "            for attribute in attributes:\n",
     "            for attribute in ():\n",
     "test_a_direct_reference_is_listed_and_a_view_is_not"),
    ("SUPER_CELL_TREATED_AS_A_CALL", DEI,
     '        if name == "__class__":\n            continue\n', "",
     "test_the_fiscal_label_scan_finds_the_same_dei_spans"),
    ("A_CALL_SITE_LEFT_ON_THE_FROZEN_READER", "scripts/vnext/historical_governance_results.py",
     "resolve_c03, resolve_c04 = release_aware(resolve_c03), release_aware(resolve_c04)\n", "",
     "test_no_historical_function_reaches_the_question_without_a_view"),
]
FAIL_LINE = re.compile(r"^(FAIL|ERROR): (\w+) \(([\w.]+)\)", re.M)


def run_suite():
    with tempfile.TemporaryDirectory() as cache:
        started = time.time()
        completed = subprocess.run([sys.executable, "-m", "unittest", SUITE], cwd=ROOT,
                                   capture_output=True, text=True, timeout=3600,
                                   env={**__import__("os").environ, "PYTHONPYCACHEPREFIX": cache})
    failed = sorted({match.group(2) for match in FAIL_LINE.finditer(completed.stderr)})
    return {"returncode": completed.returncode, "failed_cases": failed,
            "seconds": int(time.time() - started),
            "tail": completed.stderr.strip().splitlines()[-1:] if completed.stderr else []}


def main(out):
    control = run_suite()
    if control["returncode"] != 0:
        raise SystemExit("CONTROL_RUN_FAILED:" + json.dumps(control))
    results = []
    for name, relative, old, new, expected in FAULTS:
        path = ROOT / relative
        original = path.read_bytes()
        text = original.decode("utf-8")
        if text.count(old) != 1:
            raise SystemExit("FAULT_EDIT_DOES_NOT_MATCH_ONCE:" + name)
        edited = text.replace(old, new)
        compile(edited, relative, "exec")
        try:
            path.write_text(edited, encoding="utf-8")
            outcome = run_suite()
        finally:
            path.write_bytes(original)
        if path.read_bytes() != original:
            raise SystemExit("FAULT_NOT_RESTORED:" + name)
        caught_by_its_case = expected in outcome["failed_cases"]
        results.append({"fault": name, "file": relative, "expected_case": expected,
                        "caught": outcome["returncode"] != 0,
                        "caught_by_its_case": caught_by_its_case, **outcome})
        print(name, "caught" if caught_by_its_case else "NOT CAUGHT BY ITS CASE",
              outcome["failed_cases"], flush=True)
    Path(out).write_text(json.dumps({"control": control, "faults": results}, indent=1) + "\n",
                         encoding="utf-8")
    return 0 if all(r["caught_by_its_case"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
