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
        self.assertEqual([], report["duplicate_simple_conditions"])
        self.assertTrue(report["no_duplicate_simple_dispatch_condition"])
        # The map is only useful if it actually found the chains.
        self.assertGreaterEqual(report["dispatch_chains"], 10)
        self.assertIn("issue_28_v13", report["requirement_ids_routed"])

    def test_the_map_sees_set_membership_dispatch_too(self):
        """The first version of this tool had the defect it exists to prevent.

        It walked ``if/elif`` chains only, so it did not see dispatch spelled
        ``requirement_id in {...}`` - and two of this branch's own registration
        changes are that shape. A map that silently omits a form of dispatch is
        worse than no map, because it reads as complete.
        """
        report = _tool().measure(repo_root=REPO_ROOT)
        self.assertTrue(report["membership_sites"])
        routed = {identifier for site in report["membership_sites"]
                  for identifier in site["requirement_ids"]}
        # The fiscal-label coordinates are decided this way in two files, and
        # both must appear or the map is not showing the whole surface.
        self.assertIn("issue_28_v13", routed)
        files = {site["file"] for site in report["membership_sites"]}
        self.assertIn("scripts/vnext/run_store.py", files)
        self.assertIn("scripts/vnext/records.py", files)

    def test_a_compound_condition_is_left_unanalysed_rather_than_called_dead(self):
        """The narrow claim, and why it has to stay narrow.

            if requirement_id == X and mode == "TEXT": ...
            elif requirement_id == X: ...

        is reachable, and comparing bare id strings would report the second
        branch as dead. So a condition that is not a single equality or
        membership test is listed as unanalysed and never counted as a
        duplicate. The tree already contains such conditions, which is why the
        result is named no_duplicate_simple_dispatch_condition and not anything
        about every branch being reachable.
        """
        import tempfile
        from pathlib import Path
        tool = _tool()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts/vnext").mkdir(parents=True)
            (root / "scripts/vnext/run_store.py").write_text(
                'def route(manifest, mode):\n'
                '    if manifest.get("requirement_id") == "issue_28_v13" and mode == "TEXT":\n'
                '        from .a import handler\n'
                '    elif manifest.get("requirement_id") == "issue_28_v13":\n'
                '        from .b import handler\n'
                '    else:\n'
                '        from .c import handler\n'
                '    return handler\n', encoding="utf-8")
            report = tool.measure(repo_root=root)
        self.assertEqual([], report["duplicate_simple_conditions"])
        self.assertTrue(report["no_duplicate_simple_dispatch_condition"])
        self.assertTrue(report["unanalysed_conditions"])
        # And the real tree has some too, so this is not a synthetic concern.
        self.assertTrue(_tool().measure(repo_root=REPO_ROOT)["unanalysed_conditions"])

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
        self.assertFalse(report["no_duplicate_simple_dispatch_condition"])
        dead = report["duplicate_simple_conditions"]
        self.assertTrue(any(entry["requirement_id"] == "issue_28_v14" for entry in dead), dead)
        # The honest tree still passes, so the failure came from the injection.
        self.assertTrue(_tool().measure(
            repo_root=REPO_ROOT)["no_duplicate_simple_dispatch_condition"])


if __name__ == "__main__":
    unittest.main()
