"""A batch derives the Requirement snapshot and the pinned inputs once per state.

historical_derivation_memo.derived_once_per_state() keeps a frozen function's
answer for as long as nothing it reads has changed: the tree the call names,
the runtime tree and the environment. These cases are about how that could go
wrong without failing: answering after a file was rewritten in place, after a
file was added, after the runtime tree or the environment changed; keeping an
answer that read something the key does not cover; remembering a refusal;
handing out an answer a caller can change; answering a call it cannot key;
and leaving anything replaced once the block is over.

The first classes drive the memo with a stand-in function over temporary
trees, so each case is fast and says exactly what was read. The last class
calls the five real functions on this repository's own saved sources: each
answers the same twice without the memo, the memo's answer is the frozen one,
and none of them reads anything outside its key. Zero calls.
"""
import copy
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext import historical_annual_input
from vnext import historical_derivation_memo as memo
from vnext import historical_results
from vnext import historical_risk_results
from vnext import historical_run
from vnext import historical_text_input
from vnext import requirements
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_source_authority import ROOT

FROZEN = {"load_requirement_snapshot": requirements.load_requirement_snapshot,
          "prepare_historical_run_input": historical_results.prepare_historical_run_input,
          "prepare_historical_annual_input":
              historical_annual_input.prepare_historical_annual_input,
          "prepare_historical_business_text_input": prepare_historical_business_text_input,
          "prepare_text_sources": historical_risk_results.prepare_text_sources}
COMPANY = "marriott_international"
REPORT_END = "2025-12-31"


class _Reader:
    """A stand-in frozen function: reads ``value.txt`` under ``repo_root``."""

    def __init__(self, extra=None):
        self.calls = 0
        self.extra = extra

    def __call__(self, *, repo_root, label="a"):
        self.calls += 1
        if self.extra is not None:
            self.extra()
        return {"label": label, "text": (Path(repo_root) / "value.txt").read_text(),
                "rows": [1, 2, 3]}


class _Trees(unittest.TestCase):
    def setUp(self):
        memo._install_hook()
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.tree = self.base / "tree"
        self.runtime = self.base / "runtime"
        self.tree.mkdir()
        self.runtime.mkdir()
        (self.tree / "value.txt").write_text("first")
        (self.runtime / "code.py").write_text("code")
        self.report = []

    def memo_of(self, reader, name="prepare_historical_annual_input"):
        return memo._memo(name, reader, os.path.realpath(self.runtime), self.report)


class OneAnswerPerTreeState(_Trees):
    def test_an_unchanged_tree_is_answered_from_the_first_call(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        first = memoized(repo_root=self.tree)
        second = memoized(repo_root=self.tree)
        self.assertEqual(first, second)
        self.assertEqual(reader.calls, 1)
        self.assertEqual([item["outcome"] for item in self.report], ["COMPUTED", "ANSWERED"])

    def test_a_file_rewritten_in_place_is_derived_again(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        path = self.tree / "value.txt"
        status = path.stat()
        path.write_text("other")
        # Same size, and the modification time put back: only the change
        # time still says the bytes moved.
        os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns))
        self.assertEqual(path.stat().st_size, status.st_size)
        self.assertEqual(memoized(repo_root=self.tree)["text"], "other")
        self.assertEqual(reader.calls, 2)

    def test_a_new_file_is_derived_again(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        (self.tree / "new").mkdir()
        (self.tree / "new" / "file").write_text("x")
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)

    def test_the_runtime_tree_is_in_the_key(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        (self.runtime / "code.py").write_text("changed")
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)

    def test_the_environment_is_in_the_key(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        with patch.dict(os.environ, {"ISSUE47_DERIVATION_MEMO_CASE": "1"}):
            memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)

    def test_two_arguments_never_share_an_answer(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        self.assertEqual(memoized(repo_root=self.tree, label="a")["label"], "a")
        self.assertEqual(memoized(repo_root=self.tree, label="b")["label"], "b")
        other = self.base / "other"
        other.mkdir()
        (other / "value.txt").write_text("elsewhere")
        self.assertEqual(memoized(repo_root=other, label="a")["text"], "elsewhere")
        self.assertEqual(reader.calls, 3)

    def test_a_tree_holding_a_link_is_not_keyed(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        (self.tree / "link").symlink_to(self.base)
        memoized(repo_root=self.tree)
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)
        self.assertEqual([item["outcome"] for item in self.report], ["NOT_KEYED", "NOT_KEYED"])

    def test_an_answer_that_read_outside_its_key_is_not_remembered(self):
        outside = self.base / "outside.txt"
        outside.write_text("not in the key")
        reader = _Reader(extra=outside.read_text)
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)
        self.assertEqual(self.report[0]["outcome"], "COMPUTED_NOT_REMEMBERED")
        self.assertIn(os.path.realpath(outside), self.report[0]["read_outside_the_key"])

    def test_a_listing_outside_its_key_is_not_remembered(self):
        reader = _Reader(extra=lambda: os.listdir(self.base))
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)

    def test_an_answer_that_started_a_process_is_not_remembered(self):
        reader = _Reader(extra=lambda: subprocess.run([sys.executable, "-c", "pass"], check=True))
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)
        self.assertEqual(self.report[0]["outcome"], "COMPUTED_NOT_REMEMBERED")

    def test_a_refusal_is_not_remembered(self):
        attempts = []

        def refuse_once(*, repo_root):
            attempts.append(1)
            if len(attempts) == 1:
                raise ValueError("refused")
            return {"ok": True}
        memoized = self.memo_of(refuse_once)
        with self.assertRaises(ValueError):
            memoized(repo_root=self.tree)
        self.assertEqual(memoized(repo_root=self.tree), {"ok": True})
        self.assertEqual(len(attempts), 2)

    def test_the_answer_is_a_copy(self):
        memoized = self.memo_of(_Reader())
        first = memoized(repo_root=self.tree)
        first["rows"].append(4)
        second = memoized(repo_root=self.tree)
        self.assertEqual(second["rows"], [1, 2, 3])
        second["rows"].append(5)
        self.assertEqual(memoized(repo_root=self.tree)["rows"], [1, 2, 3])

    def test_arguments_that_are_not_plain_data_go_to_the_frozen_function(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree, label=1.5)
        memoized(repo_root=self.tree, label=1.5)
        memoized(repo_root=self.tree, label=object())
        self.assertEqual(reader.calls, 3)

    def test_a_call_inside_its_own_computation_goes_to_the_frozen_function(self):
        holder = {}
        inner_calls = []

        def recursive(*, repo_root, depth=0):
            if depth == 0:
                return {"outer": True, "inner": holder["memo"](repo_root=repo_root, depth=1)}
            inner_calls.append(1)
            return {"inner": True}
        holder["memo"] = self.memo_of(recursive)
        holder["memo"](repo_root=self.tree)
        holder["memo"](repo_root=self.tree)
        # One outer computation; its inner call went to the frozen function
        # instead of being keyed, and the second outer call was answered.
        self.assertEqual(len(inner_calls), 1)
        self.assertEqual([item["outcome"] for item in self.report], ["COMPUTED", "ANSWERED"])

    def test_an_answer_handed_out_for_a_foreign_tree_spoils_the_outer_answer(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        (foreign / "value.txt").write_text("foreign")
        inner = self.memo_of(_Reader(), name="prepare_historical_run_input")
        inner(repo_root=foreign)  # remembered, so the next call reads nothing
        outer_reader = _Reader(extra=lambda: inner(repo_root=foreign))
        outer = self.memo_of(outer_reader)
        outer(repo_root=self.tree)
        outer(repo_root=self.tree)
        self.assertEqual(outer_reader.calls, 2)
        spoiled = [item for item in self.report if item["outcome"] == "COMPUTED_NOT_REMEMBERED"]
        self.assertTrue(spoiled)
        self.assertTrue(any(entry.startswith("memo:") for item in spoiled
                            for entry in item["read_outside_the_key"]))

    def test_a_forgotten_state_is_derived_again_not_answered_wrong(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        with patch.object(memo, "MAX_ENTRIES", 2):
            for label in ("a", "b", "c"):
                memoized(repo_root=self.tree, label=label)
            self.assertEqual(memoized(repo_root=self.tree, label="a")["label"], "a")
        self.assertEqual(reader.calls, 4)

    def test_bytes_are_keyed_by_their_content(self):
        seen = []

        def parse(*, repo_root, raw):
            seen.append(raw)
            return {"length": len(raw)}
        memoized = self.memo_of(parse)
        memoized(repo_root=self.tree, raw=b"abc")
        memoized(repo_root=self.tree, raw=bytes(bytearray(b"abc")))
        memoized(repo_root=self.tree, raw=b"abd")
        # Equal bytes in another object are the same argument; other bytes of
        # the same length are not.
        self.assertEqual(seen, [b"abc", b"abd"])

    def test_a_preparation_handed_its_bytes_is_keyed_on_the_runtime_tree(self):
        runtime = os.path.realpath(self.runtime)
        self.assertEqual(memo._trees_of("prepare_text_sources", {}, runtime), runtime)

    def test_the_snapshot_s_tree_is_its_repository_root(self):
        runtime = os.path.realpath(self.runtime)
        self.assertEqual(memo._trees_of("load_requirement_snapshot",
                                        {"snapshot_dir": self.tree / "requirements" / "x"},
                                        runtime),
                         os.path.realpath(self.tree))
        # A snapshot copied anywhere else has no root this memo can name.
        self.assertIsNone(memo._trees_of("load_requirement_snapshot",
                                         {"snapshot_dir": self.tree / "copy" / "x"}, runtime))


class TheKeyAndTheCheckHoldAtTheirEdges(_Trees):
    """Edges an independent review found no case for, or found reachable."""

    def test_a_walk_that_fails_goes_to_the_frozen_function(self):
        # Another worker's temporary file removed while the walk read it.
        reader = _Reader()
        memoized = self.memo_of(reader)
        with patch.object(memo, "_fingerprint", side_effect=FileNotFoundError("gone")):
            self.assertEqual(memoized(repo_root=self.tree)["text"], "first")
        self.assertEqual(self.report[0], {"function": "prepare_historical_annual_input",
                                          "outcome": "NOT_KEYED",
                                          "walk_failed": "FileNotFoundError"})
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)
        self.assertEqual(self.report[1]["outcome"], "COMPUTED")

    def test_a_named_tree_that_does_not_exist_gets_the_frozen_refusal(self):
        def refuse(*, repo_root):
            if not Path(repo_root).exists():
                raise LookupError("NAMED_REFUSAL")
            return {}
        with self.assertRaisesRegex(LookupError, "NAMED_REFUSAL"):
            self.memo_of(refuse)(repo_root=self.base / "missing")

    def test_an_answer_that_cannot_be_copied_is_returned_and_not_kept(self):
        calls = []

        def answer(*, repo_root):
            calls.append(1)
            return {"module": os}
        memoized = self.memo_of(answer)
        self.assertIs(memoized(repo_root=self.tree)["module"], os)
        memoized(repo_root=self.tree)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.report[0]["outcome"], "COMPUTED_NOT_REMEMBERED")
        self.assertIn("answer_not_copyable", self.report[0])

    def test_the_runtime_git_directory_is_keyed_apart_from_its_objects(self):
        # The trust journal and the assessment registrations live under .git.
        (self.runtime / ".git" / "objects").mkdir(parents=True)
        (self.runtime / ".git" / "objects" / "pack").write_text("a")
        (self.runtime / ".git" / "journal").write_text("a")
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree)
        (self.runtime / ".git" / "objects" / "pack").write_text("b")
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 1)
        (self.runtime / ".git" / "journal").write_text("b")
        memoized(repo_root=self.tree)
        self.assertEqual(reader.calls, 2)

    def test_true_and_one_are_two_arguments(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree, label=True)
        memoized(repo_root=self.tree, label=1)
        self.assertEqual(reader.calls, 2)

    def test_a_dict_whose_keys_are_not_text_goes_to_the_frozen_function(self):
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree, label={1: "a"})
        memoized(repo_root=self.tree, label={1: "a"})
        self.assertEqual(reader.calls, 2)
        self.assertEqual([], self.report)

    def test_a_path_through_a_retargeted_link_is_another_argument(self):
        for name in ("a", "b"):
            (self.base / name).mkdir()
        link = self.base / "current"
        link.symlink_to(self.base / "a")
        reader = _Reader()
        memoized = self.memo_of(reader)
        memoized(repo_root=self.tree, label=link)
        link.unlink()
        link.symlink_to(self.base / "b")
        memoized(repo_root=self.tree, label=link)
        self.assertEqual(reader.calls, 2)

    def test_a_file_read_through_a_descriptor_opened_in_the_key_is_remembered(self):
        def read(*, repo_root):
            descriptor = os.open(Path(repo_root) / "value.txt", os.O_RDONLY)
            with open(descriptor, encoding="utf-8") as handle:
                return {"text": handle.read()}
        calls = []

        def counted(*, repo_root):
            calls.append(1)
            return read(repo_root=repo_root)
        memoized = self.memo_of(counted)
        memoized(repo_root=self.tree)
        self.assertEqual(memoized(repo_root=self.tree), {"text": "first"})
        self.assertEqual(len(calls), 1)

    def test_a_relative_read_is_not_remembered(self):
        # The working directory is not in the key: the same relative name can
        # be another file next time.
        reader = _Reader(extra=lambda: Path("value.txt").read_text())
        memoized = self.memo_of(reader)
        cwd = os.getcwd()
        os.chdir(self.tree)
        try:
            memoized(repo_root=self.tree)
            memoized(repo_root=self.tree)
        finally:
            os.chdir(cwd)
        self.assertEqual(reader.calls, 2)
        self.assertIn("relative:value.txt", self.report[0]["read_outside_the_key"])

    def test_a_nested_call_on_a_foreign_tree_it_cannot_key_spoils_the_outer_answer(self):
        # The inner call only checks existence - no audit event - and its tree
        # holds a link, so it is not keyed; the outer answer still depended on
        # a tree outside its key.
        foreign = self.base / "foreign"
        foreign.mkdir()
        (foreign / "link").symlink_to(self.base)

        def exists(*, repo_root):
            return {"exists": (Path(repo_root) / "value.txt").exists()}
        inner = self.memo_of(exists, name="prepare_historical_run_input")
        outer_reader = _Reader(extra=lambda: inner(repo_root=foreign))
        outer = self.memo_of(outer_reader)
        outer(repo_root=self.tree)
        outer(repo_root=self.tree)
        self.assertEqual(outer_reader.calls, 2)
        self.assertTrue(any(entry.startswith("memo:prepare_historical_run_input:")
                            for item in self.report
                            for entry in item.get("read_outside_the_key", ())))

    def test_the_interpreter_s_trees_are_its_library_paths_not_its_prefix(self):
        trees = memo._interpreter_trees()
        library = {os.path.realpath(path) for path in
                   (sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["purelib"])}
        self.assertTrue(library <= set(trees))
        prefix = os.path.realpath(sys.prefix)
        if prefix not in library:
            self.assertNotIn(prefix, trees)


class TheBlockSwapsTheFiveFunctions(unittest.TestCase):
    def test_every_binding_is_swapped_and_put_back(self):
        with memo.derived_once_per_state():
            self.assertIsNot(historical_run.load_requirement_snapshot,
                             FROZEN["load_requirement_snapshot"])
            self.assertIsNot(historical_run.prepare_historical_run_input,
                             FROZEN["prepare_historical_run_input"])
            self.assertIsNot(historical_results.prepare_historical_annual_input,
                             FROZEN["prepare_historical_annual_input"])
            self.assertIsNot(requirements.load_requirement_snapshot,
                             FROZEN["load_requirement_snapshot"])
            self.assertIsNot(historical_risk_results.prepare_text_sources,
                             FROZEN["prepare_text_sources"])
            self.assertIsNot(historical_text_input.prepare_historical_business_text_input,
                             FROZEN["prepare_historical_business_text_input"])
        self.assertIs(historical_run.load_requirement_snapshot, FROZEN["load_requirement_snapshot"])
        self.assertIs(historical_risk_results.prepare_text_sources, FROZEN["prepare_text_sources"])
        self.assertIs(requirements.load_requirement_snapshot, FROZEN["load_requirement_snapshot"])
        self.assertIs(historical_results.prepare_historical_annual_input,
                      FROZEN["prepare_historical_annual_input"])

    def test_everything_is_put_back_after_a_failure(self):
        with self.assertRaises(RuntimeError):
            with memo.derived_once_per_state():
                raise RuntimeError("inside")
        self.assertIs(historical_run.prepare_historical_run_input,
                      FROZEN["prepare_historical_run_input"])
        self.assertIs(requirements.load_requirement_snapshot, FROZEN["load_requirement_snapshot"])

    def test_a_module_imported_inside_the_block_gets_the_frozen_function_back(self):
        name = "vnext.historical_derivation_memo_case"
        with memo.derived_once_per_state():
            module = types.ModuleType(name)
            module.prepare_historical_annual_input = historical_annual_input.prepare_historical_annual_input
            sys.modules[name] = module
        try:
            self.assertIs(module.prepare_historical_annual_input,
                          FROZEN["prepare_historical_annual_input"])
        finally:
            del sys.modules[name]

    def test_a_block_inside_another_keeps_the_outer_memo(self):
        with memo.derived_once_per_state():
            outer = requirements.load_requirement_snapshot
            with memo.derived_once_per_state():
                self.assertIs(requirements.load_requirement_snapshot, outer)
            self.assertIs(requirements.load_requirement_snapshot, outer)
        self.assertIs(requirements.load_requirement_snapshot, FROZEN["load_requirement_snapshot"])

    def test_a_block_is_for_one_thread(self):
        failures = []
        with memo.derived_once_per_state():
            def other():
                try:
                    with memo.derived_once_per_state():
                        pass
                except Exception as error:  # noqa: BLE001 - recorded for the assertion
                    failures.append(str(error))
            thread = threading.Thread(target=other)
            thread.start()
            thread.join()
        self.assertEqual(failures, ["HISTORICAL_DERIVATION_MEMO_OPEN_IN_ANOTHER_THREAD"])


def _seam_registered():
    """Is issue_47_v1 registered in this tree (the runtime tree's registration patch)?"""
    from vnext.requirement_profile import PROFILE_ENGINES
    return "PROFILE_DRIVEN_V16" in PROFILE_ENGINES


@unittest.skipUnless(_seam_registered(),
                     "issue_47_v1 is not registered; run in the runtime tree")
class TheRealFunctionsAnswerTheirOwnAnswer(unittest.TestCase):
    """The five functions on this repository's saved sources, frozen and memoized.

    The snapshot loader refuses issue_47_v1 where the registration patch is not
    applied, so this class runs in the runtime tree; the checkout's CI runs the
    classes above.
    """

    @classmethod
    def setUpClass(cls):
        cls.snapshot = ROOT / "requirements" / "issue_47_v1"
        cls.selection = resolve_period_selection(repo_root=ROOT, company_id=COMPANY,
                                                 report_end=REPORT_END)
        cls.calls = {
            "load_requirement_snapshot": {"snapshot_dir": cls.snapshot},
            "prepare_historical_annual_input": {"repo_root": ROOT, "company_id": COMPANY,
                                                "period_selection": cls.selection},
            "prepare_historical_run_input": {"repo_root": ROOT, "company_id": COMPANY,
                                             "metric_id": "B01",
                                             "period_selection": cls.selection},
        }
        cls.calls["prepare_historical_business_text_input"] = {
            "repo_root": ROOT, "company_id": COMPANY, "metric_id": "D01",
            "period_selection": cls.selection}
        text = prepare_historical_business_text_input(
            repo_root=ROOT, company_id=COMPANY, metric_id="D01", period_selection=cls.selection)
        spec = FROZEN["prepare_historical_run_input"](
            repo_root=ROOT, company_id=COMPANY, metric_id="D01",
            period_selection=cls.selection)["compiled_specs"]["D01"]
        cls.calls["prepare_text_sources"] = {"compiled_spec": spec, **text["text_arguments"]}
        # Twice without the memo: the answer must not depend on the call, or
        # handing the first one out again would change what a caller sees.
        cls.frozen = {name: [cls._bytes(FROZEN[name](**keywords)) for _ in range(2)]
                      for name, keywords in cls.calls.items()}
        cls.report = []
        cls.memoized = {}
        modules = {"load_requirement_snapshot": requirements,
                   "prepare_historical_annual_input": historical_annual_input,
                   "prepare_historical_run_input": historical_results,
                   "prepare_historical_business_text_input": historical_text_input,
                   "prepare_text_sources": historical_risk_results}
        with memo.derived_once_per_state(report=cls.report):
            for name, keywords in cls.calls.items():
                function = getattr(modules[name], name)
                cls.memoized[name] = [cls._bytes(function(**keywords)) for _ in range(2)]

    @staticmethod
    def _bytes(answer):
        # The text preparations carry the filing's bytes, which canonical JSON
        # does not take; a deep copy compared with == covers every value.
        return copy.deepcopy(answer)

    def test_each_answers_the_same_twice_without_the_memo(self):
        for name, answers in self.frozen.items():
            self.assertEqual(answers[0], answers[1], name)

    def test_the_memo_s_answers_are_the_frozen_answer(self):
        for name, answers in self.memoized.items():
            self.assertEqual(answers, [self.frozen[name][0]] * 2, name)

    def test_none_of_them_reads_outside_its_key(self):
        refused = [item for item in self.report if item["outcome"] != "COMPUTED"
                   and item["outcome"] != "ANSWERED"]
        self.assertEqual(refused, [])
        # Each was answered at least once from what it remembered.
        answered = {item["function"] for item in self.report if item["outcome"] == "ANSWERED"}
        self.assertEqual(answered, set(self.calls))


if __name__ == "__main__":
    unittest.main()
