"""Exercise WB-5 generic exact-enum scope normalization and review gates."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tests.vnext.common import compiled_specs, reader_response, reviewed_fixture
from tests.vnext.common import sample_asset
from vnext.canonical import content_hash
from vnext.evidence import check_evidence
from vnext.reader import validate_reader_output
from vnext.render import build_review_context, render_review_markdown
from vnext.review import build_review_unit, create_system_review_decision
from vnext.review import ReviewError
from vnext.requirements import load_requirement_snapshot
from vnext.scope_contract import exact_enum_alias
from vnext.scope_contract import scope_satisfies_contract
from vnext.scope_contract import validate_scope_contract
from vnext.specs import SEMANTIC_SET_PATHS


REPO_ROOT = Path(__file__).resolve().parents[2]


class ScopeContractTest(unittest.TestCase):
    """Keep raw scope claims separate from canonical observation scope."""

    def test_exact_enum_alias_is_the_only_automatic_normalizer(self) -> None:
        """Resolve a declared literal and reject numeric-looking undeclared text."""
        contract = {
            "scope_contract_version": "2",
            "required_dimensions": ["confidence_level", "holding_period"],
            "allowed_dimensions": ["confidence_level", "holding_period"],
            "exact_enum_aliases": {
                "confidence_level": {"ninety_nine_percent": ["99%"]},
                "holding_period": {"one_day": ["one day"]},
            },
            "selection_preference": {
                "dimension_order": ["confidence_level", "holding_period"],
                "prefer_complete_required_dimensions": True,
            },
            "cross_dimension_constraints": [],
        }
        validated = validate_scope_contract(value=contract)
        self.assertEqual(
            "ninety_nine_percent",
            exact_enum_alias(
                contract=validated,
                dimension="confidence_level",
                raw_value="99%",
            ),
        )
        self.assertIsNone(
            exact_enum_alias(
                contract=validated,
                dimension="confidence_level",
                raw_value="0.99",
            )
        )
        self.assertTrue(
            scope_satisfies_contract(
                contract=validated,
                normalized_scope={
                    "confidence_level": "ninety_nine_percent",
                    "holding_period": "one_day",
                },
            )
        )

    def test_unknown_alias_requires_human_and_never_system_approval(self) -> None:
        """Keep an unknown raw alias in REVIEW_REQUIRED rather than quality."""
        fixture = reviewed_fixture()
        scope_contract = copy.deepcopy(
            compiled_specs()["DISCLOSURE"]["compiled"]["scope_contract"]
        )
        scope_contract["exact_enum_aliases"]["geography"]["worldwide"] = [
            "Global"
        ]
        candidate = validate_reader_output(
            response_text=reader_response(asset=fixture["asset"]).decode(
                "utf-8"
            ),
            attempt_id="attempt:scope:unknown-alias",
            required_roles=["occupancy", "revpar", "adr"],
            scope_contract=scope_contract,
            source_reference_ids=fixture["manifest"]["source_reference_ids"],
            derived_asset_ids=[fixture["asset"]["derived_asset_id"]],
        )
        evidence = check_evidence(
            candidate=candidate,
            derived_asset=fixture["asset"],
            reader_manifest=fixture["manifest"],
            reader_payload_body=fixture["payload"]["body"],
            source_references=[fixture["source"]],
            identity_constraints=compiled_specs()["DISCLOSURE"]["compiled"][
                "identity_constraints"
            ],
            scope_contract=scope_contract,
        )
        self.assertEqual("REVIEW_REQUIRED", candidate["status"])
        self.assertEqual("PASS", evidence["status"])
        self.assertEqual(["geography"], evidence["unresolved_scope_dimensions"])
        self.assertFalse(evidence["system_approval_eligible"])
        compiled = copy.deepcopy(compiled_specs()["DISCLOSURE"])
        compiled["compiled"]["scope_contract"] = scope_contract
        compiled["spec_semantic_hash"] = content_hash(
            value=compiled["compiled"],
            set_paths=SEMANTIC_SET_PATHS,
        )
        context = build_review_context(
            candidate=candidate,
            evidence_check=evidence,
            derived_asset=fixture["asset"],
            source_bindings=[fixture["source"]],
            spec_semantic_hash=compiled["spec_semantic_hash"],
            required_claims=compiled["compiled"]["required_claims"],
        )
        rendered = render_review_markdown(
            review_context=context["review_context"],
        )
        unit = build_review_unit(
            candidate=candidate,
            evidence_check=evidence,
            source_bindings=[fixture["source"]],
            compiled_spec=compiled,
            review_context_hash=context["review_context_hash"],
            rendered_review_hash=rendered["rendered_review_hash"],
            renderer_semantic_version=rendered[
                "review_renderer_semantic_version"
            ],
        )
        requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1",
        )
        with self.assertRaises(ReviewError):
            create_system_review_decision(
                review_unit=unit,
                required_claims=unit["required_claims"],
                decided_at_utc="2026-08-21T00:00:00Z",
                requirement=requirement,
            )

    def test_scope_evidence_must_replay_exact_raw_text(self) -> None:
        """Reject alias-like text if a locator rereads different raw bytes."""
        asset = sample_asset()
        response = json.loads(reader_response(asset=asset).decode("utf-8"))
        response["candidates"][0]["scope_evidence_locators"][0][
            "raw_text"
        ] = "Comparable"
        fixture = reviewed_fixture(
            asset=asset,
            response_bytes=json.dumps(response).encode("utf-8"),
        )
        self.assertEqual("REJECTED", fixture["evidence"]["status"])
        self.assertIn(
            "SCOPE_LABEL_TEXT_MISMATCH",
            fixture["evidence"]["reason_codes"],
        )


if __name__ == "__main__":
    unittest.main()
