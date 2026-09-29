#!/usr/bin/env python3
"""Fault injections for the export's write order: a failed write must leave the export as it was.

The first live acquisition ran the container's disk full in the middle of an
export, and the order then in use - remove stale row archives, replace files one
by one, write the index last - left an index naming an archive it had deleted.
``_publish`` stages everything new first. Each injection puts back one part of
the old behaviour; the case written for it must fail. Same rules as
``batch_injections.py``: an edit that does not apply exactly once or does not
compile stops the script, the file is restored byte for byte and checked, and
every run reads and writes bytecode only in a fresh directory.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/acquisition-wiring/export_publish_injections.py
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
CARRY = "scripts/vnext/historical_source_export.py"
EXPORT = "tests.vnext.test_historical_sec_session.AnExportCarriesExactlyWhatTheReplayAccepts"
EXPECT = "test_a_write_that_fails_leaves_the_export_already_there"
STAGED = ("    staged = []\n"
          "    try:\n"
          "        for name, data in [*sorted(files.items()), (index_name, index_bytes)]:\n"
          "            temporary = out_dir / (\".\" + name + \".tmp\")\n"
          "            staged.append((temporary, out_dir / name))\n"
          "            _write_temporary(temporary, data)\n"
          "    except BaseException:\n"
          "        for temporary, _ in staged:\n"
          "            temporary.unlink(missing_ok=True)\n"
          "        raise\n"
          "    for temporary, target in staged:\n"
          "        os.replace(temporary, target)\n"
          "    for name in remove:\n"
          "        (out_dir / name).unlink()\n")
INJECTIONS = [
    {"id": "THE_OLD_ORDER_REMOVE_THEN_REPLACE_IN_PLACE", "file": CARRY, "old": STAGED,
     "new": ("    for name in remove:\n"
             "        (out_dir / name).unlink()\n"
             "    for name, data in [*sorted(files.items()), (index_name, index_bytes)]:\n"
             "        _write_temporary(out_dir / name, data)\n"),
     "why": "the order the disk-full export used: a failed write leaves an index naming an "
            "archive already removed, or a half-written archive in place",
     "edit": "_publish() removes the stale archives first and writes every file in place"},
    {"id": "A_FAILED_STAGING_LEAVES_ITS_FILES", "file": CARRY,
     "old": ("    except BaseException:\n"
             "        for temporary, _ in staged:\n"
             "            temporary.unlink(missing_ok=True)\n"
             "        raise\n"),
     "new": "    except BaseException:\n        raise\n",
     "why": "staged files left behind by a failed export would sit in the directory the "
            "branch carries",
     "edit": "_publish() no longer removes what it staged when a write fails"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory; see batch_injections.py."""
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def main():
    control = subprocess.run([sys.executable, "-m", "unittest", EXPORT], cwd=REPO,
                             env=_isolated_env(), capture_output=True, text=True, timeout=1800)
    if control.returncode != 0:
        print("CONTROL_RUN_FAILED", control.stderr[-800:])
        return 2
    results = []
    for injection in INJECTIONS:
        path = REPO / injection["file"]
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
            run = subprocess.run([sys.executable, "-m", "unittest", EXPORT], cwd=REPO,
                                 env=_isolated_env(), capture_output=True, text=True,
                                 timeout=1800)
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        caught = run.returncode != 0 and EXPECT in failed
        summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        results.append({"id": injection["id"], "file": injection["file"],
                        "edit": injection["edit"], "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT", "expected_case": EXPECT,
                        "failed_cases": failed, "suite_result": " ".join(summary)})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    out = Path(__file__).with_name("export-publish-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_EXPORT_PUBLISH_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
