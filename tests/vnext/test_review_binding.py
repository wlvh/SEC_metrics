"""Whole ReviewUnit approval binding and immutable decision-chain tests."""

from __future__ import annotations

import copy
import unittest
from typing import Dict

from tests.vnext.common import REPO_ROOT, compiled_specs, reader_response
from tests.vnext.common import reviewed_fixture
from vnext.canonical import content_hash
from vnext.render import build_review_context, render_review_markdown
from vnext.review import ReviewError, build_review_unit
from vnext.review import create_system_review_decision
from vnext.review import create_review_decision, effective_review_decision
from vnext.review import validate_decision_binding
from vnext.requirements import load_requirement_snapshot


def review_unit_fixture(*, unresolved: bool = False) -> Dict[str, object]:
    """Build one mechanically passing unit with optional unresolved context.

    Args:
        unresolved: Whether the Reader disclosed an unresolved competing claim.

    Returns:
        ReviewUnit and its exact required claims.
    """
    compiled_spec = compiled_specs()["DISCLOSURE"]
    required = compiled_spec["compiled"]["required_claims"]
    base = reviewed_fixture()
    if unresolved:
        base = reviewed_fixture(
            asset=base["asset"],
            response_bytes=reader_response(
                asset=base["asset"],
                unresolved=[{"description": "ambiguous presentation"}],
            ),
        )
    context = build_review_context(
        candidate=base["candidate"],
        evidence_check=base["evidence"],
        derived_asset=base["asset"],
        source_bindings=[base["source"]],
        spec_semantic_hash=compiled_spec["spec_semantic_hash"],
        required_claims=required,
    )
    rendered = render_review_markdown(
        review_context=context["review_context"],
    )
    unit = build_review_unit(
        candidate=base["candidate"],
        evidence_check=base["evidence"],
        source_bindings=[base["source"]],
        compiled_spec=compiled_spec,
        review_context_hash=str(context["review_context_hash"]),
        rendered_review_hash=str(rendered["rendered_review_hash"]),
        renderer_semantic_version=str(
            rendered["review_renderer_semantic_version"]
        ),
    )
    return unit, required


class ReviewBindingTest(unittest.TestCase):
    """Prove HUMAN decisions bind visible context as one unit."""

    def test_approval_requires_exact_claims_and_human_identity(self) -> None:
        """Fail on partial claims or invalid reviewer identity."""
        unit, required = review_unit_fixture()
        with self.assertRaisesRegex(ReviewError, "exactly satisfy"):
            create_review_decision(
                review_unit=unit,
                decision="APPROVE",
                approved_claims={"geography": "worldwide"},
                required_claims=required,
                reviewer_id="human:reviewer:001",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Scope and period labels reviewed.",
                supersedes_decision_id=None,
            )
        with self.assertRaisesRegex(ReviewError, "reviewer_id"):
            create_review_decision(
                review_unit=unit,
                decision="APPROVE",
                approved_claims=required,
                required_claims=required,
                reviewer_id="x",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Scope and period labels reviewed.",
                supersedes_decision_id=None,
            )

    def test_optional_system_decision_is_auditable(self) -> None:
        """Keep the no-human path explicitly distinct from HUMAN approval."""
        unit, required = review_unit_fixture()
        requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1",
        )
        decision = create_system_review_decision(
            review_unit=unit,
            required_claims=required,
            decided_at_utc="2026-08-17T09:21:18Z",
            requirement=requirement,
        )
        self.assertEqual("SYSTEM", decision["reviewer_type"])
        self.assertEqual("APPROVE", decision["decision"])
        self.assertEqual(required, decision["approved_claims"])
        validate_decision_binding(review_unit=unit, decision=decision)

    def test_caller_cannot_redefine_the_units_required_claims(self) -> None:
        """Bind required claims to ReviewUnit instead of a caller file."""
        unit, _required = review_unit_fixture()
        partial = {"geography": "worldwide"}
        with self.assertRaisesRegex(ReviewError, "required claims"):
            create_review_decision(
                review_unit=unit,
                decision="APPROVE",
                approved_claims=partial,
                required_claims=partial,
                reviewer_id="human:reviewer:001",
                decided_at_utc="2026-07-29T13:00:00Z",
                reason="Wrong external required-claims file.",
                supersedes_decision_id=None,
            )

    def test_review_unit_cannot_substitute_candidate_source(self) -> None:
        """Bind the human context to the Candidate's exact source list."""
        fixture = reviewed_fixture()
        source = copy.deepcopy(fixture["source"])
        source["source_role"] = "substituted_primary"
        identity_fields = (
            "raw_asset_id",
            "company_id",
            "source_url",
            "accession",
            "document_name",
            "source_role",
        )
        source["source_reference_id"] = content_hash(
            value={key: source[key] for key in identity_fields}
        )
        with self.assertRaisesRegex(ReviewError, "exact set"):
            build_review_unit(
                candidate=fixture["candidate"],
                evidence_check=fixture["evidence"],
                source_bindings=[source],
                compiled_spec=compiled_specs()["DISCLOSURE"],
                review_context_hash="a" * 64,
                rendered_review_hash="b" * 64,
                renderer_semantic_version="1",
            )

    def test_review_unit_rejects_claims_detached_from_spec(self) -> None:
        """Do not pair a real Spec hash with weakened required claims."""
        fixture = reviewed_fixture()
        compiled_spec = copy.deepcopy(compiled_specs()["DISCLOSURE"])
        compiled_spec["compiled"]["required_claims"] = {
            "period_role": "current_fiscal_year"
        }
        with self.assertRaisesRegex(ReviewError, "compiled Spec"):
            build_review_unit(
                candidate=fixture["candidate"],
                evidence_check=fixture["evidence"],
                source_bindings=[fixture["source"]],
                compiled_spec=compiled_spec,
                review_context_hash="a" * 64,
                rendered_review_hash="b" * 64,
                renderer_semantic_version="1",
            )

    def test_context_change_invalidates_old_decision(self) -> None:
        """Invalidate approval when unresolved or rendered context changes."""
        original, required = review_unit_fixture()
        decision = create_review_decision(
            review_unit=original,
            decision="APPROVE",
            approved_claims=required,
            required_claims=required,
            reviewer_id="human:reviewer:001",
            decided_at_utc="2026-07-29T13:00:00Z",
            reason="Reviewed exact context.",
            supersedes_decision_id=None,
        )
        changed, _required = review_unit_fixture(unresolved=True)
        self.assertNotEqual(
            original["review_unit_hash"], changed["review_unit_hash"],
        )
        with self.assertRaisesRegex(ReviewError, "binding changed"):
            validate_decision_binding(
                review_unit=changed, decision=decision,
            )

    def test_parallel_effective_decisions_fail_closed(self) -> None:
        """Reject two root decisions rather than select one."""
        unit, required = review_unit_fixture()
        first = create_review_decision(
            review_unit=unit,
            decision="APPROVE",
            approved_claims=required,
            required_claims=required,
            reviewer_id="human:reviewer:001",
            decided_at_utc="2026-07-29T13:00:00Z",
            reason="First independent review.",
            supersedes_decision_id=None,
        )
        second = create_review_decision(
            review_unit=unit,
            decision="REJECT",
            approved_claims={},
            required_claims=required,
            reviewer_id="human:reviewer:002",
            decided_at_utc="2026-07-29T13:01:00Z",
            reason="Second independent review.",
            supersedes_decision_id=None,
        )
        with self.assertRaisesRegex(ReviewError, "one root"):
            effective_review_decision(
                review_unit=unit, decisions=[first, second],
            )

    def test_linear_supersedes_chain_has_one_effective_tip(self) -> None:
        """Resolve one immutable correction chain to its final decision."""
        unit, required = review_unit_fixture()
        first = create_review_decision(
            review_unit=unit,
            decision="REJECT",
            approved_claims={},
            required_claims=required,
            reviewer_id="human:reviewer:001",
            decided_at_utc="2026-07-29T13:00:00Z",
            reason="Initial rejection.",
            supersedes_decision_id=None,
        )
        second = create_review_decision(
            review_unit=unit,
            decision="APPROVE",
            approved_claims=required,
            required_claims=required,
            reviewer_id="human:reviewer:001",
            decided_at_utc="2026-07-29T13:05:00Z",
            reason="Correction after re-review.",
            supersedes_decision_id=str(first["review_decision_id"]),
        )
        effective = effective_review_decision(
            review_unit=unit, decisions=[first, second],
        )
        self.assertEqual(
            second["review_decision_id"], effective["review_decision_id"]
        )


if __name__ == "__main__":
    unittest.main()
