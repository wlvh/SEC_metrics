"""Original disclosure classification stays separate from debt-set approval."""
import copy
import hashlib
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b06_financing_inventory import prepare_saved_financing_inventory,inspect_financing_inventory
from vnext.normal_candidates import _prepare_b06
from vnext.sources import source_reference_record


class FinancingInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.actual = {company:prepare_saved_financing_inventory(repo_root=ROOT,company_id=company)
                for company in ['pfizer','southwest_airlines','marriott_international']}
            cls.sources = {company:_prepare_b06(repo_root=ROOT,company_id=company)
                for company in ['pfizer','southwest_airlines']}

    def arguments(self,company):
        p = self.sources[company]
        return copy.deepcopy({'primary':p['primary'],'xml':p['xml'],
            'prepared':p['input_binding']['prepared_annual_input']})

    def change(self,args,kind,transform):
        source = args[kind]
        raw = transform(source['raw_bytes'])
        self.assertTrue(raw != source['raw_bytes'],'Mutation did not change source bytes')
        blob = {**source['raw_blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old = source['source_reference']
        ref = source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],
            request_attempt_id=old['request_attempt_id'])
        args[kind] = {**source,'raw_bytes':raw,'raw_blob':blob,'source_reference':ref}

    def inspect(self,args):
        with original_sources_only():
            return inspect_financing_inventory(**args)

    def test_actual_disclosures_do_not_infer_zero_or_grant_debt_set_disposition(self):
        for packet in self.actual.values():
            inventory = packet['inventory']
            self.assertFalse(inventory['finance_lease']['absence_established'])
            self.assertFalse(inventory['finance_lease']['zero_inferred'])
            self.assertEqual('NOT_GRANTED_BY_INVENTORY',inventory['supplier']['debt_set_disposition'])
            self.assertEqual('NOT_PROVEN',inventory['debt_completeness'])
            self.assertFalse(inventory['metric_result_created'])
            self.assertFalse(packet['native_run_created'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},packet['calls'])
        pfizer = self.actual['pfizer']['inventory']
        self.assertEqual('NO_SEPARATE_FINANCE_LEASE_DISCLOSURE_FOUND',pfizer['finance_lease']['status'])
        self.assertEqual(['http://fasb.org/us-gaap/2025#AccountsPayableCurrent'],pfizer['supplier']['reported_statement_classes'])
        self.assertEqual('574000000',pfizer['supplier']['chosen_current_balance']['value'])
        self.assertEqual('SEPARATE_NATIVE_FINANCE_LEASE_FACTS_PRESENT',
                         self.actual['marriott_international']['inventory']['finance_lease']['status'])

    def test_supplier_taxonomy_name_does_not_replace_original_deferred_credit_label(self):
        item = self.actual['southwest_airlines']['inventory']['supplier']
        self.assertEqual('24000000',item['chosen_current_balance']['value'])
        self.assertEqual([],item['reported_statement_classes'])
        self.assertEqual(['Deferred supplier credits'],
            [r['source_table_row']['reported_row_label'] for r in item['sources']['primary']['balance_reports']])

    def test_supplier_amount_difference_between_html_and_xml_rejects(self):
        args = self.arguments('southwest_airlines')
        pattern = rb'(<ix:nonFraction\b(?=[^>]*name="us-gaap:SupplierFinanceProgramObligationCurrent")[^>]*>)24(</ix:nonFraction>)'
        self.change(args,'primary',lambda raw:re.sub(pattern,lambda m:m[1]+b'25'+m[2],raw,count=1))
        with self.assertRaisesRegex(ValueError,'SAME_PRECISION_CONFLICT'):
            self.inspect(args)

    def test_statement_class_cannot_differ_between_two_originals(self):
        args = self.arguments('pfizer')
        self.change(args,'primary',lambda raw:raw.replace(b'http://fasb.org/us-gaap/2025#AccountsPayableCurrent',
                                                       b'http://fasb.org/us-gaap/2025#DebtCurrent'))
        with self.assertRaisesRegex(ValueError,'STATEMENT_CLASS_CONFLICT'):
            self.inspect(args)

    def test_supplier_amount_requires_official_concept_and_usd_unit(self):
        for before,after in [(b'http://fasb.org/us-gaap/2025',b'urn:false-gaap'),
                             (b'http://www.xbrl.org/2003/iso4217',b'urn:false-currency')]:
            with self.subTest(before=before):
                args = self.arguments('southwest_airlines')
                for kind in ['primary','xml']:
                    self.change(args,kind,lambda raw:raw.replace(before,after))
                with self.assertRaisesRegex(ValueError,'CONCEPT_OR_UNIT_UNPROVEN'):
                    self.inspect(args)

    def test_original_source_binding_is_required(self):
        args = self.arguments('pfizer');args['primary']['raw_bytes'] += b' '
        with self.assertRaisesRegex(ValueError,'SOURCE_BINDING_CHANGED'):
            self.inspect(args)

    def test_hyphenated_finance_lease_disclosure_is_not_reported_missing(self):
        for text in ['finance-lease','finance‑lease']:
            with self.subTest(text=text):
                args = self.arguments('pfizer')
                paragraph = ('<p>We report '+text+' liabilities in other liabilities.</p>').encode()
                self.change(args,'primary',lambda raw:raw.replace(b'</body>',paragraph+b'</body>',1))
                result = self.inspect(args)
                self.assertEqual('FINANCE_LEASE_TEXT_FOUND_WITHOUT_SEPARATE_NATIVE_FACT',
                                 result['finance_lease']['status'])
                self.assertFalse(result['finance_lease']['zero_inferred'])


if __name__=='__main__':
    unittest.main()
