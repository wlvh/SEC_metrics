"""Real successor date conflict is a negative input, not an annual-length success."""
import copy
import json
import unittest
from contextlib import ExitStack
from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.ordinary_income_input import prepare_current_income_input, native_income_reports, inspect_income_amendment, POLICY_PATH, IncomeInputError
from vnext.normal_governance_input import prepare_saved_original_financial_sources
from vnext.annual_amendment_scope import prepare_saved_amendment_scopes, inspect_annual_amendment_scope
from vnext.sources import source_reference_record
from vnext.canonical import sha256_bytes
from vnext.deterministic_router import shared_xbrl_parses

class OrdinaryIncomeInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack=ExitStack(); cls.stack.enter_context(shared_xbrl_parses())
        cls.addClassCleanup(cls.stack.close)
        cls.company='paramount_skydance_paramount_global'
        with original_sources_only():
            cls.sources=prepare_saved_original_financial_sources(repo_root=ROOT,company_id=cls.company)
            cls.annual=cls.sources['input_binding']['prepared_annual_input']
            cls.amendments=prepare_saved_amendment_scopes(repo_root=ROOT,company_id=cls.company)
            try: prepare_current_income_input(repo_root=ROOT,company_id=cls.company)
            except IncomeInputError as error: cls.failure=error
            else: raise AssertionError('Known visible/native date conflict must not be admitted')

    def test_original_conflict_keeps_both_dates_and_source_locator(self):
        self.assertTrue(str(self.failure).startswith('ORDINARY_INCOME_VISIBLE_PERIOD_CONFLICT:'))
        e=self.failure.details
        self.assertEqual(['2025-08-08','2025-12-31'],e['native_period'])
        self.assertIn(['2025-08-07','2025-12-31'],e['visible_periods'])
        self.assertEqual('CONFLICT',e['status'])
        self.assertTrue(e['headers'] and e['source_reference']['raw_asset_id'])
        self.assertEqual('2025-01-01',self.annual['table_input']['target_period']['period_start'])

    def test_primary_visible_period_is_not_replaced_by_xml_agreement(self):
        reports={kind:native_income_reports(self.sources[kind],self.annual,
            ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
            check_visible_short_period=kind=='primary') for kind in ['primary','xml']}
        selected={kind:[r for r in rows if r['period_start']=='2025-08-08'] for kind,rows in reports.items()}
        self.assertTrue(all(selected.values()))
        self.assertEqual('CONFLICT',selected['primary'][0]['visible_period_check']['status'])
        self.assertEqual(selected['primary'][0]['value'],selected['xml'][0]['value'])

    def test_wrong_registrant_cannot_use_the_same_original(self):
        annual=copy.deepcopy(self.annual); annual['entity']='813828'
        with self.assertRaises(ValueError):
            native_income_reports(self.sources['primary'],annual,
                ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'])

    def test_income_correction_in_part_iii_cannot_use_the_balance_only_proof(self):
        packet=self.amendments;scope=packet['scopes'][0]
        args={}
        for role in ['original','amendment']:
            ref=scope[role]['document']['source_reference']
            blob=next(r for r in packet['source_records'] if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==ref['raw_asset_id'])
            args[role]={'raw':(ROOT/blob['storage_uri']).read_bytes(),'blob':blob,'reference':ref,'filing':scope[role]['filing']}
        original=args['amendment'];raw=original['raw'].replace(b'</body>',
            b'<p>The Company corrected revenue in the original annual filing to $1 million.</p></body>',1)
        self.assertNotEqual(raw,original['raw'])
        blob={**original['blob'],'raw_asset_id':'sha256:'+sha256_bytes(content=raw),'byte_length':len(raw)}
        ref=original['reference']
        changed=source_reference_record(raw_blob=blob,**{k:ref[k] for k in
            ['company_id','source_url','accession','document_name','source_role','request_attempt_id']})
        args['amendment']={**original,'raw':raw,'blob':blob,'reference':changed}
        scope=inspect_annual_amendment_scope(**args,company_id=self.company,cik=self.annual['entity'])
        rules=json.loads((ROOT/POLICY_PATH).read_text())
        with self.assertRaisesRegex(ValueError,'AMENDMENT_INCOME_CORRECTION_UNRESOLVED'):
            inspect_income_amendment(scope,raw,rules)

    def test_unbound_original_change_is_rejected(self):
        source=copy.deepcopy(self.sources['primary']);source['raw_bytes']+=b' '
        with self.assertRaisesRegex(ValueError,'ORIGINAL_BINDING_CHANGED'):
            native_income_reports(source,self.annual,['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'])

if __name__=='__main__':unittest.main()
