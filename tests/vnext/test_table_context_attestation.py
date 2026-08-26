"""Verify the Stage C-B-derived exact context feasibility attestation."""

from __future__ import annotations

import copy
import json
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash
from vnext.requirements import ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS
from vnext.requirements import ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY
from vnext.table_context_attestation import ATTESTATION_POINTER
from vnext.table_context_attestation import EXACT_REQUEST_BINDING_FIELDS
from vnext.table_context_attestation import (
    build_table_context_feasibility_attestation,
)
from vnext.table_context_attestation import exact_request_binding
from vnext.table_context_attestation import current_exact_request_binding
from vnext.table_context_attestation import evaluate_context_feasibility
from vnext.table_context_attestation import (
    validate_table_context_feasibility_attestation,
)
from vnext.table_context_attestation import TableContextAttestationError
from vnext.table_context_measurement import build_table_context_measurement_plan


class TableContextAttestationTest(unittest.TestCase):
    """Prove exact derivation without provider, paid, or SEC egress."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the accepted revised Occupancy attestation."""
        pointer = json.loads(
            (REPO_ROOT / ATTESTATION_POINTER).read_text(encoding="utf-8")
        )
        cls.attestation = json.loads(
            (REPO_ROOT / pointer["attestation_path"]).read_text(
                encoding="utf-8"
            )
        )

    def test_attestation_is_mechanically_derived_from_stage_c_b(self) -> None:
        """Bind the full request, raw usage, terminal IDs, and no-credit flags."""
        attestation = self.attestation
        evidence = json.loads(
            (REPO_ROOT / attestation["measurement_evidence_path"]).read_text(
                encoding="utf-8"
            )
        )
        plan = json.loads(
            (REPO_ROOT / attestation["measurement_plan_path"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "sha256:0399b5034d4920a31d9391f36870eb6407a39e943454147f0e6b7f33c9813825",
            attestation["source_measurement_evidence_id"],
        )
        self.assertEqual(
            evidence["measurement_evidence_id"],
            attestation["source_measurement_evidence_id"],
        )
        self.assertEqual(
            plan["provider_request_body_sha256"],
            attestation["exact_provider_request_body_sha256"],
        )
        self.assertEqual(
            plan["catalog_task_contract_hash"],
            attestation["task_contract_hash"],
        )
        self.assertEqual(
            plan["system_prompt_hash"], attestation["prompt_hash"],
        )
        self.assertEqual(
            plan["output_schema_hash"], attestation["output_schema_hash"],
        )
        for field in (
            "actual_prompt_tokens",
            "actual_completion_tokens",
            "actual_total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ):
            self.assertEqual(evidence[field], attestation[field])
        self.assertEqual(161282, attestation["actual_prompt_tokens"])
        self.assertEqual(200000, attestation["context_budget_tokens"])
        self.assertEqual(38718, attestation["context_headroom_tokens"])
        self.assertTrue(attestation["measurement_authorization_consumed"])
        self.assertFalse(attestation["qualification_credit"])
        self.assertFalse(
            attestation["qualification_response_reuse_eligible"]
        )
        self.assertEqual(
            attestation["measurement_requirement_closure_hash"],
            attestation["requirement_closure_hash"],
        )
        self.assertEqual(
            attestation["measurement_protected_closure_hash"],
            attestation["protected_closure_hash"],
        )

    def test_attestation_and_pointer_are_content_addressed(self) -> None:
        """Recompute both current immutable identities from canonical bodies."""
        pointer = json.loads(
            (REPO_ROOT / ATTESTATION_POINTER).read_text(encoding="utf-8")
        )
        attestation = json.loads(
            (REPO_ROOT / pointer["attestation_path"]).read_text(
                encoding="utf-8"
            )
        )
        pointer_body = {
            key: value for key, value in pointer.items() if key != "pointer_id"
        }
        attestation_body = {
            key: value
            for key, value in attestation.items()
            if key != "attestation_id"
        }
        self.assertEqual(content_hash(value=pointer_body), pointer["pointer_id"])
        self.assertEqual(
            content_hash(value=attestation_body), attestation["attestation_id"]
        )
        self.assertEqual(pointer["attestation_id"], attestation["attestation_id"])

    def test_attestation_rebuild_is_deterministic(self) -> None:
        """Reject a new measurement-derived record after grants are consumed."""
        with self.assertRaises(TableContextAttestationError):
            build_table_context_feasibility_attestation(repo_root=REPO_ROOT)

    def test_exact_binding_projection_matches_d07_policy(self) -> None:
        """Expose exactly the fields that D-07 requires future requests to match."""
        attestation = self.attestation
        binding = exact_request_binding(attestation=attestation)
        self.assertEqual(set(EXACT_REQUEST_BINDING_FIELDS), set(binding))
        self.assertEqual(
            list(EXACT_REQUEST_BINDING_FIELDS),
            ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY[
                "exact_attestation_path"
            ]["required_exact_equalities"],
        )
        self.assertEqual(
            "ONE_EXACT_TASK_REQUEST",
            attestation["invalidation_policy"]["attestation_scope"],
        )
        self.assertEqual(
            "FORBIDDEN",
            attestation["invalidation_policy"][
                "measurement_response_qualification_reuse"
            ],
        )

    def test_scope_bound_prompt_invalidates_prior_occupancy_binding(self) -> None:
        """Keep the prior schema-v3 proof historical after prompt drift."""
        with self.assertRaises(TableContextAttestationError):
            current_exact_request_binding(
                repo_root=REPO_ROOT,
                task_contract_id="lodging_occupancy_table_v2",
            )
        current = build_table_context_measurement_plan(
            repo_root=REPO_ROOT,
            task_contract_id="lodging_occupancy_table_v2",
        )
        self.assertNotEqual(
            self.attestation["prompt_hash"], current["system_prompt_hash"],
        )

    def test_old_occupancy_request_blocks_pending_new_measurement(self) -> None:
        """Reject the old schema-v3 request under the new frozen prompt."""
        binding = exact_request_binding(attestation=self.attestation)
        result = evaluate_context_feasibility(
            repo_root=REPO_ROOT,
            estimated_input_tokens=394837,
            max_estimated_input_tokens=200000,
            request_binding=binding,
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual(
            "EXACT_CONTEXT_ATTESTATION_INVALID", result["blocking_reason_code"],
        )
        current = build_table_context_measurement_plan(
            repo_root=REPO_ROOT,
            task_contract_id="lodging_occupancy_table_v2",
        )
        self.assertEqual(394837, current["estimated_input_tokens"])

    def test_old_revpar_request_blocks_pending_new_measurement(self) -> None:
        """Keep the prior RevPAR proof historical after prompt drift."""
        row = ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS[1]
        attestation = json.loads((
            REPO_ROOT
            / "artifacts/vnext/table_stage_c_evidence/"
            "context_feasibility_attestations"
            / (row["attestation_id"].split(":", maxsplit=1)[1] + ".json")
        ).read_text(encoding="utf-8"))
        result = evaluate_context_feasibility(
            repo_root=REPO_ROOT,
            estimated_input_tokens=394828,
            max_estimated_input_tokens=200000,
            request_binding=exact_request_binding(attestation=attestation),
        )
        self.assertEqual(161263, attestation["actual_prompt_tokens"])
        self.assertEqual(200000, attestation["context_budget_tokens"])
        self.assertEqual(38737, attestation["context_headroom_tokens"])
        self.assertIsNone(attestation["source_stage_c_b_packet_id"])
        self.assertIsNone(attestation["source_stage_c_b_packet_path"])
        self.assertFalse(attestation["qualification_credit"])
        self.assertFalse(
            attestation["qualification_response_reuse_eligible"]
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual(
            "EXACT_CONTEXT_ATTESTATION_REQUIRED", result["blocking_reason_code"],
        )
        changed = copy.deepcopy(exact_request_binding(attestation=attestation))
        changed["provider_request_body_sha256"] = "0" * 64
        blocked = evaluate_context_feasibility(
            repo_root=REPO_ROOT,
            estimated_input_tokens=394828,
            max_estimated_input_tokens=200000,
            request_binding=changed,
        )
        self.assertEqual("BLOCKED", blocked["status"])
        self.assertIn(
            "provider_request_body_sha256", blocked["drift_fields"],
        )

    def test_every_exact_binding_drift_blocks_before_egress(self) -> None:
        """Reject source/task/prompt/schema/transport/request mutations."""
        attestation = self.attestation
        baseline = exact_request_binding(attestation=attestation)
        mutations = {
            "source_sha256": "0" * 64,
            "task_contract_hash": "sha256:" + "0" * 64,
            "prompt_hash": "sha256:" + "0" * 64,
            "output_schema_hash": "sha256:" + "0" * 64,
            "serializer_identity": "table_payload_serialization_v3",
            "serializer_hash": "0" * 64,
            "provider": "other-provider",
            "model": "other-model",
            "api": "responses",
            "provider_request_body_sha256": "0" * 64,
            "requirement_closure_hash": "sha256:" + "0" * 64,
            "protected_closure_hash": "sha256:" + "0" * 64,
        }
        for field, replacement in mutations.items():
            with self.subTest(field=field):
                changed = copy.deepcopy(baseline)
                changed[field] = replacement
                result = evaluate_context_feasibility(
                    repo_root=REPO_ROOT,
                    estimated_input_tokens=392447,
                    max_estimated_input_tokens=200000,
                    request_binding=changed,
                )
                self.assertEqual("BLOCKED", result["status"])
                self.assertIn(field, result["drift_fields"])

    def test_unrelated_and_revpar_requests_cannot_borrow_attestation(self) -> None:
        """Keep the alternative scoped to one occupancy task/request."""
        attestation = self.attestation
        for field, replacement in (
            ("family_id", "unrelated_table_family"),
            ("task_contract_id", "lodging_revpar_table_v2"),
        ):
            binding = exact_request_binding(attestation=attestation)
            binding[field] = replacement
            result = evaluate_context_feasibility(
                repo_root=REPO_ROOT,
                estimated_input_tokens=392438,
                max_estimated_input_tokens=200000,
                request_binding=binding,
            )
            self.assertEqual("BLOCKED", result["status"])
            if field == "task_contract_id":
                self.assertIn(
                    "provider_request_body_sha256", result["drift_fields"],
                )
                self.assertIn("task_contract_hash", result["drift_fields"])
            else:
                self.assertIn(field, result["drift_fields"])

    def test_default_estimated_bound_does_not_need_attestation(self) -> None:
        """Preserve the ordinary inclusive 200000 path unchanged."""
        result = evaluate_context_feasibility(
            repo_root=REPO_ROOT,
            estimated_input_tokens=200000,
            max_estimated_input_tokens=200000,
            request_binding=None,
        )
        self.assertEqual("PASSED", result["status"])
        self.assertEqual("ESTIMATED_BOUND", result["evidence_basis"])


if __name__ == "__main__":
    unittest.main()
