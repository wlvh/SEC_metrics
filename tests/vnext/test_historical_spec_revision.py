"""A revised Spec moves one bound, and the frozen compiler keeps its bytes.

The point of the revision module is not that it produces a compiled Spec - a
substitution would do that. It is that it cannot produce one for a successor
that changed anything else, because the frozen compiler rejects a whole file
with one message and cannot say which of its checks failed. Every negative here
is a successor that differs from its predecessor in one more place, built by
mutating the real v2 front matter rather than a fixture, so a check that stopped
working would have to be noticed here.
"""
import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.historical_spec_revision import (REVISED_TEXT_SPECS, SUCCESSOR_MAX_ITEMS,
                                            SpecRevisionError,
                                            compile_historical_spec_file,
                                            compile_revised_text_spec)
from vnext.specs import SpecError, compile_spec_file, parse_spec_document

SUCCESSOR = "catalog/r6/D02_legal_disclosures_v2.md"
PREDECESSOR = "catalog/r6/D02_legal_disclosures_v1.md"


def _mutated(mutate):
    """Write the real successor's front matter with one field changed."""
    front, body = parse_spec_document(text=(ROOT / SUCCESSOR).read_text(encoding="utf-8"))
    mutate(front)
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "successor.md"
    path.write_text("---\n" + json.dumps(front, ensure_ascii=False, indent=1) + "\n---\n" + body,
                    encoding="utf-8")
    return directory, path


class HistoricalSpecRevisionTest(unittest.TestCase):
    def test_the_frozen_compiler_still_refuses_the_successor(self):
        """If it ever accepts v2, the ceiling moved and this module is dead code."""
        with self.assertRaises(SpecError) as raised:
            compile_spec_file(path=ROOT / SUCCESSOR, dependency_specs={})
        self.assertIn("text_policy", str(raised.exception))

    def test_the_revision_carries_the_declared_bound_and_nothing_else(self):
        predecessor = compile_spec_file(path=ROOT / PREDECESSOR, dependency_specs={})
        successor = compile_historical_spec_file(
            repo_root=ROOT, repo_relative_path=SUCCESSOR, dependency_specs={})
        self.assertEqual(64, predecessor["compiled"]["text_policy"]["max_items"])
        self.assertEqual(192, successor["compiled"]["text_policy"]["max_items"])
        self.assertEqual(
            {key: value for key, value in predecessor["compiled"].items() if key != "text_policy"},
            {key: value for key, value in successor["compiled"].items() if key != "text_policy"})
        self.assertEqual(
            {k: v for k, v in predecessor["compiled"]["text_policy"].items() if k != "max_items"},
            {k: v for k, v in successor["compiled"]["text_policy"].items() if k != "max_items"})
        # A different bound is a different Spec identity, which is why the Runs
        # frozen under v1 keep declaring v1.
        self.assertNotEqual(predecessor["spec_semantic_hash"], successor["spec_semantic_hash"])
        self.assertNotEqual(predecessor["spec_closure_hash"], successor["spec_closure_hash"])
        self.assertEqual(successor["prompt_bundle"]["spec_semantic_hash"],
                         successor["spec_semantic_hash"])

    def test_an_unrevised_spec_takes_the_frozen_path_unchanged(self):
        routed = compile_historical_spec_file(
            repo_root=ROOT, repo_relative_path=PREDECESSOR, dependency_specs={})
        self.assertEqual(compile_spec_file(path=ROOT / PREDECESSOR, dependency_specs={}), routed)
        self.assertNotIn(PREDECESSOR, REVISED_TEXT_SPECS)

    def test_a_successor_that_moves_anything_else_is_refused(self):
        """Each case is the real v2 with exactly one more field changed."""
        cases = {
            "required_sections": lambda f: f["text_policy"].__setitem__(
                "required_sections", ["ITEM_3"]),
            "max_text_chars": lambda f: f["text_policy"].__setitem__("max_text_chars", 32000),
            "allowed_source_roles": lambda f: f["text_policy"].__setitem__(
                "allowed_source_roles", ["PRIMARY"]),
            "name": lambda f: f.__setitem__("name", "Something else"),
            "quality_rule": lambda f: f.__setitem__("quality_rule", {}),
            "disclosure_group": lambda f: f.__setitem__("disclosure_group", None),
            # Valid front matter that the frozen compiler accepts, so the
            # comparison is what refuses it rather than a check upstream.
            "applicability": lambda f: f.__setitem__(
                "applicability", {"all": ["is_lodging"], "none": []}),
            "metric_id": lambda f: f.__setitem__("metric_id", "C02"),
        }
        for label, mutate in cases.items():
            with self.subTest(changed=label):
                directory, path = _mutated(mutate)
                with directory:
                    with self.assertRaises(SpecError) as raised:
                        compile_revised_text_spec(successor_path=path,
                                                  predecessor_path=ROOT / PREDECESSOR,
                                                  dependency_specs={})
                    self.assertIn("Revised Spec", str(raised.exception))

    def test_front_matter_the_frozen_compiler_rejects_never_reaches_the_comparison(self):
        """The successor path adds a check; it does not remove any."""
        for label, mutate in {
            "applicability": lambda f: f.__setitem__("applicability", {"kind": "always"}),
            "renderer": lambda f: f["text_policy"].__setitem__("renderer", "OTHER"),
        }.items():
            with self.subTest(changed=label):
                directory, path = _mutated(mutate)
                with directory:
                    with self.assertRaises(SpecError) as raised:
                        compile_revised_text_spec(successor_path=path,
                                                  predecessor_path=ROOT / PREDECESSOR,
                                                  dependency_specs={})
                    self.assertNotIn("Revised Spec", str(raised.exception))

    def test_a_bound_above_the_successor_ceiling_is_refused(self):
        directory, path = _mutated(
            lambda f: f["text_policy"].__setitem__("max_items", SUCCESSOR_MAX_ITEMS + 1))
        with directory:
            with self.assertRaises(SpecRevisionError) as raised:
                compile_revised_text_spec(successor_path=path,
                                          predecessor_path=ROOT / PREDECESSOR,
                                          dependency_specs={})
            self.assertIn("max_items", str(raised.exception))

    def test_every_front_matter_field_is_covered_by_one_of_the_two_comparisons(self):
        """The equality is only a guard if no declared field escapes both sides."""
        from vnext.specs import SPEC_FIELDS
        compiled = compile_spec_file(path=ROOT / PREDECESSOR, dependency_specs={})
        reachable = set(compiled["compiled"]) | {"ai_instructions", "prompt_examples"}
        self.assertEqual(set(), set(SPEC_FIELDS) - reachable)


if __name__ == "__main__":
    unittest.main()
