"""Small historical consumer examples for the shared original-fact check.

These are constructed inline documents, not saved-company installations.
KEEP means the limited input check passed, not complete B03 acceptance.
"""
from unittest import TestCase

from vnext.historical_zero_ai_results import inspect_selected_historical_depreciation_input
from vnext.normal_zero_ai_results import NormalZeroAiError
from vnext.ordinary_b03_input_scope import inspect_depreciation_input


PERIOD = {"period_start": "2025-01-01", "period_end": "2025-12-31"}


def fact(concept="g:DepreciationAndAmortization", value="100", *,
         context="fy", unit="money", decimals="0"):
    return ('<ix:nonFraction name="' + concept + '" contextRef="' + context
            + '" unitRef="' + unit + '" decimals="' + decimals
            + '" scale="0">' + value + '</ix:nonFraction>')


def document(body, *, namespace="http://fasb.org/us-gaap/2025"):
    contexts = []
    for name, entity, start, end in (
            ("fy", "1", "2025-01-01", "2025-12-31"),
            ("other", "2", "2025-01-01", "2025-12-31"),
            ("prior", "1", "2024-01-01", "2024-12-31")):
        contexts.append('<xbrli:context id="' + name + '"><xbrli:entity>'
            '<xbrli:identifier scheme="http://www.sec.gov/CIK">' + entity
            + '</xbrli:identifier></xbrli:entity><xbrli:period>'
            '<xbrli:startDate>' + start + '</xbrli:startDate><xbrli:endDate>'
            + end + '</xbrli:endDate></xbrli:period></xbrli:context>')
    return ('<html xmlns:g="' + namespace
        + '" xmlns:corp="https://example.invalid/extension/2025"'
        ' xmlns:currency="http://www.xbrl.org/2003/iso4217"'
        ' xmlns:xbrli="http://www.xbrl.org/2003/instance"'
        ' xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>'
        '<ix:header><ix:resources>' + ''.join(contexts)
        + '<xbrli:unit id="money"><xbrli:measure>currency:USD</xbrli:measure>'
        '</xbrli:unit><xbrli:unit id="euros"><xbrli:measure>currency:EUR'
        '</xbrli:measure></xbrli:unit></ix:resources></ix:header>'
        + body + '</body></html>').encode()


def observation(role="depreciation_and_amortization", *,
                concept="us-gaap:DepreciationAndAmortization", value="100"):
    return {"semantic_role": role, "value": value,
            "source_binding": {"concept": concept, "entity": "1"}}


def inspect(raw, observations=None):
    return inspect_selected_historical_depreciation_input(raw_bytes=raw,
        entity="1", period=PERIOD,
        observations=observations if observations is not None else [observation()])


def impairment_document(*, note="Includes depreciation related to an asset impairment.",
                        first="60", marker="g"):
    return document('<table><tr><td>Depreciation and amortization</td><td>'
        + first + '</td><td>(g)</td><td>40</td><td>' + fact()
        + '</td></tr></table><p>(' + marker + ') ' + note + '</p>')


class HistoricalSharedB03InputTest(TestCase):
    def test_wrong_inline_namespace_is_not_a_confirmed_historical_amount(self):
        raw = document('<p>' + fact() + '</p>',
                       namespace="http://fasb.org/us-gaap/2021-01-31")
        raw = raw.replace(b'<ix:nonFraction ',
            b'<wrong:nonFraction xmlns:wrong="https://example.invalid/not-inline" ')
        raw = raw.replace(b'</ix:nonFraction>', b'</wrong:nonFraction>')
        checked = inspect(raw)
        self.assertEqual("WITHHOLD", checked["status"])
        self.assertEqual("SOURCE_NUMERIC_VALUES_UNRESOLVED", checked["why"])
        self.assertTrue(any('NUMERIC_TAG_NOT_SUPPORTED' in row['reason']
                            for row in checked['source_numeric_issues']))

    def test_unformatted_comma_cannot_confirm_a_historical_chain_amount(self):
        checked = inspect(document('<p>' + fact(value="1,00") + '</p>',
            namespace="http://fasb.org/us-gaap/2021-01-31"))
        self.assertEqual("WITHHOLD", checked["status"])
        self.assertTrue(any('NUMERIC_LEXICAL_FORM_NOT_SUPPORTED' in row['reason']
                            for row in checked['source_numeric_issues']))

    def test_declared_decimal_transform_keeps_dated_release_amount(self):
        raw = document('<p>' + fact(value="1,000") + '</p>',
                       namespace="http://fasb.org/us-gaap/2021-01-31")
        raw = raw.replace(b'<html ',
            b'<html xmlns:num="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" ')
        raw = raw.replace(b'<ix:nonFraction ', b'<ix:nonFraction format="num:num-dot-decimal" ')
        checked = inspect(raw, [observation(value="1000")])
        self.assertEqual("KEEP", checked["status"])
        self.assertEqual("1000", checked['source_facts'][0]['value'])
        self.assertFalse(checked['complete_business_scope_proven'])

    def test_custom_same_local_name_cannot_create_a_gaap_conflict(self):
        checked = inspect(document('<p>' + fact() + '</p><p>'
            + fact("corp:DepreciationAndAmortization", "999") + '</p>'))
        self.assertEqual("KEEP", checked["status"])
        self.assertEqual(["100"], [row["value"] for row in checked["source_facts"]])
        self.assertFalse(checked["complete_business_scope_proven"])

    def test_legal_concept_and_currency_prefix_aliases_are_resolved(self):
        checked = inspect(document('<p>' + fact() + '</p>'))
        self.assertEqual("KEEP", checked["status"])
        self.assertEqual("DepreciationAndAmortization", checked["source_facts"][0]["concept"])

    def test_historical_dated_release_is_explicit_and_current_default_is_retained(self):
        raw = document('<p>' + fact() + '</p>',
                       namespace="http://fasb.org/us-gaap/2021-01-31")
        self.assertEqual("KEEP", inspect(raw)["status"])
        current = inspect_depreciation_input(raw_bytes=raw, entity="1",
            period=PERIOD, observations=[observation()])
        self.assertEqual("WITHHOLD", current["status"])
        for uri in ("https://example.invalid/us-gaap/2021-01-31",
                    "http://fasb.org/us-gaap/2021q4",
                    "http://fasb.org/us-gaap/2021-01-31/extra"):
            with self.subTest(uri=uri):
                self.assertEqual("WITHHOLD", inspect(document('<p>' + fact() + '</p>',
                    namespace=uri))["status"])

    def test_dated_composition_uses_same_policy_for_both_original_components(self):
        observations = [observation("depreciation", concept="us-gaap:Depreciation", value="60"),
            observation("amortization", concept="us-gaap:AmortizationOfIntangibleAssets", value="40")]
        raw = document('<p>' + fact("g:Depreciation", "60") + '</p><p>'
            + fact("g:AmortizationOfIntangibleAssets", "40") + '</p>',
            namespace="http://fasb.org/us-gaap/2021-01-31")
        self.assertEqual("KEEP", inspect(raw, observations)["status"])

    def test_another_entity_period_or_currency_cannot_support_the_chain(self):
        for options in ({"context": "other"}, {"context": "prior"}, {"unit": "euros"}):
            with self.subTest(options=options):
                checked = inspect(document('<p>' + fact(**options) + '</p>'))
                self.assertEqual("WITHHOLD", checked["status"])
                self.assertEqual([], checked["source_facts"])

    def test_wrong_scope_facts_cannot_change_a_supported_amount(self):
        raw = document('<p>' + fact() + '</p>' + ''.join('<p>'
            + fact(value="999", **options) + '</p>' for options in
            ({"context": "other"}, {"context": "prior"}, {"unit": "euros"})))
        self.assertEqual("KEEP", inspect(raw)["status"])

    def test_true_same_concept_disagreement_remains_withheld(self):
        checked = inspect(document('<p>' + fact() + '</p><p>'
            + fact(value="999") + '</p>'))
        self.assertEqual("WITHHOLD", checked["status"])
        self.assertTrue(checked["why"].startswith("ONE_CONCEPT_CARRIES_TWO_AMOUNTS:"))

    def test_reported_precision_is_retained(self):
        checked = inspect(document('<p>' + fact(value="100", decimals="-1")
            + '</p><p>' + fact(value="104", decimals="0") + '</p>'))
        self.assertEqual("KEEP", checked["status"])

    def test_composition_requires_both_selected_original_components(self):
        observations = [observation("depreciation", concept="us-gaap:Depreciation", value="60"),
            observation("amortization", concept="us-gaap:AmortizationOfIntangibleAssets", value="40")]
        raw = document('<p>' + fact("g:Depreciation", "60") + '</p><p>'
            + fact("g:AmortizationOfIntangibleAssets", "40") + '</p>')
        checked = inspect(raw, observations)
        self.assertEqual("KEEP", checked["status"])
        self.assertEqual({"depreciation", "amortization"}, set(checked["composition_originals"]))
        missing = document('<p>' + fact("g:Depreciation", "60") + '</p>')
        with self.assertRaisesRegex(NormalZeroAiError,
                "B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NOT_IN_ORIGINAL:amortization") as error:
            inspect(missing, observations)
        self.assertEqual("SOURCE_INTEGRITY_ERROR", error.exception.category)

    def test_changed_chain_amount_remains_withheld(self):
        checked = inspect(document('<p>' + fact() + '</p>'),
            [observation(value="101")])
        self.assertEqual("WITHHOLD", checked["status"])
        self.assertEqual("CHAIN_AMOUNT_DIFFERS_FROM_PRIMARY_AT_REPORTED_PRECISION", checked["why"])

    def test_aliased_fact_cannot_bypass_original_impairment_inclusion(self):
        checked = inspect(impairment_document())
        self.assertEqual("WITHHOLD", checked["status"])
        self.assertEqual("THE_SELECTED_TOTAL_INCLUDES_IMPAIRMENT_RELATED_DEPRECIATION", checked["why"])
        self.assertEqual("g", checked["impairment_inclusion"]["included_component"]["marker"])

    def test_exclusion_or_unlinked_footnote_is_not_an_inclusion_proof(self):
        for options in ({"note": "Excludes depreciation related to an asset impairment."},
                {"marker": "h"}, {"first": "61"}):
            with self.subTest(options=options):
                checked = inspect(impairment_document(**options))
                self.assertEqual("KEEP", checked["status"])
                self.assertNotIn("impairment_inclusion", checked)

    def test_composition_can_request_one_retake_without_guessing_a_total(self):
        raw = document('<p>' + fact("g:DepreciationDepletionAndAmortization", "60")
            + '</p><p>' + fact() + '</p><p>' + fact("g:Depreciation", "60")
            + '</p><p>' + fact("g:AmortizationOfIntangibleAssets", "40") + '</p>')
        checked = inspect(raw, [observation(concept="us-gaap:DepreciationDepletionAndAmortization", value="60")])
        self.assertEqual(("RETAKE", "DepreciationAndAmortization"),
                         (checked["status"], checked["concept"]))
        self.assertEqual("KEEP", inspect(raw)["status"])
