"""The minted ``issue_47_v1`` snapshot has to match the tree it describes.

This is not a style check. ``requirements/issue_47_v1/baseline_manifest.json``
records the sha256 of twelve rule files, and
``load_profile_requirement_snapshot`` verifies those bytes against both the data
root and the installed code root. A rule file that changes without a re-mint
therefore produces a snapshot that cannot install, and nothing says so until an
installation is attempted.

It has already happened twice on this branch. Two commits changed
``historical_package.py``, ``historical_run.py`` and ``historical_projection.py``
and left the snapshot behind, because the only thing guarding it was a sentence
in a README asking the reader to run ``--check``. A sentence is not a guard.
"""
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT


def _tool():
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools import vnext_mint_historical_requirement as tool
    return tool


class HistoricalRequirementSnapshotTest(unittest.TestCase):
    def test_the_committed_snapshot_matches_the_current_tree(self):
        """Fails the moment a rule file moves without ``--mint`` being re-run."""
        self.assertEqual(0, _tool().main(["--check"]))

    def test_one_changed_rule_byte_is_enough_to_fail_the_check(self):
        """And the check is byte-sensitive rather than a file-existence test.

        One rule file is made to hash differently; nothing else moves. The
        manifest is then the only file that can differ, and it must.
        """
        tool = _tool()
        target = "scripts/vnext/historical_projection.py"
        self.assertIn(target, tool.NEW_RULE_FILES)
        real = tool.sha256_file

        def drifted(*, path):
            digest = real(path=path)
            return "sha256:" + "0" * 64 if path == REPO_ROOT / target else digest

        with patch.object(tool, "sha256_file", drifted):
            with self.assertRaises(SystemExit) as caught:
                tool.main(["--check"])
        self.assertIn("baseline_manifest.json", str(caught.exception))
        # The honest tree still passes, so the failure came from the drift and
        # not from the check having been left broken.
        self.assertEqual(0, tool.main(["--check"]))


if __name__ == "__main__":
    unittest.main()
