"""Validate the post-attestation Stage-C answer-first packet."""

from __future__ import annotations

import unittest

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, strict_json_file
from vnext.stage_c_context_packet import PACKET_POINTER
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


class StageCContextPacketFastTest(unittest.TestCase):
    """Read current and historical addressed packets under the 30s fast cap."""

    @staticmethod
    def _addressed(*, pointer_path: str, id_field: str) -> dict:
        """Load a pointer target and recompute its canonical identity."""
        pointer = strict_json_file(path=REPO_ROOT / pointer_path)
        packet = strict_json_file(path=REPO_ROOT / pointer["packet_path"])
        body = {
            key: value for key, value in packet.items() if key != id_field
        }
        if packet[id_field] != content_hash(value=body):
            raise AssertionError("Packet identity differs")
        if pointer[id_field] != packet[id_field]:
            raise AssertionError("Packet pointer differs")
        return packet

    def test_current_packet_persists_no_credit_and_zero_current_egress(
        self,
    ) -> None:
        """Keep current boundaries inspectable without full authority rebuild."""
        packet = self._addressed(
            pointer_path=PACKET_POINTER.as_posix(),
            id_field="stage_c_context_packet_id",
        )
        self.assertFalse(
            packet["measurement_state"][
                "historical_measurement_response_qualification_credit"
            ]
        )
        self.assertFalse(
            packet["qualification_state"]["live_qualification_authorized"]
        )
        self.assertEqual([], packet["readiness"]["live_ready_family_ids"])
        self.assertEqual({0}, set(packet["current_pr_egress_counts"].values()))

    def test_historical_stage_c_b_packet_remains_content_addressed(self) -> None:
        """Preserve the consumed 1/1/0 terminal without current-source claims."""
        packet = self._addressed(
            pointer_path=(
                "artifacts/vnext/table_stage_c_evidence/"
                "current_stage_c_b_packet.json"
            ),
            id_field="stage_c_b_packet_id",
        )
        terminal = packet["measurement_terminal"]
        semantics = packet["measurement_semantics"]
        self.assertEqual(160937, terminal["actual_prompt_tokens"])
        self.assertEqual(
            {
                "real_model_provider_egress_count": 1,
                "paid_model_provider_call_count": 1,
                "real_SEC_egress_count": 0,
            },
            terminal["egress_counts"],
        )
        self.assertTrue(semantics["authorization_permanently_consumed"])
        self.assertFalse(semantics["response_reuse_for_qualification"])

    def test_current_packet_persists_sibling_and_financial_blockers(self) -> None:
        """Keep task/family/F3 blockers visible in the lightweight read path."""
        packet = self._addressed(
            pointer_path=PACKET_POINTER.as_posix(),
            id_field="stage_c_context_packet_id",
        )
        self.assertEqual(
            "EXACT_CONTEXT_EVIDENCE_REQUIRED",
            packet["context_feasibility"]["sibling_request"]["status"],
        )
        self.assertFalse(
            packet["context_feasibility"]["family_overall_live_ready"]
        )
        self.assertEqual(
            "F3_NEED_MORE_EVIDENCE", packet["financial_state"]["decision"]
        )


if __name__ == "__main__":
    unittest.main()
