"""Verify the Stage-B owner-approved/undecided packet boundary."""

from __future__ import annotations

import unittest

from tests.vnext.common import REPO_ROOT
from tools.create_table_qualification_owner_decision_packet import (
    build_owner_decision_packet,
)
from vnext.canonical import content_hash, strict_json_file


OLD_PACKET_ID = (
    "sha256:04f4980c8864be0f77a0739028e58d06056548709888eeb31f3c1d2e59499805"
)
CONTEXT_RECEIPT_ID = (
    "sha256:2dd551a5613cf6980644ae8f9a99c9231456c736ae29969f613d4c8cedd1e3a1"
)
CENSUS_RECEIPT_ID = (
    "sha256:ea3d796f256a43ac5a6079de753d7d5456fc6d7485bb794ef4c9e27276ca6f2c"
)


class TableStageBOwnerPacketTest(unittest.TestCase):
    """Keep approved decisions separate from unresolved product choices."""

    @classmethod
    def setUpClass(cls) -> None:
        pointer = strict_json_file(path=(
            REPO_ROOT
            / "artifacts/vnext/table_qualification_freeze/"
            "current_owner_decision_packet.json"
        ))
        cls.pointer = pointer
        cls.packet = strict_json_file(
            path=REPO_ROOT / pointer["packet_path"],
        )
        cls.rebuilt = build_owner_decision_packet(
            repo_root=REPO_ROOT,
            generated_at_utc=cls.packet["generated_at_utc"],
        )

    def test_packet_is_content_addressed_and_rebuilds_exactly(self) -> None:
        """Bind the pointer to exact packet bytes and deterministic rebuild."""
        packet_id = self.packet["owner_decision_packet_id"]
        body = {
            key: self.packet[key]
            for key in self.packet
            if key != "owner_decision_packet_id"
        }
        self.assertEqual(content_hash(value=body), packet_id)
        self.assertEqual(packet_id, self.pointer["owner_decision_packet_id"])
        self.assertEqual(self.packet, self.rebuilt)
        self.assertIn(
            OLD_PACKET_ID,
            self.packet["supersedes_owner_decision_packet_ids"],
        )
        old_path = (
            REPO_ROOT
            / "artifacts/vnext/table_qualification_freeze/decision_packets/"
            / (OLD_PACKET_ID.split(":", maxsplit=1)[1] + ".json")
        )
        self.assertTrue(old_path.is_file())

    def test_owner_approved_fields_are_exact(self) -> None:
        """Record 200k/family scope without authorizing any live activity."""
        approved = self.packet["OWNER_APPROVED"]
        threshold = approved["estimated_input_threshold"]
        self.assertEqual(100000, threshold["old_max_estimated_input_tokens"])
        self.assertEqual(200000, threshold["new_max_estimated_input_tokens"])
        self.assertTrue(threshold["inclusive"])
        self.assertEqual("PER_FAMILY_PER_REQUEST", threshold["scope"])
        self.assertTrue(approved["family_scoped_readiness"])
        self.assertEqual(
            "INVALIDATE_ALL_DEPENDENT_FAMILIES",
            approved["shared_dependency_drift_policy"],
        )
        self.assertFalse(approved["semantic_prefilter"])
        self.assertFalse(approved["selector_authorized"])
        self.assertFalse(approved["live_measurement_authorized"])
        self.assertFalse(approved["live_qualification_authorized"])
        self.assertEqual(
            "ONE_EXACT_TASK_REQUEST",
            approved["context_attestation_scope"],
        )
        self.assertFalse(
            approved["measurement_response_qualification_credit"]
        )
        self.assertFalse(
            approved["measurement_response_reuse_for_qualification"]
        )

    def test_undecided_options_remain_null(self) -> None:
        """Refuse to select serializer, measurement, resource, or selector."""
        undecided = {
            row["decision"]: row["selected_value"]
            for row in self.packet["STILL_UNDECIDED"]
        }
        self.assertEqual({
            "adopt_any_lossless_serializer_candidate": None,
            "obtain_sibling_exact_context_evidence": None,
            "financial_raise_cap_or_per_table_shard": None,
            "replace_financial_development_source": None,
            "authorize_or_require_selector": None,
        }, undecided)
        self.assertFalse(self.packet["undecided_product_choice_made"])
        self.assertIsNone(
            self.packet["financial_grid_census_summary"]["selected_option"]
        )

    def test_current_readiness_investigations_and_root_are_bound(self) -> None:
        """Persist blockers, research IDs, and unchanged R2 root."""
        current = self.packet["current_readiness"]
        self.assertEqual([], current["live_ready_family_ids"])
        self.assertEqual(
            160937,
            current["attested_request"]["actual_prompt_tokens"],
        )
        self.assertEqual(
            "FEASIBLE", current["attested_request"]["context_status"]
        )
        self.assertEqual(
            "EXACT_CONTEXT_EVIDENCE_REQUIRED",
            current["sibling_request"]["context_status"],
        )
        self.assertEqual(
            [
                "ESTIMATED_CONTEXT_LIMIT",
                "EXACT_CONTEXT_BINDING_MISMATCH",
            ],
            current["readiness_by_family"]["lodging_kpi_table"][
                "blocking_reason_codes"
            ],
        )
        self.assertEqual(
            ["EXPANDED_GRID_RESOURCE_LIMIT"],
            current["readiness_by_family"]["financial_statement"][
                "blocking_reason_codes"
            ],
        )
        bindings = self.packet["investigation_bindings"]
        self.assertEqual(
            CONTEXT_RECEIPT_ID,
            bindings["context_minimization"]["receipt_id"],
        )
        self.assertEqual(
            CENSUS_RECEIPT_ID,
            bindings["financial_grid_census"]["receipt_id"],
        )
        self.assertEqual(
            "TABLE_CONTEXT_FEASIBILITY_ATTESTATION",
            bindings["context_feasibility_attestation"]["record_type"],
        )
        self.assertEqual(
            "EXACT_CONTEXT_EVIDENCE_REQUIRED",
            bindings["sibling_request_context_analysis"]["status"],
        )
        root = self.packet["unchanged_active_root"]
        self.assertEqual(309, root["public_matrix_row_count"])
        self.assertTrue(root["before_after_byte_equal"])

    def test_packet_records_zero_egress_and_no_completion_claim(self) -> None:
        """Keep Stage-B evidence below qualification and Issue completion."""
        self.assertEqual({
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_sec_egress_count": 0,
        }, self.packet["egress_counts"])
        completion = self.packet["completion_boundary"]
        self.assertTrue(all(value is False for value in completion.values()))


if __name__ == "__main__":
    unittest.main()
