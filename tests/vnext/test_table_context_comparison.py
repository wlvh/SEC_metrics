"""Validate the decision-neutral full-request sibling comparison."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext import ai_adapter
from vnext.table_context_comparison import ANALYSIS_POINTER
from vnext.table_context_comparison import (
    build_sibling_request_context_analysis,
)
from vnext.table_context_comparison import (
    validate_sibling_request_context_analysis,
)


class TableContextComparisonTest(unittest.TestCase):
    """Keep the offline comparison exact and inference-neutral."""

    @classmethod
    def setUpClass(cls) -> None:
        """Validate the current immutable analysis once."""
        cls.analysis = validate_sibling_request_context_analysis(
            repo_root=REPO_ROOT,
        )

    def test_exact_request_hashes_lengths_and_byte_ranges_are_recorded(
        self,
    ) -> None:
        """Bind both full bodies and the minimal unequal half-open ranges."""
        requests = self.analysis["requests"]
        occupancy = requests["ATTESTED_MEASUREMENT_REQUEST"]
        revpar = requests["UNATTESTED_SIBLING_REQUEST"]
        self.assertEqual(
            "5ffa7b16d54ff9e3c2bdbc10d468f84b9aaae2ac029b5fc63e459d895eb8109a",
            occupancy["provider_request_body_sha256"],
        )
        self.assertEqual(392447, occupancy["provider_request_body_bytes"])
        self.assertEqual(
            "1dbe25dd3886bc7ab5e559c7f790bf40cc3471a3550553435450acfe92e72b0b",
            revpar["provider_request_body_sha256"],
        )
        self.assertEqual(392438, revpar["provider_request_body_bytes"])
        ranges = self.analysis["exact_request_comparison"][
            "minimal_differing_byte_ranges"
        ]
        self.assertEqual(16153, ranges["shared_prefix_bytes"])
        self.assertEqual(374222, ranges["shared_suffix_bytes"])
        self.assertEqual(
            2072, ranges["attested_request_range"]["length"]
        )
        self.assertEqual(
            2063, ranges["sibling_request_range"]["length"]
        )

    def test_shared_and_changed_authority_components_are_explicit(self) -> None:
        """Separate task differences from shared prompt/schema/source bytes."""
        comparison = self.analysis["exact_request_comparison"]
        self.assertFalse(comparison["task_contract_equal"])
        self.assertTrue(comparison["prompt_equal"])
        self.assertTrue(comparison["output_schema_equal"])
        self.assertEqual(
            {
                "task_contract_hash",
                "task_contract_bytes_sha256",
                "task_spec_semantic_hash",
                "reader_request_body_sha256",
                "provider_request_body_sha256",
            },
            set(comparison["changed_component_names"]),
        )
        components = {
            row["component"]: row["status"]
            for row in comparison["component_comparison"]
        }
        self.assertEqual("SHARED_EXACT", components["serializer_hash"])
        self.assertEqual("SHARED_EXACT", components["expanded_grid_sha256"])
        self.assertEqual("CHANGED_EXACT", components["task_contract_hash"])

    def test_no_sound_cross_task_token_bound_is_claimed(self) -> None:
        """Require exact sibling evidence instead of ratios or family inference."""
        self.assertEqual(
            "EXACT_CONTEXT_EVIDENCE_REQUIRED",
            self.analysis["REVPAR_CONTEXT_STATUS"],
        )
        self.assertEqual(
            "NO_SOUND_CROSS_TASK_TOKEN_BOUND", self.analysis["reason"]
        )
        assessment = self.analysis["token_upper_bound_assessment"]
        self.assertFalse(
            assessment[
                "repository_authorized_sound_cross_task_upper_bound_exists"
            ]
        )
        self.assertEqual("NOT_MEASURED", assessment["sibling_actual_prompt_tokens"])
        self.assertEqual(
            [],
            self.analysis["context_attestation_inventory"][
                "matching_sibling_attestation_ids"
            ],
        )
        encoded = json.dumps(self.analysis, sort_keys=True)
        self.assertNotIn("2.4385", encoded)
        self.assertNotIn("bytes_per_actual_prompt_token", encoded)

    def test_rebuild_is_deterministic_and_never_opens_provider(self) -> None:
        """Reconstruct both requests twice with every network opener untouched."""
        with mock.patch.object(
            ai_adapter, "_open_provider_request",
        ) as provider_opener:
            first = build_sibling_request_context_analysis(repo_root=REPO_ROOT)
            second = build_sibling_request_context_analysis(repo_root=REPO_ROOT)
        self.assertEqual(first, second)
        self.assertEqual(self.analysis, first)
        provider_opener.assert_not_called()
        self.assertEqual(
            {
                "real_model_provider_egress_count": 0,
                "paid_model_provider_call_count": 0,
                "real_SEC_egress_count": 0,
            },
            first["egress_counts"],
        )

    def test_pointer_names_the_content_addressed_current_analysis(self) -> None:
        """Keep old analyses immutable while only the pointer can advance."""
        pointer = json.loads(
            (REPO_ROOT / ANALYSIS_POINTER).read_text(encoding="utf-8")
        )
        self.assertEqual(pointer["analysis_id"], self.analysis["analysis_id"])


if __name__ == "__main__":
    unittest.main()
