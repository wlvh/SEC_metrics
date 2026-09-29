"""Issue #47's own executable files spell none of the family-owned business phrases.

tools/check_vnext_semantics.py forbids the phrases the approved source
strategy owns (config/source_strategy_registry.json,
forbidden_production_literals) in executable vNext code: business phrases
belong in the catalog. CI does not run that repository-wide audit, and #47's
C02, E01, B10/B11 and B13 modules had spelled nine of them for days before a
local run of the audit found it. This runs the audit's own per-file check on
#47's files, so a phrase that comes back fails here instead of waiting for
someone to run the gate.

Which files are #47's: the rule files its generation records (the mint
tool's NEW_RULE_FILES) and every module and tool named for the history work,
within the audit's own reach (scripts/vnext/*.py and tools/vnext_*.py).
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

from check_vnext_semantics import audit_python_file, compile_business_literal_pattern  # noqa: E402
from vnext_mint_historical_requirement import NEW_RULE_FILES  # noqa: E402


def issue_47_files():
    """#47's executable files inside the audit's reach, by repository-relative path."""
    named = {path.relative_to(ROOT).as_posix() for pattern in ("historical_*.py", "normal_history*.py")
             for path in (ROOT / "scripts/vnext").glob(pattern)}
    named |= {path.relative_to(ROOT).as_posix() for path in (ROOT / "tools").glob("vnext_*histor*.py")}
    named |= {path for path in NEW_RULE_FILES if path.endswith(".py")}
    return sorted(path for path in named
                  if path.startswith("scripts/vnext/") and path.count("/") == 2
                  or path.startswith("tools/vnext_") and path.count("/") == 1)


class Issue47SpellsNoFamilyOwnedPhrase(unittest.TestCase):

    def test_the_files_are_found_before_they_are_judged(self):
        # An empty or narrowed set would pass the next case by finding nothing.
        files = issue_47_files()
        for expected in ("scripts/vnext/historical_board_composition.py",
                         "scripts/vnext/historical_event_items.py",
                         "scripts/vnext/historical_lodging_results.py",
                         "scripts/vnext/historical_capacity_results.py",
                         "scripts/vnext/normal_history_plan.py",
                         "tools/vnext_mint_historical_requirement.py"):
            self.assertIn(expected, files)
        # 59 when this was written; a floor, so files added later never break it.
        self.assertGreaterEqual(len(files), 50)

    def test_no_file_spells_a_family_owned_phrase(self):
        pattern = compile_business_literal_pattern(repo_root=ROOT)
        hits = [hit for path in issue_47_files()
                for hit in audit_python_file(path=ROOT / path, repo_root=ROOT,
                                             business_literal_pattern=pattern)
                if hit["type"] == "BUSINESS_LITERAL"]
        self.assertEqual([], [(hit["file"], hit["line"], hit["literal"]) for hit in hits])


if __name__ == "__main__":
    unittest.main()
