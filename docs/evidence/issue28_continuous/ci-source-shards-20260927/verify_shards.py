"""Check deterministic source sharding without executing saved-source tests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
import run_fast_tests_v2 as runner


complete = runner._selected_tests("source-material", 0, 1)
parts = tuple(runner._selected_tests("source-material", index, 2) for index in (0, 1))
assert complete == runner.SOURCE_TESTS
assert len(complete) == len(set(complete)) == 75
assert set(parts[0]).isdisjoint(parts[1])
assert set(parts[0]) | set(parts[1]) == set(complete)
assert tuple(name for index, name in enumerate(complete) if index % 2 == 0) == parts[0]
assert tuple(name for index, name in enumerate(complete) if index % 2 == 1) == parts[1]
assert runner._selected_tests("fast", 0, 1) == runner.FAST_TESTS

for suite, index, count in (("fast", 1, 2), ("source-material", -1, 2),
                            ("source-material", 2, 2), ("source-material", 0, 0)):
    try:
        runner._selected_tests(suite, index, count)
    except runner.inherited.FastTestError as error:
        assert str(error) == "FAST_TEST_SHARD_INVALID"
    else:
        raise AssertionError((suite, index, count))

original = runner._run_source_case
try:
    runner._run_source_case = lambda name: {"test": name, "return_code": 0, "duration_seconds": 0}
    results = tuple(runner.run_fast_tests(jobs=2, suite="source-material",
                                          shard_index=index, shard_count=2)
                    for index in (0, 1))
    default_result = runner.run_fast_tests(jobs=2, suite="source-material")
finally:
    runner._run_source_case = original
assert all(result["status"] == "PASSED" for result in results)
assert default_result["status"] == "PASSED" and "shard_index" not in default_result
assert set(row["test"] for result in results for row in result["tests"]) == set(complete)
assert len(results[0]["tests"]) == 38 and len(results[1]["tests"]) == 37

print(json.dumps({"full": len(complete), "shards": [len(part) for part in parts],
                  "disjoint_complete": True, "default_unchanged": True,
                  "invalid_shards_rejected": 4, "runner_smoke_mocked": True},
                 sort_keys=True))
