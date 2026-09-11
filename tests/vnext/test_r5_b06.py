"""Short deterministic B06 primary source and acceptance boundary tests."""
from pathlib import Path
import json,unittest
from decimal import Decimal
from vnext import r5_b06_structured as route
from vnext.specs import compile_spec_file
from vnext.sources import source_reference_record, companyfacts_structured_facts
from vnext.canonical import sha256_bytes
from vnext.observations import scope_key
from vnext import r5_b06_publication as release
from vnext import publication
ROOT=Path(__file__).resolve().parents[2]

class B06PrimaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=compile_spec_file(path=ROOT/route.SPEC_PATH,dependency_specs={})
    def build(self, values, equity=100, *, unit='USD', accession='0000000001-25-000001'):
        vals={**values,'StockholdersEquity':equity};payload={'cik':1,'facts':{'us-gaap':{name:{'units':{unit:[{'val':value,'end':'2024-12-31','accn':accession,'form':'10-K','fp':'FY','fy':2024,'filed':'2025-02-01'}]}} for name,value in vals.items()}}}
        raw=json.dumps(payload).encode();blob={'record_type':'RAW_BLOB','raw_asset_id':'sha256:'+sha256_bytes(content=raw),'byte_length':len(raw),'media_type':'application/json','storage_uri':'evidence/source.json'}
        source=source_reference_record(raw_blob=blob,company_id='test_company',source_url='https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json',accession=accession,document_name='CIK0000000001.json',source_role='companyfacts',request_attempt_id='request:test')
        facts=companyfacts_structured_facts(raw_bytes=raw,source_reference=source,approved_concepts=route.concepts(self.spec),allowed_ciks=['1'],include_instant=True)
        scope={'entity_scope':'consolidated'};target={'company_id':'test_company','period_start':'2024-12-31','period_end':'2024-12-31','accession':accession,'entity':'1','scope':scope,'scope_key':scope_key(scope=scope)}
        return raw,source,facts,target
    def run_case(self,values,equity=100,**kwargs):
        raw,source,facts,target=self.build(values,equity,**kwargs)
        return route.resolve_primary(spec=self.spec,target=target,traits=['non_financial'],facts=facts)
    def test_direct_total_never_adds_current_noncurrent_or_short(self):
        r,t,o,a=self.run_case({'DebtAndCapitalLeaseObligations':70,'LongTermDebtCurrent':10,'LongTermDebtNoncurrent':60,'ShortTermBorrowings':5})
        self.assertEqual(Decimal('0.7'),Decimal(r['value']));self.assertEqual('DIRECT_TOTAL_NO_ADDERS',a['branch']);self.assertEqual(2,len(o))
    def test_same_family_pair_and_cross_family_rejection(self):
        r,_,_,a=self.run_case({'LongTermDebtCurrent':20,'LongTermDebtNoncurrent':30});self.assertEqual('0.5',r['value'])
        r,_,_,a=self.run_case({'LongTermDebtCurrent':20,'LongTermDebtAndCapitalLeaseObligationsNoncurrent':30});self.assertEqual('WITHHELD',r['publication']);self.assertIn('NO_COMPLETE_DEBT_BRANCH',a['reasons'])
    def test_lease_only_and_noncurrent_standalone_are_not_totals(self):
        for values in [{'FinanceLeaseLiabilityCurrent':3,'FinanceLeaseLiabilityNoncurrent':4},{'LongTermDebtAndCapitalLeaseObligations':70},
                       {'DebtSecurities':70,'DebtInstrumentFairValue':70,'RepaymentsOfLongTermDebt':70}]:
            r,_,_,a=self.run_case(values);self.assertIsNone(r['value']);self.assertEqual('STRUCTURED_SOURCE_AMBIGUOUS',r['reason_code']);self.assertFalse(a['fallback_executed'])
    def test_conflicting_totals_short_and_separate_lease_coverage(self):
        for values,reason in [({'DebtAndCapitalLeaseObligations':70,'LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities':75},'DIRECT_TOTAL_CONFLICT'),({'LongTermDebtCurrent':20,'LongTermDebtNoncurrent':30,'CommercialPaper':5},'SHORT_DEBT_COVERAGE_REQUIRES_REVIEW'),({'LongTermDebtCurrent':20,'LongTermDebtNoncurrent':30,'FinanceLeaseLiabilityCurrent':5},'SEPARATE_LEASE_COVERAGE_REQUIRES_REVIEW')]:
            r,_,_,a=self.run_case(values);self.assertIsNone(r['value']);self.assertIn(reason,a['reasons'])
    def test_zero_and_negative_equity_keep_inputs_without_ratio(self):
        for equity in [0,-10]:
            r,t,o,a=self.run_case({'DebtAndCapitalLeaseObligations':70},equity);self.assertIsNone(r['value']);self.assertEqual('NOT_MEANINGFUL',r['quality']);self.assertEqual('DENOMINATOR_NONPOSITIVE',r['reason_code']);self.assertEqual(2,len(o));self.assertTrue(a['nonpositive_equity'])
    def test_wrong_unit_period_entity_and_raw_source_do_not_pass(self):
        r,_,_,a=self.run_case({'DebtAndCapitalLeaseObligations':70},unit='EUR');self.assertEqual('WITHHELD',r['publication'])
        raw,source,facts,target=self.build({'DebtAndCapitalLeaseObligations':70})
        for field,value in [('entity','2'),('accession','0000000002-25-000001'),('period_end','2023-12-31')]:
            changed={**target,field:value}
            if field=='period_end':changed['period_start']=value
            r,_,_,_=route.resolve_primary(spec=self.spec,target=changed,traits=[],facts=facts);self.assertIsNone(r['value'])
        with self.assertRaisesRegex(ValueError,'bytes differ'):
            companyfacts_structured_facts(raw_bytes=raw+b' ',source_reference=source,approved_concepts=route.concepts(self.spec),allowed_ciks=['1'],include_instant=True)
    def test_scope_evidence_blocks_even_a_complete_total(self):
        raw,source,facts,target=self.build({'DebtAndCapitalLeaseObligations':70})
        r,_,_,a=route.resolve_primary(spec=self.spec,target=target,traits=[],facts=facts,scope_reasons=['INDUSTRIAL_VS_FINANCE_SCOPE_REQUIRES_REVIEW']);self.assertEqual('WITHHELD',r['publication']);self.assertIn('INDUSTRIAL_VS_FINANCE_SCOPE_REQUIRES_REVIEW',a['reasons'])
    def test_draft_cannot_issue_any_production_write_permission(self):
        for fn in [release.commit_authority,release.guard_switch,release.guard_recovery,release.guard_mirror_repair]:
            with self.assertRaisesRegex(publication.PublicationError,'NOT_AUTHORIZED'):fn()
    def test_cli_output_path_cannot_traverse_back_into_checkout(self):
        from tools.vnext_r5_b06 import checked_output
        disguised=ROOT.parent/'..'/ROOT.parent.name/ROOT.name/'outputs'/'new-r5-test.json'
        with self.assertRaisesRegex(ValueError,'canonical'):checked_output(disguised)
        with self.assertRaisesRegex(ValueError,'outside'):checked_output(ROOT/'outputs'/'new-r5-test.json')

if __name__=='__main__':unittest.main()
