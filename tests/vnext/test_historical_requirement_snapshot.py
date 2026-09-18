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


class ExecutionAuthorityClosureTest(unittest.TestCase):
    """An authority that does not name what its own code imports is incomplete.

    The point is not tidiness. A delivery assembled from the execution
    authority - which is what the list is for - has to be able to import the
    modules it names. ``requirement_profile.py`` is in the list and imports
    ``requirement_profile_v10`` through ``v14`` at module scope; ``v11`` was the
    only one of the five the parent's list omits, so anything built from the
    authority alone fails on the first Requirement load.

    This was found by building such a package, not by reading the list.
    """

    def test_the_historical_authority_names_everything_it_imports(self):
        import sys
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from tools.vnext_authority_closure import measure
        report = measure(repo_root=REPO_ROOT, requirement_id="issue_47_v1")
        self.assertEqual([], report["required_to_import_but_not_named"])
        self.assertTrue(report["authority_is_import_complete"])
        self.assertEqual(report["authority_python_modules"], report["module_scope_closure"])

    def test_the_inherited_list_is_the_one_that_was_short(self):
        """Pins where the gap came from, so the fix is not mistaken for noise.

        issue_28_v13 is not modified by this branch, and this asserts its state
        rather than changing it: the omission is inherited, and issue_47_v1
        closes it for its own generation only.
        """
        import sys
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from tools.vnext_authority_closure import measure
        parent = measure(repo_root=REPO_ROOT, requirement_id="issue_28_v13")
        self.assertEqual(["scripts/vnext/requirement_profile_v11.py"],
                         parent["required_to_import_but_not_named"])


if __name__ == "__main__":
    unittest.main()
