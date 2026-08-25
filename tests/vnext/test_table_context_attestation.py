"""Verify the Stage C-B-derived exact context feasibility attestation."""

from __future__ import annotations

import copy
import json
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash
from vnext.requirements import ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY
from vnext.table_context_attestation import ATTESTATION_POINTER
from vnext.table_context_attestation import EXACT_REQUEST_BINDING_FIELDS
from vnext.table_context_attestation import (
    build_table_context_feasibility_attestation,
)
from vnext.table_context_attestation import exact_request_binding
from vnext.table_context_attestation import evaluate_context_feasibility
from vnext.table_context_attestation import (
    validate_table_context_feasibility_attestation,
)


class TableContextAttestationTest(unittest.TestCase):
    """Prove exact derivation without provider, paid, or SEC egress."""

    @classmethod
    def setUpClass(cls) -> None:
        """Validate the immutable attestation once for focused field tests."""
        cls.attestation = validate_table_context_feasibility_attestation(
            repo_root=REPO_ROOT,
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
            "sha256:bd5c4e1e1fb302ce539c2ae7aa88b67c2b366c419436253b9ebb56f56dbf9795",
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
        self.assertEqual(160937, attestation["actual_prompt_tokens"])
        self.assertEqual(200000, attestation["context_budget_tokens"])
        self.assertEqual(39063, attestation["context_headroom_tokens"])
        self.assertTrue(attestation["measurement_authorization_consumed"])
        self.assertFalse(attestation["qualification_credit"])
        self.assertFalse(
            attestation["qualification_response_reuse_eligible"]
        )
        self.assertNotEqual(
            attestation["measurement_requirement_closure_hash"],
            attestation["requirement_closure_hash"],
        )
        self.assertNotEqual(
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
        """Repeated offline reconstruction yields the same immutable object."""
        first = build_table_context_feasibility_attestation(repo_root=REPO_ROOT)
        second = build_table_context_feasibility_attestation(repo_root=REPO_ROOT)
        self.assertEqual(first, second)

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

    def test_exact_occupancy_request_passes_above_estimated_bound(self) -> None:
        """Admit only the measured request via provider-reported exact binding."""
        attestation = self.attestation
        result = evaluate_context_feasibility(
            repo_root=REPO_ROOT,
            estimated_input_tokens=392447,
            max_estimated_input_tokens=200000,
            request_binding=exact_request_binding(attestation=attestation),
        )
        self.assertEqual("PASSED", result["status"])
        self.assertEqual(
            "PROVIDER_REPORTED_EXACT_BINDING", result["evidence_basis"]
        )
        self.assertEqual(160937, result["attested_actual_prompt_tokens"])

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
