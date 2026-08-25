"""Verify the Stage C-B-derived exact context feasibility attestation."""

from __future__ import annotations

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
from vnext.table_context_attestation import (
    validate_table_context_feasibility_attestation,
)


class TableContextAttestationTest(unittest.TestCase):
    """Prove exact derivation without provider, paid, or SEC egress."""

    def test_attestation_is_mechanically_derived_from_stage_c_b(self) -> None:
        """Bind the full request, raw usage, terminal IDs, and no-credit flags."""
        attestation = validate_table_context_feasibility_attestation(
            repo_root=REPO_ROOT,
        )
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
        attestation = validate_table_context_feasibility_attestation(
            repo_root=REPO_ROOT,
        )
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


if __name__ == "__main__":
    unittest.main()
