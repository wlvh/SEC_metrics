"""Validate the post-attestation Stage-C answer-first packet."""

from __future__ import annotations

import unittest

from tests.vnext.common import REPO_ROOT
from vnext.stage_c_context_packet import (
    build_stage_c_context_attestation_packet,
)
from vnext.stage_c_context_packet import (
    validate_stage_c_context_attestation_packet,
)


class StageCContextPacketTest(unittest.TestCase):
    """Keep feasibility, qualification, readiness, and egress distinct."""

    @classmethod
    def setUpClass(cls) -> None:
        """Validate the immutable current packet once."""
        cls.packet = validate_stage_c_context_attestation_packet(
            repo_root=REPO_ROOT,
        )

    def test_exact_request_is_feasible_but_sibling_and_family_are_blocked(
        self,
    ) -> None:
        """Represent one task PASS without manufacturing family readiness."""
        context = self.packet["context_feasibility"]
        self.assertEqual(
            "CONTEXT_FEASIBLE", context["attested_request"]["status"]
        )
        self.assertEqual(
            "PROVIDER_REPORTED_EXACT_BINDING",
            context["attested_request"]["evidence_basis"],
        )
        self.assertEqual(160937, context["attested_request"]["actual_prompt_tokens"])
        self.assertEqual(
            "EXACT_CONTEXT_EVIDENCE_REQUIRED",
            context["sibling_request"]["status"],
        )
        self.assertFalse(context["family_overall_live_ready"])
        self.assertEqual([], self.packet["readiness"]["live_ready_family_ids"])

    def test_measurement_never_becomes_qualification(self) -> None:
        """Keep consumed authorization and no-credit response explicit."""
        measurement = self.packet["measurement_state"]
        qualification = self.packet["qualification_state"]
        self.assertTrue(
            measurement["measurement_authorization_permanently_consumed"]
        )
        self.assertFalse(measurement["additional_measurement_authorized"])
        self.assertFalse(
            measurement["historical_measurement_response_qualification_credit"]
        )
        self.assertFalse(
            measurement[
                "historical_measurement_response_reuse_for_qualification"
            ]
        )
        self.assertFalse(qualification["live_qualification_authorized"])
        self.assertFalse(qualification["qualification_started"])
        self.assertEqual(0, qualification["qualification_fresh_ordinals_executed"])

    def test_financial_root_and_zero_egress_state_remain_unchanged(self) -> None:
        """Keep F3, active R2, root bytes, and current PR egress honest."""
        self.assertEqual(
            "F3_NEED_MORE_EVIDENCE",
            self.packet["financial_state"]["decision"],
        )
        self.assertFalse(
            self.packet["financial_state"][
                "production_resource_policy_changed"
            ]
        )
        self.assertTrue(
            self.packet["active_root_state"][
                "root_business_artifacts_byte_equal"
            ]
        )
        self.assertFalse(
            self.packet["active_root_state"]["publication_changed"]
        )
        self.assertEqual(
            {
                "real_model_provider_egress_count": 0,
                "paid_model_provider_call_count": 0,
                "real_SEC_egress_count": 0,
            },
            self.packet["current_pr_egress_counts"],
        )
        self.assertEqual(
            {
                "real_model_provider_egress_count": 1,
                "paid_model_provider_call_count": 1,
                "real_SEC_egress_count": 0,
            },
            self.packet["historical_stage_c_b"]["historical_egress_counts"],
        )

    def test_packet_rebuild_is_deterministic(self) -> None:
        """Recompute the packet from all current addressed authorities."""
        self.assertEqual(
            self.packet,
            build_stage_c_context_attestation_packet(repo_root=REPO_ROOT),
        )


if __name__ == "__main__":
    unittest.main()
