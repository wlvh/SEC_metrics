"""Profile Issue #47's LIVE egress class: where a class fixture and a send spend their time.

Run from the root of a runtime tree that carries both patches (minted), with a
private bytecode cache, as the owner's runner and verify.py run:

    PYTHONPYCACHEPREFIX=$(mktemp -d) python3 <this file> <out-dir> [--profile] [case ...]

Imports nothing of the checkout before the suite module: that module refuses a
process that already holds checkout code (it must load the owner's runner
first). Writes, per case, the wall time; with --profile, one cProfile file for
the whole run and a text summary of the functions the send path repeats.
"""
import cProfile
import json
import pstats
import sys
import time
import unittest
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
PROFILE = "--profile" in sys.argv[2:]
CASES = [name for name in sys.argv[2:] if not name.startswith("--")]
MODULE = "tests.vnext.test_historical_model_egress"
CLASS = "TheLivePathSendsThePlannedBytesOnceThroughTheControlledOpener"

sys.path.insert(0, str(Path.cwd()))
started = time.perf_counter()
times, marks = {}, {"process_start": 0.0}


class Timed(unittest.TextTestResult):
    def startTest(self, test):
        marks.setdefault("first_case_start", time.perf_counter() - started)
        self._case_started = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        times[test.id().rsplit(".", 1)[1]] = round(time.perf_counter() - self._case_started, 2)
        super().stopTest(test)


def run():
    loader = unittest.defaultTestLoader
    module = __import__(MODULE, fromlist=["_"])
    marks["module_imported"] = time.perf_counter() - started
    if CASES:
        suite = unittest.TestSuite(loader.loadTestsFromName(CLASS + "." + name, module) for name in CASES)
    else:
        suite = loader.loadTestsFromName(CLASS, module)
    result = unittest.TextTestRunner(resultclass=Timed, verbosity=2).run(suite)
    marks["run_end"] = time.perf_counter() - started
    return result


if PROFILE:
    profiler = cProfile.Profile()
    result = profiler.runcall(run)
    profiler.dump_stats(str(OUT / "live.prof"))
else:
    result = run()

summary = {"cases": times, "marks": {k: round(v, 2) for k, v in marks.items()},
           "fixture_seconds": round(marks.get("first_case_start", 0) - marks.get("module_imported", 0), 2),
           "ok": result.wasSuccessful(), "errors": len(result.errors), "failures": len(result.failures),
           "profiled": PROFILE}
(OUT / "timings.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=1))

if PROFILE:
    watched = ("pinned_native_source", "prepare_historical_d04_semantic_source", "native_source",
               "requests_from_source", "reconstruct_requests", "measured_groups", "measure_request",
               "render_prompt", "_check", "validate", "_validate_single", "verify_ordinary_source_proofs",
               "loaded_code_holds", "model_allowance", "verify_model_wiring", "build_plan",
               "execute_historical_semantic", "planned_request_digests", "prepare_historical_requests",
               "prepare_successor_invocation_authority", "encode", "strict_json_loads",
               "canonical_json_bytes", "content_hash", "sha256_bytes", "request_body",
               "evidence_json_bytes", "live_model_ledger")
    stats = pstats.Stats(str(OUT / "live.prof"))
    rows = []
    for (path, line, name), (primitive, total_calls, own, cumulative, _callers) in stats.stats.items():
        if name in watched:
            rows.append({"function": name, "file": path.rsplit("/", 2)[-1] if "/" in path else path,
                         "line": line, "calls": total_calls, "own_seconds": round(own, 2),
                         "cumulative_seconds": round(cumulative, 2)})
    rows.sort(key=lambda row: -row["cumulative_seconds"])
    (OUT / "watched.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    text = OUT / "top-cumulative.txt"
    with text.open("w", encoding="utf-8") as handle:
        pstats.Stats(str(OUT / "live.prof"), stream=handle).sort_stats("cumulative").print_stats(80)
    with (OUT / "top-own.txt").open("w", encoding="utf-8") as handle:
        pstats.Stats(str(OUT / "live.prof"), stream=handle).sort_stats("tottime").print_stats(40)
    for row in rows[:30]:
        print(row)
