"""Actual bank/industrial originals retain scoped balances and specific gaps."""
import copy
import hashlib
import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_candidates import _prepare_b06
from vnext.ordinary_special_debt_scope import inspect_special_scope, POLICY_PATH
from vnext.sources import source_reference_record


class SpecialDebtScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((ROOT / POLICY_PATH).read_text())
        with original_sources_only():
            cls.sources = {co: _prepare_b06(repo_root=ROOT, company_id=co)
                for co in ['jpmorgan_chase', 'ford_motor_company']}

    def arguments(self, company):
        p = self.sources[company]
        return copy.deepcopy({'primary': p['primary'], 'xml': p['xml'],
            'annual': p['input_binding']['prepared_annual_input'],
            'financial_institution': company == 'jpmorgan_chase', 'rules': self.rules})

    def inspect(self, args):
        with original_sources_only():
            return inspect_special_scope(**args)

    def change(self, args, kind, transform):
        source = args[kind]; raw = transform(source['raw_bytes'])
        self.assertNotEqual(raw, source['raw_bytes'])
        blob = {**source['raw_blob'], 'raw_asset_id': 'sha256:' + hashlib.sha256(raw).hexdigest(),
                'byte_length': len(raw)}
        old = source['source_reference']
        ref = source_reference_record(raw_blob=blob, company_id=old['company_id'], source_url=old['source_url'],
            accession=old['accession'], document_name=old['document_name'], source_role=old['source_role'],
            request_attempt_id=old['request_attempt_id'])
        args[kind] = {**source, 'raw_bytes': raw, 'raw_blob': blob, 'source_reference': ref}

    def test_actual_scope_reconstruction_does_not_turn_subtotals_into_complete_ratios(self):
        for company, subtotal, reason in [
            ('jpmorgan_chase', '970329000000', 'BANK_FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED'),
            ('ford_motor_company', '21919000000', 'INDUSTRIAL_ATTRIBUTABLE_EQUITY_NOT_ESTABLISHED')]:
            with self.subTest(company=company):
                value = self.inspect(self.arguments(company))
                self.assertEqual(value['reported_subtotal'], subtotal)
                self.assertEqual(value['limitations'], [reason])
                self.assertIsNone(value['ratio'])
                self.assertFalse(value['subtotal_is_complete_B06'])
                self.assertFalse(value['missing_concept_proves_absence'])
                for role in value['reported_components'].values():
                    self.assertTrue(role['visible_table_evidence'])
                    self.assertTrue(all(role['source_reports'].values()))
                if company == 'ford_motor_company':
                    self.assertIsNone(value['same_scope_attributable_equity'])
                    self.assertNotIn('35952000000', [r['value'] for r in value['reported_components'].values()])

    def test_both_originals_must_agree_on_the_reported_amount(self):
        args = self.arguments('jpmorgan_chase')
        self.change(args, 'xml', lambda raw: raw.replace(b'>442396000000<', b'>442397000000<'))
        with self.assertRaisesRegex(ValueError, 'PRECISION_CONFLICT'):
            self.inspect(args)

    def test_wrong_official_namespace_cannot_supply_funding_roles(self):
        args = self.arguments('jpmorgan_chase')
        for kind in ['primary', 'xml']:
            self.change(args, kind, lambda raw: raw.replace(b'http://fasb.org/us-gaap/2025', b'urn:false-gaap'))
        with self.assertRaisesRegex(ValueError, 'OFFICIAL_CONCEPT_REQUIRED'):
            self.inspect(args)

    def test_industrial_native_scope_also_requires_its_visible_column(self):
        args = self.arguments('ford_motor_company')
        self.change(args, 'primary', lambda raw: raw.replace(b'Company excluding Ford Credit', b'Company including Ford Credit'))
        with self.assertRaisesRegex(ValueError, 'INDUSTRIAL_COLUMN_LABEL_NOT_PROVEN'):
            self.inspect(args)

    def test_changed_original_without_new_binding_is_rejected(self):
        args = self.arguments('ford_motor_company'); args['primary']['raw_bytes'] += b' '
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_BINDING_CHANGED'):
            self.inspect(args)

    def test_moving_a_valid_fact_to_the_prior_year_column_is_rejected(self):
        args = self.arguments('ford_motor_company')
        def swap(raw):
            pattern = rb'<ix:nonfraction\b(?=[^>]*name="us-gaap:LongTermDebtCurrent")[^>]*>.*?</ix:nonfraction>'
            matches = list(re.finditer(pattern, raw, re.I | re.S))
            self.assertEqual(len(matches), 2)
            first, second = matches
            return (raw[:first.start()] + second.group() + raw[first.end():second.start()]
                    + first.group() + raw[second.end():])
        self.change(args, 'primary', swap)
        with self.assertRaisesRegex(ValueError, 'INDUSTRIAL_COLUMN_LABEL_NOT_PROVEN'):
            self.inspect(args)


if __name__ == '__main__':
    unittest.main()
