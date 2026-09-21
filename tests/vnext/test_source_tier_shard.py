"""Splitting the saved-source tier must be a partition, not a sample.

The saved-source CI job reached its thirty-five minute cap and was cancelled
mid-step, which reads as "cancelled" rather than as a failing assertion - so a
tier that grows with the issue needs to be splittable. A split that dropped a
case, ran one twice, or moved cases between runs would still look green, and
the shard would then be evidence about something other than the tier.
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "scripts"), str(ROOT)]

import run_fast_tests_v2 as runner  # noqa: E402 - path is set above


def _budget(names):
    return sum(runner.SOURCE_TIMEOUT_OVERRIDES.get(name, runner.SOURCE_TIMEOUT_SECONDS)
               for name in names)


class SourceTierShardTest(unittest.TestCase):
    def test_every_case_is_in_exactly_one_shard(self):
        for shards in (1, 2, 3, 4):
            with self.subTest(shards=shards):
                parts = [runner.source_shard(shard=index, shards=shards)
                         for index in range(1, shards + 1)]
                union = [name for part in parts for name in part]
                self.assertEqual(sorted(runner.SOURCE_TESTS), sorted(union))
                self.assertEqual(len(union), len(set(union)))

    def test_the_same_shard_comes_back_every_time(self):
        """A shard decided by dict order would pass the partition case alone."""
        first = runner.source_shard(shard=2, shards=3)
        self.assertEqual(first, runner.source_shard(shard=2, shards=3))
        self.assertEqual(tuple(sorted(first)), first)

    def test_no_shard_carries_more_than_its_share_plus_one_case(self):
        """The three long cases must not land together.

        Dealing round-robin over the declared order would put them in one
        shard whenever their positions line up, and that shard would hit the
        cap the split exists to avoid. The bound asserted here is the one
        longest-processing-time gives: no shard exceeds the even share by more
        than the heaviest single case.
        """
        heaviest = max(runner.SOURCE_TIMEOUT_OVERRIDES.get(name,
                                                           runner.SOURCE_TIMEOUT_SECONDS)
                       for name in runner.SOURCE_TESTS)
        for shards in (2, 3):
            share = _budget(runner.SOURCE_TESTS) / shards
            for index in range(1, shards + 1):
                with self.subTest(shards=shards, shard=index):
                    self.assertLessEqual(_budget(runner.source_shard(shard=index,
                                                                     shards=shards)),
                                         share + heaviest)

    def test_a_shard_outside_the_split_is_refused(self):
        for shard, shards in ((0, 2), (3, 2), (1, 0), (-1, 2)):
            with self.subTest(shard=shard, shards=shards):
                with self.assertRaises(runner.inherited.FastTestError):
                    runner.source_shard(shard=shard, shards=shards)

    def test_an_unsharded_run_still_covers_the_whole_tier(self):
        """The workflow patch may not be applied, so the old command must work."""
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(0, runner.main(["--suite", "source-material", "--list"]))
        self.assertEqual(len(runner.SOURCE_TESTS),
                         len(json.loads(printed.getvalue())["tests"]))

    def test_a_shard_says_which_part_of_the_tier_it_is(self):
        """Evidence about a shard is not evidence about the tier."""
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(0, runner.main(["--suite", "source-material",
                                             "--shard", "1/2", "--list"]))
        listed = json.loads(printed.getvalue())["tests"]
        self.assertEqual(sorted(runner.source_shard(shard=1, shards=2)), sorted(listed))
        self.assertLess(len(listed), len(runner.SOURCE_TESTS))


if __name__ == "__main__":
    unittest.main()
