"""Current stub-period observations stay separate from predecessor financials."""
import copy
import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.ordinary_income_input import (prepare_current_income_input,verify_income_observations,
    native_income_reports,inspect_income_amendment,POLICY_PATH)
from vnext.normal_candidates import _prepare_b06
from vnext.normal_zero_ai_results import resolve_ordinary_zero_ai_metric
from vnext.observations import structured_observation
from vnext.canonical import content_hash
from vnext.canonical import sha256_bytes
from vnext.sources import source_reference_record
from vnext.annual_amendment_scope import inspect_annual_amendment_scope


class OrdinaryIncomeInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.company='paramount_skydance_paramount_global'
        with original_sources_only():
            cls.packet=prepare_current_income_input(repo_root=ROOT,company_id=cls.company)
            cls.results={m:resolve_ordinary_zero_ai_metric(repo_root=ROOT,company_id=cls.company,metric_id=m) for m in ['B01','B03']}
            cls.sources=_prepare_b06(repo_root=ROOT,company_id=cls.company)

    def observation(self,old,**changes):
        args={k:old[k] for k in ['metric_id','semantic_role','company_id','period_start','period_end','scope','value','unit','quality','source_binding']}
        args.update(changes);return structured_observation(**args)

    def test_original_period_and_existing_calculator_guard_are_preserved(self):
        p=self.packet
        self.assertEqual(p['statement_period'],{'fiscal_year':2025,'period_start':'2025-08-08','period_end':'2025-12-31'})
        self.assertEqual(p['income_input_id'],content_hash(value={k:v for k,v in p.items() if k!='income_input_id'}))
        self.assertEqual(len(p['amendment_checks']),1)
        for m,x in self.results.items():
            r=x['result']
            self.assertEqual((r['quality'],r['reason_code'],r['value']),('NOT_MEANINGFUL','ANNUAL_DURATION_OUT_OF_RANGE',None))
            self.assertTrue(x['input_binding']['income_observation_checks'])
            self.assertEqual(x['calls'],{'provider':0,'paid':0,'sec':0})
            self.assertEqual(r['period_start'],'2025-08-08')
            self.assertTrue(all(o['source_binding']['duration_days']==146 for o in x['observations']))
        self.assertEqual(self.results['B01']['observations'][0]['value'],'12269000000')

    def test_structurally_valid_different_amount_cannot_replace_the_original(self):
        old=self.results['B01']['observations'][0]
        changed=self.observation(old,value='12270000000')
        with self.assertRaisesRegex(ValueError,'SELECTED_COMPANYFACTS_AMOUNT_DIFFERS'):
            verify_income_observations(self.packet,[changed])

    def test_predecessor_period_is_not_the_current_statement_period(self):
        old=self.results['B01']['observations'][0]
        changed=self.observation(old,period_start='2025-01-01',period_end='2025-08-06',value='16622000000')
        with self.assertRaisesRegex(ValueError,'SELECTED_OBSERVATION_SCOPE_CHANGED'):
            verify_income_observations(self.packet,[changed])

    def test_income_correction_in_part_iii_cannot_use_the_balance_only_proof(self):
        packet=self.packet['amendment_input'];scope=packet['scopes'][0]
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
        scope=inspect_annual_amendment_scope(**args,company_id=self.company,cik=self.packet['annual_input']['entity'])
        rules=json.loads((ROOT/POLICY_PATH).read_text())
        with self.assertRaisesRegex(ValueError,'AMENDMENT_INCOME_CORRECTION_UNRESOLVED'):
            inspect_income_amendment(scope,raw,rules)

    def test_unbound_original_change_is_rejected(self):
        source=copy.deepcopy(self.sources['primary']);source['raw_bytes']+=b' '
        with self.assertRaisesRegex(ValueError,'ORIGINAL_BINDING_CHANGED'):
            native_income_reports(source,self.packet['annual_input'],['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'])


if __name__=='__main__':unittest.main()
