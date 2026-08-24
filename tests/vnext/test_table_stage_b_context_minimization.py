"""Verify deterministic, decision-neutral lodging context research."""

from __future__ import annotations

import unittest

from tests.vnext.common import REPO_ROOT
from tools.investigate_table_context_minimization import (
    build_context_minimization_receipt,
)


EXPECTED_RECEIPT_ID = (
    "sha256:2dd551a5613cf6980644ae8f9a99c9231456c736ae29969f613d4c8cedd1e3a1"
)


class TableStageBContextMinimizationTest(unittest.TestCase):
    """Keep research reversible, reproducible, and outside production paths."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build twice so nondeterministic receipt preimages fail the suite."""
        cls.first = build_context_minimization_receipt(repo_root=REPO_ROOT)
        cls.second = build_context_minimization_receipt(repo_root=REPO_ROOT)

    def test_receipt_rebuild_is_deterministic(self) -> None:
        """Produce the same content ID on two consecutive offline builds."""
        self.assertEqual(EXPECTED_RECEIPT_ID, self.first["receipt_id"])
        self.assertEqual(self.first["receipt_id"], self.second["receipt_id"])
        self.assertEqual(self.first, self.second)

    def test_exact_source_task_and_provider_decomposition(self) -> None:
        """Cover four source hashes, both tasks, and every envelope byte."""
        self.assertEqual(4, len(self.first["source_set"]))
        baseline = self.first["baseline_current_v2"]
        self.assertEqual(8, len(baseline["per_source_task_measurements"]))
        marriott = {
            row["task_contract_id"]: row["estimated_input_tokens"]
            for row in baseline["marriott_measurements"]
        }
        self.assertEqual({
            "lodging_occupancy_table_v2": 392447,
            "lodging_revpar_table_v2": 392438,
        }, marriott)
        for row in baseline["per_source_task_measurements"]:
            decomposition = row["provider_layer_decomposition"]
            self.assertEqual(
                decomposition["exact_provider_envelope_bytes"],
                decomposition["attributed_byte_sum"],
            )
        for source in self.first["decomposition_by_source"]:
            compact = source["compact_payload"]
            self.assertEqual(
                compact["exact_compact_transport_bytes"],
                compact["component_byte_sum"],
            )
            repetition = source["text_and_repetition"]
            self.assertTrue(repetition["repeated_string_exact_set"])
            self.assertTrue(
                repetition["repeated_string_exact_set_hash"].startswith(
                    "sha256:"
                )
            )

    def test_candidates_do_not_claim_model_accuracy(self) -> None:
        """Separate machine round-trip from model readability evidence."""
        candidates = {
            row["candidate_id"]: row for row in self.first["candidates"]
        }
        self.assertEqual(
            {"CANDIDATE-1", "CANDIDATE-2", "CANDIDATE-3",
             "CANDIDATE-4", "CANDIDATE-5"},
            set(candidates),
        )
        self.assertEqual(
            [286407, 337587, 337056, 386572, 392671],
            [
                candidates[candidate_id]["maximum_estimated_input_tokens"]
                for candidate_id in sorted(candidates)
            ],
        )
        for candidate in candidates.values():
            self.assertTrue(candidate["machine_reversible"])
            self.assertTrue(
                candidate[
                    "decode_candidate_field_equal_current_expanded_authority"
                ]
            )
            self.assertTrue(
                candidate["machine_decoded_semantic_text_byte_equal"]
            )
            self.assertFalse(candidate["maximum_below_or_equal_200000"])
            self.assertFalse(candidate["contains_selector"])
            self.assertFalse(candidate["contains_filter"])
            self.assertFalse(candidate["contains_semantic_decision"])
            self.assertFalse(candidate["production_enabled"])
        self.assertEqual(
            "HIGH_REQUIRES_REAL_QUALIFICATION",
            candidates["CANDIDATE-3"]["model_readability_risk"],
        )
        self.assertFalse(
            candidates["CANDIDATE-3"][
                "model_final_visible_semantic_text_byte_equal"
            ]
        )
        self.assertTrue(
            candidates["CANDIDATE-5"]["co_table_evidence"][
                "stable_co_table_for_all_sources"
            ]
        )
        self.assertIn(
            "does not prove unchanged model extraction accuracy",
            self.first["interpretation_boundary"],
        )

    def test_research_has_zero_egress_and_no_root_side_effect(self) -> None:
        """Keep production serializer, root, and egress untouched."""
        self.assertEqual({
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_sec_egress_count": 0,
        }, self.first["egress_counts"])
        self.assertTrue(self.first["root_business_artifacts_byte_equal"])
        self.assertEqual("NOT_RUN", self.first["actual_prompt_tokens"])
        self.assertFalse(
            self.first["scope"]["production_serializer_changed"]
        )
        self.assertFalse(
            self.first["scope"]["production_task_contract_changed"]
        )


if __name__ == "__main__":
    unittest.main()
