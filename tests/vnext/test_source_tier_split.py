"""The saved-source tier's split across its CI jobs.

The split is by measured CI seconds, heaviest first to the lighter shard. It is
only useful while its weights name real cases: a weight whose key was renamed
away silently counts that case at the default, which is how a split drifts
back to the imbalance it was introduced to fix.
"""
import importlib.util
import sys
import unittest

from tests.vnext.common import REPO_ROOT as ROOT

sys.path.insert(0, str(ROOT / "tools"))
_SPEC = importlib.util.spec_from_file_location("run_fast_tests_v2", ROOT / "tools/run_fast_tests_v2.py")
RUNNER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RUNNER)


def _weight(name):
    return RUNNER.SOURCE_CI_SECONDS.get(name, RUNNER.SOURCE_DEFAULT_CI_SECONDS)


class TheSplitCoversTheTierOnceTest(unittest.TestCase):
    def test_four_shards_cover_the_complete_tier_once(self):
        shards = [RUNNER._selected_tests("source-material", index, 4) for index in range(4)]
        flattened = [case for shard in shards for case in shard]
        self.assertEqual(sorted(RUNNER.SOURCE_TESTS), sorted(flattened))
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_every_case_is_in_exactly_one_shard(self):
        shards = [RUNNER._selected_tests("source-material", index, 2) for index in (0, 1)]
        self.assertEqual(set(), set(shards[0]) & set(shards[1]))
        self.assertEqual(sorted(RUNNER.SOURCE_TESTS), sorted(shards[0] + shards[1]))

    def test_the_split_is_the_same_on_every_job(self):
        self.assertEqual(RUNNER._selected_tests("source-material", 1, 2),
                         RUNNER._selected_tests("source-material", 1, 2))

    def test_every_weight_names_a_case_in_the_tier(self):
        self.assertEqual(set(), set(RUNNER.SOURCE_CI_SECONDS) - set(RUNNER.SOURCE_TESTS))

    def test_each_shard_runs_its_heaviest_cases_first(self):
        for index in (0, 1):
            weights = [_weight(name) for name in RUNNER._selected_tests("source-material", index, 2)]
            self.assertEqual(sorted(weights, reverse=True), weights)

    def test_the_shards_differ_by_less_than_the_heaviest_case(self):
        loads = [sum(map(_weight, RUNNER._selected_tests("source-material", index, 2)))
                 for index in (0, 1)]
        self.assertLessEqual(abs(loads[0] - loads[1]), max(map(_weight, RUNNER.SOURCE_TESTS)))

    def test_the_fast_suite_is_not_split(self):
        self.assertEqual(RUNNER.FAST_TESTS, RUNNER._selected_tests("fast", 0, 1))
        with self.assertRaises(RUNNER.inherited.FastTestError):
            RUNNER._selected_tests("fast", 0, 2)


if __name__ == "__main__":
    unittest.main()
