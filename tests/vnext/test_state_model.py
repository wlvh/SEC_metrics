"""Independent object-state and batch publication tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from vnext.states import (
    FREEZEABLE_VALIDATION_STATUSES,
    PUBLISHABLE_VALIDATION_STATUSES,
    StateError,
    publication_candidate_status,
    validate_transition,
)


class StateModelTest(unittest.TestCase):
    """Prove FROZEN, validated, and publishable remain independent states."""

    def test_only_declared_transitions_are_allowed(self) -> None:
        """Accept terminal transitions and reject terminal mutation."""
        validate_transition(
            object_type="RUN", current_status="OPEN", target_status="FROZEN",
        )
        with self.assertRaises(StateError):
            validate_transition(
                object_type="RUN",
                current_status="FROZEN",
                target_status="FAILED",
            )

    def test_applicable_withheld_blocks_whole_batch(self) -> None:
        """Block any applicable WITHHELD result but allow structural N/A."""
        self.assertEqual(
            "BLOCKED",
            publication_candidate_status(
                results=[
                    {
                        "applicability": "APPLICABLE",
                        "publication": "WITHHELD",
                    }
                ]
            ),
        )
        self.assertEqual(
            "PUBLISHABLE",
            publication_candidate_status(
                results=[
                    {
                        "applicability": "N_A_STRUCTURAL",
                        "publication": "PUBLISHED",
                    }
                ]
            ),
        )

    def test_sop_structured_validation_state_contract(self) -> None:
        """Bind operator instructions to the three executable state cases."""
        repo_root = Path(__file__).resolve().parents[2]
        text = (repo_root / "SOP.md").read_text(encoding="utf-8")
        start_marker = "<!-- vnext-validation-state-contract:start -->"
        end_marker = "<!-- vnext-validation-state-contract:end -->"
        self.assertEqual(1, text.count(start_marker))
        self.assertEqual(1, text.count(end_marker))
        block = text.split(start_marker, maxsplit=1)[1].split(
            end_marker, maxsplit=1,
        )[0]
        rows = {}
        for line in block.splitlines():
            if not line.startswith("| `"):
                continue
            fields = [field.strip() for field in line.strip("|").split("|")]
            self.assertEqual(3, len(fields))
            rows[fields[0].strip("`")] = tuple(fields[1:])
        expected = {
            status: (
                "允许",
                (
                    "满足本状态门"
                    if status in PUBLISHABLE_VALIDATION_STATUSES
                    else "禁止"
                ),
            )
            for status in FREEZEABLE_VALIDATION_STATUSES
        }
        self.assertEqual(expected, rows)


if __name__ == "__main__":
    unittest.main()
