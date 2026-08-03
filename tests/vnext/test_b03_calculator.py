"""Spec-driven B03 role resolution, guard, quality, and parity tests."""

from __future__ import annotations

import copy
import decimal
import unittest
from typing import Dict, Mapping, Optional, Sequence, Tuple

from tests.vnext.common import compiled_specs
from vnext.calculator import calculate_metric
from vnext.canonical import content_hash
from vnext.observations import scope_key, structured_observation


PERIOD_START = "2025-01-01"
PERIOD_END = "2025-12-31"
ACCESSION = "0001048286-26-000007"
ENTITY = "entity:fixture"
SCOPE = {"consolidation": "entity"}


def fact(
    *,
    concept: str,
    value: str,
    accession: str = ACCESSION,
    entity: str = ENTITY,
    duration_days: int = 365,
    unit: str = "USD",
) -> Dict[str, object]:
    """Build one exact structured candidate fact.

    Args:
        concept: Qualified XBRL concept.
        value: Fixed-point value.
        accession: Filing accession.
        entity: Filing entity identity.
        duration_days: Fact duration.
        unit: Fact unit.

    Returns:
        Strict calculator fact mapping.
    """
    token = concept.split(":", 1)[-1]
    return {
        "accession": accession,
        "concept": concept,
        "duration_days": duration_days,
        "entity": entity,
        "fact_id": "fact:" + token + ":" + value.replace("-", "neg"),
        "filed": "2026-02-26",
        "fiscal_period": "FY",
        "form": "10-K",
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "source_binding": {
            "raw_asset_id": "sha256:" + "a" * 64,
            "source_reference_id": "sha256:" + "b" * 64,
            "accession": accession,
            "document_name": "companyfacts.json",
            "source_role": "companyfacts",
            "entity": entity,
        },
        "unit": unit,
        "value": value,
    }


def calculation_inputs(
    *,
    revenue: str,
    company_id: str = "company_fixture",
    accession: str = ACCESSION,
    entity: str = ENTITY,
    duration_days: int = 365,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Build a target and the unique reusable B01 observation.

    Args:
        revenue: Revenue observation value.
        company_id: Logical company identity.
        accession: Target filing accession.
        entity: Target filing entity.
        duration_days: Revenue duration evidence.

    Returns:
        Exact calculation target and B01 observation.
    """
    target = {
        "company_id": company_id,
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "accession": accession,
        "entity": entity,
        "scope": SCOPE,
        "scope_key": scope_key(scope=SCOPE),
    }
    observation = structured_observation(
        metric_id="B01",
        semantic_role="revenue",
        company_id=company_id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        scope=SCOPE,
        value=revenue,
        unit="USD",
        quality="EXACT",
        source_binding={
            "raw_asset_id": "sha256:" + "a" * 64,
            "source_reference_id": "sha256:" + "b" * 64,
            "accession": accession,
            "document_name": "companyfacts.json",
            "source_role": "companyfacts",
            "entity": entity,
            "duration_days": duration_days,
        },
    )
    return target, observation


def calculate_b03(
    *,
    facts: Sequence[Mapping[str, object]],
    revenue: str,
    company_id: str = "company_fixture",
    target_accession: str = ACCESSION,
    target_entity: str = ENTITY,
    revenue_duration_days: int = 365,
    observations: Optional[Sequence[Mapping[str, object]]] = None,
) -> Tuple[
    Dict[str, object], Dict[str, object], Sequence[Mapping[str, object]]
]:
    """Execute B03 with a reusable B01 observation and declared traits.

    Args:
        facts: Structured candidate fact set.
        revenue: B01 value used when observations are not supplied.
        company_id: Logical company identity.
        target_accession: Target accession.
        target_entity: Target entity.
        revenue_duration_days: B01 duration evidence.
        observations: Optional explicit reusable observation sequence.

    Returns:
        MetricResult, ExecutionTrace, and selected observations.
    """
    target, revenue_observation = calculation_inputs(
        revenue=revenue,
        company_id=company_id,
        accession=target_accession,
        entity=target_entity,
        duration_days=revenue_duration_days,
    )
    selected_observations = (
        [revenue_observation] if observations is None else list(observations)
    )
    return calculate_metric(
        compiled_spec=compiled_specs()["B03"],
        target=target,
        company_traits=["non_financial"],
        structured_facts=facts,
        verified_observations=selected_observations,
    )


class B03CalculatorTest(unittest.TestCase):
    """Prove B03 behavior is generic, declarative, guarded, and replayable."""

    def test_b01_preserves_selected_reported_currency(self) -> None:
        """Match legacy B01 by carrying EUR rather than relabeling it USD."""
        target, _observation = calculation_inputs(revenue="100")
        result, _trace, observations = calculate_metric(
            compiled_spec=compiled_specs()["B01"],
            target=target,
            company_traits=["non_financial"],
            structured_facts=[
                fact(concept="us-gaap:Revenues", value="100", unit="EUR")
            ],
            verified_observations=[],
        )
        self.assertEqual("PUBLISHED", result["publication"])
        self.assertEqual("EUR", result["unit"])
        self.assertEqual("EUR", observations[0]["unit"])

    def test_b03_mixed_component_currency_fails_closed(self) -> None:
        """Keep the declared B03 compatible-units guard executable."""
        _target, revenue_observation = calculation_inputs(revenue="1000")
        revenue_observation["unit"] = "EUR"
        body = {
            key: revenue_observation[key]
            for key in (
                "semantic_role",
                "metric_id",
                "company_id",
                "period_start",
                "period_end",
                "scope",
                "scope_key",
                "value",
                "unit",
                "source_binding",
            )
        }
        revenue_observation["observation_id"] = content_hash(value=body)
        result, _trace, _observations = calculate_b03(
            facts=[
                fact(concept="us-gaap:OperatingIncomeLoss", value="100"),
                fact(
                    concept="us-gaap:DepreciationDepletionAndAmortization",
                    value="20",
                ),
            ],
            revenue="1000",
            observations=[revenue_observation],
        )
        self.assertEqual("WITHHELD", result["publication"])
        self.assertEqual("MISMATCH_UNIT", result["reason_code"])

    def test_direct_combined_dna_wins_without_double_counting(self) -> None:
        """Use combined D&A once even when amortization also exists."""
        facts = [
            fact(concept="us-gaap:OperatingIncomeLoss", value="100"),
            fact(
                concept="us-gaap:DepreciationDepletionAndAmortization",
                value="50",
            ),
            fact(concept="us-gaap:AmortizationOfIntangibleAssets", value="20"),
        ]
        result, trace, observations = calculate_b03(
            facts=facts, revenue="1000",
        )
        self.assertEqual("0.15", result["value"])
        self.assertEqual("EXACT", result["quality"])
        roles = [item["semantic_role"] for item in observations]
        self.assertNotIn("amortization", roles)
        formula = [
            step
            for step in trace["steps"]
            if step["event"] == "FORMULA_RESULT"
        ][0]
        self.assertEqual(
            "50", formula["resolved_values"]["depreciation_and_amortization"],
        )

    def test_marriott_exact_and_pfizer_approx_match_legacy_anchors(
        self,
    ) -> None:
        """Match two legacy B03 anchors through declared branches."""
        marriott_facts = [
            fact(concept="us-gaap:OperatingIncomeLoss", value="4141000000"),
            fact(concept="us-gaap:Depreciation", value="145000000"),
            fact(
                concept="us-gaap:AmortizationOfIntangibleAssets",
                value="313000000",
            ),
        ]
        marriott, _trace, _observations = calculate_b03(
            facts=marriott_facts,
            revenue="26186000000",
            company_id="marriott_international",
        )
        self.assertEqual(
            "0.1756281982738868097456656229", marriott["value"],
        )
        self.assertEqual("EXACT", marriott["quality"])

        pfizer_accession = "0000078003-26-000026"
        pfizer_entity = "entity:pfizer"
        pfizer_facts = [
            fact(
                concept=(
                    "us-gaap:IncomeLossFromContinuingOperationsBefore"
                    "IncomeTaxesExtraordinaryItemsNoncontrollingInterest"
                ),
                value="7520000000",
                accession=pfizer_accession,
                entity=pfizer_entity,
            ),
            fact(
                concept="us-gaap:OtherNonoperatingIncomeExpense",
                value="-6724000000",
                accession=pfizer_accession,
                entity=pfizer_entity,
            ),
            fact(
                concept="us-gaap:DepreciationDepletionAndAmortization",
                value="6592000000",
                accession=pfizer_accession,
                entity=pfizer_entity,
            ),
        ]
        pfizer, pfizer_trace, _observations = calculate_b03(
            facts=pfizer_facts,
            revenue="62579000000",
            company_id="pfizer",
            target_accession=pfizer_accession,
            target_entity=pfizer_entity,
        )
        self.assertEqual(
            "0.3329551446971028619824541779", pfizer["value"],
        )
        self.assertEqual("APPROX", pfizer["quality"])
        self.assertIn(
            "CROSS_CHECK_UNAVAILABLE",
            [step["event"] for step in pfizer_trace["steps"]],
        )

    def test_cross_check_relative_boundary_is_inclusive(self) -> None:
        """Accept 0.99/1.00% and withhold 1.01% in cross-check."""
        for expected_oi, expected_publication in (
            ("100.99", "PUBLISHED"),
            ("101", "PUBLISHED"),
            ("101.01", "WITHHELD"),
        ):
            facts = [
                fact(
                    concept=(
                        "us-gaap:IncomeLossFromContinuingOperationsBefore"
                        "IncomeTaxesExtraordinaryItemsNoncontrollingInterest"
                    ),
                    value="200",
                ),
                fact(
                    concept="us-gaap:OtherNonoperatingIncomeExpense",
                    value="100",
                ),
                fact(
                    concept="us-gaap:DepreciationDepletionAndAmortization",
                    value="20",
                ),
                fact(
                    concept="us-gaap:CostsAndExpenses",
                    value=str(
                        decimal.Decimal("1000") - decimal.Decimal(expected_oi)
                    ),
                ),
            ]
            with self.subTest(expected_oi=expected_oi):
                result, trace, _observations = calculate_b03(
                    facts=facts, revenue="1000",
                )
                self.assertEqual(expected_publication, result["publication"])
                check_steps = [
                    step
                    for step in trace["steps"]
                    if step["event"] == "CROSS_CHECK_EVALUATED"
                ]
                self.assertEqual(1, len(check_steps))

    def test_cross_accession_is_withheld_and_zero_is_not_meaningful(
        self,
    ) -> None:
        """Enforce source equality and preserve zero semantics."""
        facts = [
            fact(
                concept="us-gaap:OperatingIncomeLoss",
                value="100",
                accession="0000000000-25-999999",
            ),
            fact(
                concept="us-gaap:DepreciationDepletionAndAmortization",
                value="20",
            ),
        ]
        mismatched, _trace, _observations = calculate_b03(
            facts=facts, revenue="1000",
        )
        self.assertEqual("WITHHELD", mismatched["publication"])
        self.assertEqual("MISMATCH_ACCESSION", mismatched["reason_code"])

        zero_facts = [
            fact(concept="us-gaap:OperatingIncomeLoss", value="100"),
            fact(
                concept="us-gaap:DepreciationDepletionAndAmortization",
                value="20",
            ),
        ]
        zero, _trace, _observations = calculate_b03(
            facts=zero_facts, revenue="0",
        )
        self.assertEqual("PUBLISHED", zero["publication"])
        self.assertEqual("NOT_MEANINGFUL", zero["quality"])
        self.assertEqual("DENOMINATOR_ZERO", zero["reason_code"])

    def test_nonannual_duration_and_duplicate_b01_fail_closed(self) -> None:
        """Expose nonannual duration and withhold ambiguous reuse."""
        short_facts = [
            fact(
                concept="us-gaap:OperatingIncomeLoss",
                value="100",
                duration_days=200,
            ),
            fact(
                concept="us-gaap:DepreciationDepletionAndAmortization",
                value="20",
                duration_days=200,
            ),
        ]
        short, _trace, _observations = calculate_b03(
            facts=short_facts, revenue="1000",
        )
        self.assertEqual("NOT_MEANINGFUL", short["quality"])
        self.assertEqual("ANNUAL_DURATION_OUT_OF_RANGE", short["reason_code"])

        target, revenue_observation = calculation_inputs(revenue="1000")
        duplicate = dict(revenue_observation)
        ambiguous, _trace, _observations = calculate_metric(
            compiled_spec=compiled_specs()["B03"],
            target=target,
            company_traits=["non_financial"],
            structured_facts=short_facts,
            verified_observations=[revenue_observation, duplicate],
        )
        self.assertEqual("WITHHELD", ambiguous["publication"])
        self.assertEqual("REUSE_CARDINALITY_FAILED", ambiguous["reason_code"])

    def test_tied_facts_with_different_provenance_are_ambiguous(self) -> None:
        """Do not let input order choose between distinct tied facts."""
        first = fact(concept="us-gaap:OperatingIncomeLoss", value="100")
        second = copy.deepcopy(first)
        second["source_binding"]["document_name"] = "different.json"
        dna = fact(
            concept="us-gaap:DepreciationDepletionAndAmortization",
            value="20",
        )
        for ordered in ([first, second, dna], [second, first, dna]):
            with self.subTest(first_document=ordered[0]["source_binding"]):
                result, _trace, _observations = calculate_b03(
                    facts=ordered, revenue="1000",
                )
                self.assertEqual("WITHHELD", result["publication"])
                self.assertEqual(
                    "ALL_BRANCHES_REJECTED", result["reason_code"]
                )

    def test_extension_namespace_cannot_impersonate_approved_concept(
        self,
    ) -> None:
        """Do not match a custom extension by local-name coincidence."""
        result, _trace, _observations = calculate_b03(
            facts=[
                fact(
                    concept="custom:OperatingIncomeLoss", value="100",
                ),
                fact(
                    concept="us-gaap:DepreciationAndAmortization",
                    value="10",
                ),
            ],
            revenue="1000",
        )
        self.assertEqual("WITHHELD", result["publication"])

    def test_external_decimal_context_does_not_change_result(self) -> None:
        """Keep arithmetic at local precision 28 and HALF_EVEN."""
        original = decimal.getcontext().copy()
        try:
            decimal.getcontext().prec = 3
            decimal.getcontext().rounding = decimal.ROUND_DOWN
            facts = [
                fact(concept="us-gaap:OperatingIncomeLoss", value="1"),
                fact(
                    concept="us-gaap:DepreciationDepletionAndAmortization",
                    value="2",
                ),
            ]
            result, _trace, _observations = calculate_b03(
                facts=facts, revenue="7",
            )
            self.assertEqual(
                "0.4285714285714285714285714286", result["value"],
            )
        finally:
            decimal.setcontext(original)

    def test_decimal_object_cannot_bypass_input_digit_limit(self) -> None:
        """Apply the same bound to Decimal objects and fixed-point text."""
        oversized = fact(
            concept="us-gaap:OperatingIncomeLoss", value="100",
        )
        oversized["value"] = decimal.Decimal("9" * 129)
        with self.assertRaisesRegex(ValueError, "Decimal policy"):
            calculate_b03(
                facts=[
                    oversized,
                    fact(
                        concept=(
                            "us-gaap:DepreciationDepletionAndAmortization"
                        ),
                        value="20",
                    ),
                ],
                revenue="1000",
            )


if __name__ == "__main__":
    unittest.main()
