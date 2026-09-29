#!/usr/bin/env python3
"""Fault injections for the installer's rule-input generations.

The ledger root's second round stopped before any request: a base merge had
changed a configuration file the parent generation records, the re-mint carried
it, and the installer refused the new bytes because it allowed no difference at
all. ``_install_rule_inputs`` now re-checks within one generation and replaces,
with a recorded transition, across a re-mint. Each injection undoes one part of
that; the case written for it must fail. Same rules as ``batch_injections.py``:
an edit that does not apply exactly once or does not compile stops the script,
the file is restored byte for byte and checked, and every run reads and writes
bytecode only in a fresh directory.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/acquisition-wiring/rule_input_injections.py
"""
import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SESSION = "scripts/vnext/historical_sec_session.py"
SUITE = "tests.vnext.test_historical_sec_session.RuleInputsFollowTheMintedGeneration"
INJECTIONS = [
    {"id": "EVERY_DIFFERENCE_IS_REFUSED", "old": "    if installed == stamp:\n",
     "new": "    if True:\n", "expect": "test_a_new_generation_replaces_the_input_and_records_it",
     "edit": "_install_rule_inputs() re-checks against the root whatever the generation",
     "why": "the refusal that stopped the second round: a re-mint could never reach a ledger root"},
    {"id": "A_CHANGED_INPUT_IS_REPLACED_WITHIN_A_GENERATION", "old": "    if installed == stamp:\n",
     "new": "    if False:\n", "expect": "test_within_one_generation_a_changed_input_is_refused",
     "edit": "_install_rule_inputs() replaces differing inputs even when the stamp matches",
     "why": "a rule input changed under a root of the same generation would be overwritten "
            "without a word instead of refused"},
    {"id": "A_BASELINE_FILE_IS_REPLACED_AS_A_RULE_INPUT",
     "old": ("        _need(relative not in baseline_files or not path.exists(),\n"
             "              \"ISSUE_47_BASELINE_RULE_INPUT_CHANGED:\" + relative)\n"),
     "new": "",
     "expect": "test_a_baseline_file_is_never_replaced_as_a_rule_input",
     "edit": "_install_rule_inputs() replaces a rule input that is also a baseline file",
     "why": "the baseline corpus is governed by its own stamp, which refuses any change; a "
            "transition must not rewrite part of it"},
    {"id": "A_TRANSITION_IS_NOT_RECORDED",
     "old": ("    with (root / RULE_INPUT_TRANSITIONS).open(\"a\", encoding=\"utf-8\") as handle:\n"
             "        handle.write(canonical_json_bytes(value=transition).decode(\"utf-8\")"
             ".rstrip(\"\\n\") + \"\\n\")\n"),
     "new": "",
     "expect": "test_a_new_generation_replaces_the_input_and_records_it",
     "edit": "_install_rule_inputs() replaces inputs without recording the transition",
     "why": "a root whose configuration changed without a record reads as if it had always "
            "held these bytes"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory; see batch_injections.py."""
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def main():
    control = subprocess.run([sys.executable, "-m", "unittest", SUITE], cwd=REPO,
                             env=_isolated_env(), capture_output=True, text=True, timeout=1800)
    if control.returncode != 0:
        print("CONTROL_RUN_FAILED", control.stderr[-800:])
        return 2
    results = []
    for injection in INJECTIONS:
        path = REPO / SESSION
        original = path.read_bytes()
        text = original.decode("utf-8")
        found = text.count(injection["old"])
        if found != 1:
            print("INJECTION_DID_NOT_APPLY", injection["id"], found)
            return 2
        edited = text.replace(injection["old"], injection["new"])
        try:
            compile(edited, str(path), "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
        try:
            path.write_text(edited, encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", SUITE], cwd=REPO,
                                 env=_isolated_env(), capture_output=True, text=True,
                                 timeout=1800)
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        caught = run.returncode != 0 and injection["expect"] in failed
        summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        results.append({"id": injection["id"], "file": SESSION, "edit": injection["edit"],
                        "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary)})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    out = Path(__file__).with_name("rule-input-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_RULE_INPUT_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
