"""A Requirement is registered in many places, so read all of them mechanically.

This branch estimated the registration cost by reading one dispatch chain at a
time and was wrong repeatedly, which suggested the wrong lesson: that only
running the code can establish the cost. The counter-example arrived from a
careful read of the patch. ``0a811d2`` carried a stray

    elif manifest.get("requirement_id") == "issue_47_v1":

sitting after the branch that already matched that id, inside a patch to a
frozen-authority file. It is unreachable, so it changes no behaviour, so a
complete end-to-end Run passed with it in place. Execution could not have found
it; exhaustive reading can, and that is what this pins.
"""
import unittest

from tests.vnext.common import REPO_ROOT


def _tool():
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools import vnext_dispatch_map as tool
    return tool


class RequirementDispatchMapTest(unittest.TestCase):
    def test_no_dispatch_chain_tests_one_requirement_id_twice(self):
        report = _tool().measure(repo_root=REPO_ROOT)
        self.assertEqual([], report["unreachable_branches"])
        self.assertTrue(report["every_branch_reachable"])
        # The map is only useful if it actually found the chains.
        self.assertGreaterEqual(report["dispatch_chains"], 10)
        self.assertIn("issue_28_v13", report["requirement_ids_routed"])

    def test_the_check_catches_a_second_branch_on_an_id_already_matched(self):
        """And it is byte-level, not a spelling convention.

        A duplicate is injected into a copy of the tree rather than the tree, so
        the negative proves the gate rather than the absence of a defect today.
        """
        import shutil
        import tempfile
        tool = _tool()
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            root = Path(directory)
            (root / "scripts/vnext").mkdir(parents=True)
            source = (REPO_ROOT / "scripts/vnext/run_store.py").read_text(encoding="utf-8")
            anchor = '    if manifest.get("requirement_id") == "issue_28_v14":'
            self.assertIn(anchor, source)
            broken = source.replace(
                anchor,
                '    if manifest.get("requirement_id") == "issue_28_v14":\n'
                '        pass\n'
                '    elif manifest.get("requirement_id") == "issue_28_v14":',
                1)
            (root / "scripts/vnext/run_store.py").write_text(broken, encoding="utf-8")
            for name in ("records.py", "requirement_profile.py"):
                shutil.copy2(REPO_ROOT / "scripts/vnext" / name, root / "scripts/vnext" / name)
            report = tool.measure(repo_root=root)
        self.assertFalse(report["every_branch_reachable"])
        dead = report["unreachable_branches"]
        self.assertTrue(any(entry["requirement_id"] == "issue_28_v14" for entry in dead), dead)
        # The honest tree still passes, so the failure came from the injection.
        self.assertTrue(_tool().measure(repo_root=REPO_ROOT)["every_branch_reachable"])


if __name__ == "__main__":
    unittest.main()
