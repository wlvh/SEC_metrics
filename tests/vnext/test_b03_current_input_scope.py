"""Finite D&A scope boundaries and actual current source-only result delivery."""
from decimal import Decimal
from pathlib import Path
import shutil
import json
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.ordinary_b03_input_scope import inspect_depreciation_input
from vnext.ordinary_saved_result import create_saved_result, read_saved_result
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.deterministic_router import shared_xbrl_parses
from vnext.annual_amendment_scope import prepare_saved_amendment_scopes
from vnext.instant_balance_amendment import prepare_instant_balance_amendment_input

PERIOD={'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}


def original(facts):
    # Small labelled synthetic input; not a registered company or source claim.
    prefix='''<html xmlns:gaap="http://fasb.org/us-gaap/2025" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:currency="http://www.xbrl.org/2003/iso4217"><body>'''
    parts=[]
    for index,item in enumerate(facts):
        concept,value,decimals,*extra=item;overrides=extra[0] if extra else {}
        entity=overrides.get('entity','195');start=overrides.get('start','2025-01-01');end=overrides.get('end','2025-12-31')
        currency=overrides.get('unit','USD');scheme=overrides.get('scheme','http://www.sec.gov/CIK')
        segment=''
        if overrides.get('dimension'):
            segment='<xbrli:segment><xbrldi:explicitMember dimension="gaap:SegmentsAxis">gaap:OtherSegmentMember</xbrldi:explicitMember></xbrli:segment>'
        parts.append(f'''<xbrli:context id="c{index}"><xbrli:entity><xbrli:identifier scheme="{scheme}">{entity}</xbrli:identifier>{segment}</xbrli:entity><xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="u{index}"><xbrli:measure>currency:{currency}</xbrli:measure></xbrli:unit><ix:nonFraction name="gaap:{concept}" contextRef="c{index}" unitRef="u{index}" decimals="{decimals}">{value}</ix:nonFraction>''')
    return (prefix+''.join(parts)+'</body></html>').encode()


def observation(concept,value):
    return {'semantic_role':'depreciation_and_amortization','value':value,
            'source_binding':{'concept':'us-gaap:'+concept}}


class CurrentDaScopeTest(unittest.TestCase):
    def check(self,rows,value='1200000000'):
        return inspect_depreciation_input(raw_bytes=original(rows),entity='195',period=PERIOD,
            observations=[observation('DepreciationDepletionAndAmortization',value)])

    def test_conflicting_subtotal_is_withheld_and_larger_total_not_automatically_taken(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1200000000','-8'),
                           ('DepreciationAndAmortization','3631000000','-6')])
        self.assertEqual(answer['status'],'WITHHOLD')
        self.assertEqual(answer['reason_code'],'B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN')
        self.assertFalse(answer['complete_business_scope_proven'])

    def test_reported_precision_agreement_keeps_chain_not_exact_numeric_equality(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1200000000','-8'),
                           ('DepreciationAndAmortization','1234000000','-6')])
        self.assertEqual(answer['status'],'KEEP')
        self.assertEqual(answer['chain_input']['value'],'1200000000')

    def test_only_unique_original_composition_can_retake_a_later_direct_candidate(self):
        answer=self.check([('DepreciationDepletionAndAmortization','10','INF'),
            ('DepreciationAndAmortization','20','INF'),('Depreciation','7','INF'),
            ('AmortizationOfIntangibleAssets','13','INF')],value='10')
        self.assertEqual(answer['status'],'RETAKE');self.assertEqual(answer['concept'],'DepreciationAndAmortization')

    def test_foreign_entity_period_unit_segment_or_namespace_does_not_create_own_total_conflict(self):
        good=('DepreciationDepletionAndAmortization','1200000000','INF')
        for changes in ({'entity':'196'},{'start':'2024-01-01'},{'unit':'GBP'},{'dimension':True}):
            with self.subTest(changes=changes):
                answer=self.check([good,('DepreciationAndAmortization','3631000000','INF',changes)])
                self.assertEqual(answer['status'],'KEEP')
                self.assertEqual(len(answer['source_facts']),1)
        raw=original([good,('DepreciationAndAmortization','3631000000','INF')])
        raw=raw.replace(b'name="gaap:DepreciationAndAmortization"',b'name="foreign:DepreciationAndAmortization"')
        answer=inspect_depreciation_input(raw_bytes=raw,entity='195',period=PERIOD,
            observations=[observation(good[0],good[1])])
        self.assertEqual(answer['status'],'KEEP')

    def test_currency_alias_is_resolved_and_foreign_identifier_scheme_is_not_accepted(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1200000000','INF')])
        self.assertEqual(answer['status'],'KEEP')
        self.assertTrue(answer['source_facts'][0]['context_proof'])
        with self.assertRaises(ValueError):
            self.check([('DepreciationDepletionAndAmortization','1200000000','INF',{'scheme':'https://example.invalid/company'})])


class CurrentB03SourceOnlyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.sources={};cls.saved={}
        with shared_xbrl_parses():
            for company in ('marriott_international','salesforce'):
                source=cls.root/company;source.mkdir();cls.sources[company]=source
                prepared=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id=company)
                paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
                for proof in prepared['source_proofs']:
                    paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
                for relative in paths:
                    target=source/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(REPO_ROOT/relative,target)
                cls.saved[company]=create_saved_result(source_root=source,output_root=cls.root/(company+'-result'),
                    company_id=company,metric_id='B03')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_marriott_composition_458m_and_135m_revenue_deduction_excluded(self):
        saved=self.saved['marriott_international'];records=[json.loads(s) for s in (self.root/'marriott_international-result/records.jsonl').read_text().splitlines()]
        roles={r['semantic_role']:r for r in records if r['record_type']=='VERIFIED_OBSERVATION' and r['metric_id']=='B03'}
        self.assertEqual(Decimal(roles['depreciation']['value'])+Decimal(roles['amortization']['value']),Decimal('458000000'))
        self.assertEqual(saved['result']['value'],'0.1756281982738868097456656229')
        self.assertEqual(saved['manifest']['target_period']['fiscal_year'],2025)
        self.assertFalse((self.sources['marriott_international']/'catalog').exists())
        self.assertEqual(saved['result']['unit'],'ratio')
        scope=saved['input_assessments']['depreciation_scope']
        self.assertEqual(scope['status'],'KEEP')
        exclusion=scope['existing_scope_check']
        self.assertFalse(exclusion['blocked'])
        self.assertTrue(any(Decimal(row['value_usd'])==Decimal('135000000') and row['dimensions']=={'srt:ProductOrServiceAxis':'mar:FeeServiceMember'} for row in exclusion['excluded_facts']))
        self.assertFalse(exclusion['amount_added_or_result_recomputed'])

    def test_salesforce_named_withheld_does_not_consume_bad_subtotal_and_carries_b01(self):
        saved=self.saved['salesforce'];self.assertIsNone(saved['result']['value'])
        self.assertEqual(saved['result']['publication'],'WITHHELD')
        self.assertEqual(saved['result']['reason_code'],'B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN')
        self.assertEqual(saved['manifest']['target_period']['fiscal_year'],2026)
        records=[json.loads(s) for s in (self.root/'salesforce-result/records.jsonl').read_text().splitlines()]
        revenues=[r for r in records if r['record_type']=='METRIC_RESULT' and r['metric_id']=='B01']
        self.assertEqual(len(revenues),1);self.assertEqual(revenues[0]['value'],'41525000000')
        reread=read_saved_result(output_root=self.root/'salesforce-result')
        self.assertEqual(reread['result']['result_id'],saved['result']['result_id'])
        scope=reread['input_assessments']['depreciation_scope']
        self.assertEqual(scope['status'],'WITHHOLD')
        self.assertEqual({r['value'] for r in scope['source_facts']},{'1200000000','3631000000'})

    def test_amendment_input_uses_program_policy_without_sources_containing_it(self):
        source=self.sources['marriott_international']
        packet=prepare_saved_amendment_scopes(repo_root=source,company_id='marriott_international',rules_root=REPO_ROOT)
        self.assertEqual(packet['scopes'],[])
        instant=prepare_instant_balance_amendment_input(repo_root=source,company_id='marriott_international',rules_root=REPO_ROOT)
        self.assertEqual(instant['decision'],'INPUT_PROPERTY_PROVEN')
        self.assertFalse((source/'config/annual_amendment_scope_v1.json').exists())

    def test_saved_input_assessment_is_read_without_recalculation_and_damage_is_visible(self):
        path=self.root/'marriott_international-result/input-assessments.json'
        original=path.read_bytes();path.write_bytes(original+b' ')
        try:
            with self.assertRaisesRegex(ValueError,'SAVED_RESULT_FILE_CHANGED:input-assessments.json'):
                read_saved_result(output_root=path.parent)
        finally:path.write_bytes(original)


if __name__=='__main__':unittest.main()
