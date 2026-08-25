"""Verify the authorized Issue #15 Stage C-B terminal packet."""

from __future__ import annotations

import subprocess
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, strict_json_file
from vnext.stage_c_b_packet import APPROVAL_REVIEW
from vnext.stage_c_b_packet import EXPECTED_AUTHORIZATION_ID
from vnext.stage_c_b_packet import EXPECTED_CYCLE_ID
from vnext.stage_c_b_packet import EXPECTED_PLAN_ID
from vnext.stage_c_b_packet import PACKET_POINTER
from vnext.stage_c_b_packet import validate_stage_c_b_packet


class TableStageCBPacketTest(unittest.TestCase):
    """Keep usage evidence separate from qualification and JPM decisions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Validate the complete committed Stage C-B overlay once."""
        cls.summary = validate_stage_c_b_packet(repo_root=REPO_ROOT)
        cls.pointer = strict_json_file(path=REPO_ROOT / PACKET_POINTER)
        cls.packet = strict_json_file(
            path=REPO_ROOT / cls.pointer["packet_path"],
        )

    def test_packet_binds_review_authorization_and_terminal(self) -> None:
        """Recompute identities and require one successful terminal only."""
        body = {
            key: self.packet[key]
            for key in self.packet
            if key != "stage_c_b_packet_id"
        }
        self.assertEqual(
            self.packet["stage_c_b_packet_id"], content_hash(value=body),
        )
        authority = self.packet["authority"]
        self.assertEqual(APPROVAL_REVIEW, authority["approval_review"])
        self.assertEqual(EXPECTED_PLAN_ID, authority["measurement_plan_id"])
        self.assertEqual(EXPECTED_CYCLE_ID, authority["measurement_cycle_id"])
        self.assertEqual(
            EXPECTED_AUTHORIZATION_ID, authority["authorization_id"],
        )
        terminal = self.packet["measurement_terminal"]
        self.assertEqual("COMPLETED", terminal["status"])
        self.assertEqual(200, terminal["http_status"])
        self.assertEqual("SUCCEEDED", terminal["transport_terminal_status"])
        self.assertEqual(160937, terminal["actual_prompt_tokens"])
        self.assertEqual(576, terminal["actual_completion_tokens"])
        self.assertEqual(161513, terminal["actual_total_tokens"])
        self.assertEqual(0, terminal["prompt_cache_hit_tokens"])
        self.assertEqual(160937, terminal["prompt_cache_miss_tokens"])
        self.assertFalse(terminal["retry_performed"])
        self.assertEqual({
            "real_model_provider_egress_count": 1,
            "paid_model_provider_call_count": 1,
            "real_SEC_egress_count": 0,
        }, terminal["egress_counts"])

    def test_measurement_has_no_qualification_or_publication_credit(self) -> None:
        """Preserve ordinary 200k blocking and permanent consumption."""
        semantics = self.packet["measurement_semantics"]
        self.assertEqual(
            "ACTUAL_PROMPT_TOKEN_USAGE_ONLY", semantics["purpose"],
        )
        self.assertTrue(semantics["ordinary_qualification_remains_blocked"])
        self.assertEqual(
            200000,
            semantics["ordinary_qualification_max_estimated_input_tokens"],
        )
        self.assertFalse(semantics["qualification_credit"])
        self.assertFalse(semantics["qualification_evidence_eligible"])
        self.assertFalse(semantics["publication_eligible"])
        self.assertFalse(semantics["response_reuse_for_qualification"])
        self.assertTrue(semantics["authorization_permanently_consumed"])
        self.assertFalse(semantics["additional_measurement_egress_authorized"])
        self.assertIn(
            "ADDITIONAL_REAL_TOKEN_MEASUREMENT",
            self.packet["STILL_UNAUTHORIZED"],
        )
        self.assertIn("LIVE_QUALIFICATION", self.packet["STILL_UNAUTHORIZED"])
        self.assertIn("PUBLICATION", self.packet["STILL_UNAUTHORIZED"])

    def test_jpm_blocker_and_active_root_remain_unchanged(self) -> None:
        """Keep the token result independent from the financial decision."""
        financial = self.packet["financial_evidence"]
        self.assertEqual("F3_NEED_MORE_EVIDENCE", financial["financial_decision"])
        self.assertEqual("NOT_RUN_RSS_GUARD_UNAVAILABLE", financial["status"])
        self.assertFalse(financial["completion_result"])
        self.assertIsNone(financial["peak_rss_bytes"])
        self.assertIsNone(financial["wall_time_seconds"])
        self.assertIsNone(financial["canonical_json_bytes"])
        self.assertIsNone(financial["derived_asset_id"])
        self.assertEqual(["JPM_RSS_GUARD_UNAVAILABLE"], self.packet["BLOCKERS"])
        self.assertEqual(309, self.packet["active_root_state"]["public_matrix_row_count"])

    def test_validation_snapshot_uses_stage_c_b_overlay(self) -> None:
        """Require the current source tree and historical R2 bytes together."""
        completed = subprocess.run(
            ["python3", "tools/check_validation_snapshot.py"],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("current Stage C-B measurement-evidence overlay", completed.stdout)


if __name__ == "__main__":
    unittest.main()
