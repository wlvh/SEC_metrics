"""Undo each part of the awaiting-#28 labelling and require the case written for it to fail.

Usage: python3 injections.py <out.json>

Each injection edits scripts/vnext/historical_coverage.py in place (exactly one
match, must compile), runs the one test class with a fresh bytecode prefix, and
restores the bytes. Zero calls.
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
TARGET = REPO / "scripts/vnext/historical_coverage.py"
CLASS = "tests.vnext.test_historical_coverage.PositionsLeftToIssue28AreCountedApartTest"
INJECTIONS = {
    "ANY_TARGET_FILING_MATCHES": (
        '''        if (awaiting is not None and awaiting["target_accession"]
                == candidate["current_filing"]["accessionNumber"]):''',
        '''        if awaiting is not None:''',
        "test_another_target_filing_is_not_covered"),
    "THE_DECISION_COVERS_EVERY_METRIC_OF_THE_PERIOD": (
        '''                                     awaiting=awaiting.get((company_id, metric_id,
                                                            report_end)))''',
        '''                                     awaiting=awaiting.get((company_id, "D04",
                                                            report_end)))''',
        "test_other_metrics_at_the_newest_period_keep_their_status"),
    "THE_RECORDED_ATTEMPT_IS_DROPPED": (
        '''                      "attempt": attempt,
                      "what_is_not_claimed": (
                          "that #28 has accepted''',
        '''                      "attempt": None,
                      "what_is_not_claimed": (
                          "that #28 has accepted''',
        "test_a_recorded_attempt_stays_attached"),
    "NO_RECORDED_DECISION_IS_NEEDED": (
        '''    _need(isinstance(recorded.get("decisions"), dict)
          and isinstance(recorded["decisions"].get(decision.get("key")), str),
          "COVERAGE_AWAITING_DECISION_NOT_RECORDED")''',
        '''    _need(isinstance(recorded.get("decisions"), dict),
          "COVERAGE_AWAITING_DECISION_NOT_RECORDED")''',
        "test_a_register_must_cite_a_recorded_decision"),
    "A_DUPLICATE_ENTRY_OVERWRITES": (
        '''        _need(key not in entries, "COVERAGE_AWAITING_ENTRY_DUPLICATED")''',
        '''        pass''',
        "test_a_register_must_cite_a_recorded_decision"),
}


def run():
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=1800)
    return done, int(time.time() - started)


def main(out):
    original = TARGET.read_bytes()
    results = {}
    control, seconds = run()
    if control.returncode != 0:
        raise SystemExit("CONTROL_FAILED:\n" + control.stderr[-2000:])
    results["CONTROL"] = {"returncode": 0, "seconds": seconds}
    try:
        for name, (old, new, expected) in INJECTIONS.items():
            text = original.decode("utf-8")
            if text.count(old) != 1:
                raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
            TARGET.write_bytes(text.replace(old, new).encode("utf-8"))
            py_compile.compile(str(TARGET), doraise=True, cfile=tempfile.mktemp())
            done, seconds = run()
            TARGET.write_bytes(original)
            failed = [line.split(" ")[1] for line in done.stderr.splitlines()
                      if line.startswith(("FAIL: ", "ERROR: "))]
            results[name] = {"returncode": done.returncode, "seconds": seconds,
                             "failed_cases": failed, "expected_case": expected,
                             "caught_by_the_case_written_for_it": expected in failed}
    finally:
        TARGET.write_bytes(original)
    if TARGET.read_bytes() != original:
        raise SystemExit("TARGET_NOT_RESTORED")
    results["all_caught"] = all(r["caught_by_the_case_written_for_it"]
                                for k, r in results.items() if k != "CONTROL")
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    print(json.dumps(results, indent=1, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])
