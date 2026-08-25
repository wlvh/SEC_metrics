"""Verify the answer-first Issue #15 Stage C-A decision-evidence packet."""

from __future__ import annotations

import unittest

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, strict_json_file
from vnext.stage_c_packet import PACKET_POINTER


class TableStageCAPacketTest(unittest.TestCase):
    """Keep implemented, measured, unauthorized, and blocked states separate."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the preserved pre-egress packet as historical evidence."""
        cls.pointer = strict_json_file(path=REPO_ROOT / PACKET_POINTER)
        cls.packet = strict_json_file(
            path=REPO_ROOT / cls.pointer["packet_path"],
        )

    def test_packet_sections_preserve_stage_c_a_claim_boundaries(self) -> None:
        """Report implementation and blocker without claiming live evidence."""
        self.assertEqual(
            self.pointer["stage_c_a_packet_id"],
            self.packet["stage_c_a_packet_id"],
        )
        body = {
            key: self.packet[key]
            for key in self.packet
            if key != "stage_c_a_packet_id"
        }
        self.assertEqual(
            self.packet["stage_c_a_packet_id"], content_hash(value=body),
        )
        self.assertEqual(
            "BLOCKED_OFFLINE_BENCHMARK_NOT_RUN",
            self.packet["stage_c_a_status"],
        )
        self.assertEqual(
            ["JPM_RSS_GUARD_UNAVAILABLE"], self.packet["BLOCKERS"],
        )
        self.assertTrue(
            self.packet["OWNER_APPROVED"][
                "exact_lodging_token_measurement_path_implementation"
            ]
        )
        implemented = self.packet["IMPLEMENTED_NOT_EXECUTED"]
        self.assertTrue(implemented["lodging_actual_token_measurement_executor"])
        self.assertEqual(
            "O_EXCL_FAIL_CLOSED_FILE_AND_DIRECTORY_FSYNC",
            implemented["concurrent_marker_claim"],
        )
        self.assertEqual(
            "PASSED_MOCK_TWO_PROCESS_ONE_OPENER",
            implemented["concurrent_sender_regression"],
        )
        self.assertEqual(
            "RESOLVED_PENDING_INDEPENDENT_REREVIEW",
            implemented["reviewed_b1_status"],
        )
        self.assertEqual(
            "PENDING_OWNER_DECISION",
            implemented["reviewer_receipt_recommendation_status"],
        )
        self.assertFalse(implemented["external_exact_head_authorization_received"])
        self.assertFalse(implemented["opaque_execution_authorization_issued"])
        self.assertFalse(implemented["provider_egress_executed"])
        authorization = self.packet["measurement_authorization"]
        self.assertEqual("NOT_ISSUED", authorization["authorization_id"])
        self.assertEqual(392447, authorization["estimated_input_tokens"])
        self.assertEqual(
            200000,
            authorization["ordinary_qualification_max_estimated_input_tokens"],
        )
        review = self.packet["authority"]["rework_review"]
        self.assertEqual(5014458726, review["review_id"])
        self.assertEqual(
            "fb6144e240d5b3b16ba080731b805e06cf936abb",
            review["reviewed_head"],
        )
        self.assertEqual("REWORK_REQUIRED", review["code_verdict"])

    def test_benchmark_active_root_and_egress_are_honest(self) -> None:
        """Expose null benchmark values, unchanged R2 bytes, and exact zeroes."""
        measured = self.packet["MEASURED_OFFLINE"]
        self.assertEqual("NOT_RUN_RSS_GUARD_UNAVAILABLE", measured["status"])
        self.assertFalse(measured["completion_result"])
        self.assertIsNone(measured["peak_rss_bytes"])
        self.assertIsNone(measured["wall_time_seconds"])
        self.assertIsNone(measured["canonical_json_bytes"])
        self.assertIsNone(measured["derived_asset_id"])
        root = self.packet["active_root_state"]
        self.assertEqual(309, root["public_matrix_row_count"])
        self.assertTrue(root["root_business_artifacts_byte_equal"])
        self.assertEqual(
            root["root_business_artifacts_before"],
            root["root_business_artifacts_after"],
        )
        self.assertEqual({
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_SEC_egress_count": 0,
        }, self.packet["egress_counts"])
        self.assertEqual(
            {
                "REAL_TOKEN_MEASUREMENT",
                "LIVE_QUALIFICATION",
                "R3",
                "R4",
                "PRODUCTION_MAX_TOTAL_CELLS_CHANGE",
                "SHARDING",
                "SERIALIZER_CANDIDATE",
                "SELECTOR",
                "PUBLICATION",
            },
            set(self.packet["STILL_UNAUTHORIZED"]),
        )

    def test_packet_remains_the_historical_pre_egress_terminal(self) -> None:
        """Do not rewrite Stage C-A zeroes after the Stage C-B execution."""
        self.assertEqual(
            "NOT_ISSUED",
            self.packet["measurement_authorization"]["authorization_id"],
        )
        self.assertEqual(
            "NOT_RUN",
            self.packet["IMPLEMENTED_NOT_EXECUTED"][
                "measurement_evidence_status"
            ],
        )


if __name__ == "__main__":
    unittest.main()
