"""Finite certificates/pension forms exercised through the actual disclosure verifier."""
import copy
import re
import unittest

from tests.vnext.test_b06_disclosure_v2 import original, verify
from vnext.deterministic_router import parse_accession_xbrl_source


class FallbackSourceFormsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original('southwest_airlines')
        cls.baseline = verify(cls.original)

    def certificate(self, label='Pass Through Certificates'):
        args = copy.deepcopy(self.original)
        self.assertIn(b'5.25% Notes', args['raw'])
        args['raw'] = args['raw'].replace(b'5.25% Notes', b'5.25% '+label.encode())
        args['primary'] = args['primary'].replace(b'5.25% Notes', b'5.25% '+label.encode())
        # Preserve the actual rate fact inside the table label. Its numeric
        # inline element separates 5.25 from the following % Notes text.
        self.assertIn(b'5.25</ix:nonFraction>% Notes', args['primary'])
        args['primary'] = args['primary'].replace(b'5.25</ix:nonFraction>% Notes',
            b'5.25</ix:nonFraction>% '+label.encode())
        return args

    def pension_fact(self, prefix='us-gaap'):
        args = copy.deepcopy(self.original)
        parsed = parse_accession_xbrl_source(raw_bytes=args['raw'])
        equity = next(f for f in parsed.facts if f['qualified_name']=='us-gaap:stockholdersequity'
            and parsed.contexts[f['context_ref']]['period_start']==parsed.contexts[f['context_ref']]['period_end']
            ==args['target']['period_end'])
        name = prefix+':DefinedBenefitPlanBenefitObligation'
        addition = ('<'+name+' contextRef="'+equity['context_ref']+'" unitRef="'+equity['unit_ref']
                    +'" decimals="-6">241000000</'+name+'>').encode()
        args['raw'], count = re.subn(rb'(</(?:[A-Za-z0-9_-]+:)?xbrl>\s*)$',
            lambda m: addition+m[1], args['raw'])
        self.assertEqual(1, count)
        return args

    def inventory(self, proof):
        return proof['disclosure_inventory']

    def test_reported_certificates_reconcile_inside_the_same_debt_total(self):
        proof = verify(self.certificate())
        self.assertEqual(self.baseline['carrying_amount'], proof['carrying_amount'])
        row = next(r for r in self.inventory(proof) if r.get('label')=='5.25% Pass Through Certificates')
        self.assertEqual('INCLUDED_IN_SELECTED_SET', row['disposition'])
        self.assertTrue(proof['successor_content_checks']['primary_xml_numeric_agreement'])

    def test_negated_certificates_are_not_debt_members(self):
        for label in ('Certificates not included in debt', 'Excluded certificates'):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, 'DEBT_MEMBERSHIP_NEGATED|FINANCE_LEASE_RELATIONSHIP_CONFLICT'):
                    verify(self.certificate(label))

    def test_standard_pension_obligation_keeps_its_different_business_nature(self):
        proof = verify(self.pension_fact())
        self.assertEqual(self.baseline['carrying_amount'], proof['carrying_amount'])
        row = next(r for r in self.inventory(proof) if r.get('concept')=='us-gaap:definedbenefitplanbenefitobligation')
        self.assertEqual('EXCLUDED_STANDARD_DIFFERENT_MEASUREMENT_OR_NATURE', row['disposition'])

    def test_custom_pension_name_cannot_borrow_the_standard_exclusion(self):
        with self.assertRaisesRegex(ValueError, 'UNRESOLVED_FINANCING_ITEM'):
            verify(self.pension_fact('luv'))
