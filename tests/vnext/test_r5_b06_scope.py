"""Bounded financing-scope, raw materials and nonoverlap regressions."""
from pathlib import Path
import copy,json,unittest
from decimal import Decimal
from functools import lru_cache
from vnext import r5_b06_structured as route
from vnext.r5_b06_scope import scope_inputs,precision_choice,validate_partition
from vnext.specs import compile_spec_file,compile_spec,SpecError
from vnext.batch_workflow import _registry_rows,repository_company_ciks,repository_company_traits
from vnext.sources import raw_blob_record,source_reference_record,companyfacts_structured_facts
from vnext.observations import scope_key
ROOT=Path(__file__).resolve().parents[2]

@lru_cache(maxsize=10)
def material(cid):
    company=next(c for c in _registry_rows(repo_root=ROOT) if c['company_id']==cid);sel=route.discover(data_root=ROOT,company=company);spec=compile_spec_file(path=ROOT/route.SPEC_PATH,dependency_specs={});scope={'entity_scope':'consolidated'};target={'company_id':cid,'period_start':sel['target_period']['period_start'],'period_end':sel['target_period']['period_end'],'accession':sel['filing']['accessionNumber'],'entity':sel['entity'],'scope':scope,'scope_key':scope_key(scope=scope)};facts=[];measurement=None;xmlargs=None
    for proof in sel['sources']:
        cf='/companyfacts/' in proof['source_url'];xml=proof['document_name'].endswith('_htm.xml')
        if not (cf or xml):continue
        raw=(ROOT/proof['request_repo_relative_path']).read_bytes();blob=raw_blob_record(repo_root=ROOT,repo_relative_path=proof['request_repo_relative_path'],media_type='application/json' if cf else 'application/xml');source=source_reference_record(raw_blob=blob,company_id=cid,source_url=proof['source_url'],accession=proof['accession'],document_name=proof['document_name'],source_role='companyfacts' if cf else 'accession_xbrl',request_attempt_id=proof['request_attempt_id'])
        if cf:facts=companyfacts_structured_facts(raw_bytes=raw,source_reference=source,approved_concepts=route.concepts(spec),allowed_ciks=repository_company_ciks(repo_root=ROOT,company_id=cid),include_instant=True)
        else:
            xmlargs=dict(raw=raw,source=source,spec=spec,target=target,filed=sel['filing']['filingDate'],data_root=ROOT);measurement=scope_inputs(**xmlargs)
    return dict(spec=spec,target=target,traits=repository_company_traits(repo_root=ROOT,company_id=cid),facts=facts,measurement=measurement),xmlargs

class B06ScopeTest(unittest.TestCase):
    def resolve(self,cid):return route.resolve_primary(**material(cid)[0])
    def test_complete_new_disjoint_lease_ratios_and_native_components(self):
        for cid,amount,equity in [('salesforce','14974000000','59142000000'),('macys','2445000000','4860000000')]:
            r,t,o,a=self.resolve(cid);self.assertEqual(str(Decimal(amount)/Decimal(equity)),r['value']);self.assertEqual(amount,a['debt']);self.assertFalse(a['reasons']);self.assertTrue(all('xbrl_fact_ordinal' in x['source_binding'] for x in o))
        _,_,o,_=self.resolve('macys');self.assertEqual({'principal','premium','cost','finance_lease','equity'},{x['semantic_role'] for x in o})
    def test_pfizer_current_subtotal_precision_but_no_false_completeness(self):
        args,_=material('pfizer');m=args['measurement'];self.assertEqual('64795000000',m['carrying_amount']);self.assertEqual('0.7492830380683657893519589250',str(Decimal(m['carrying_amount'])/Decimal(m['equity_fact']['value'])))
        precise=next(p for p in m['precision'] if p['concept']=='us-gaap:LongTermDebtNoncurrent');self.assertEqual({'61641000000','62000000000'},{c['value'] for c in precise['all_reports']});r,t,o,a=self.resolve('pfizer');self.assertEqual('WITHHELD',r['publication']);self.assertIn('FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED',a['reasons'])
    def test_original_five_apply_new_set_without_duplicate_lease_or_short(self):
        for cid,debt,quality in [('marriott_international','16204000000','NOT_MEANINGFUL'),('southwest_airlines','4901000000','EXACT'),('lumen_technologies','17441000000','NOT_MEANINGFUL'),('paramount_skydance_paramount_global','13658000000','EXACT'),('enphase_energy','1204377000','EXACT')]:
            r,t,o,a=self.resolve(cid);self.assertEqual(debt,a['debt']);self.assertEqual(quality,r['quality']);self.assertFalse(a['reasons'])
    def test_bank_and_industrial_evidence_gaps_are_not_na_or_zero(self):
        for cid in ['jpmorgan_chase','ford_motor_company']:
            r,t,o,a=self.resolve(cid);self.assertEqual('APPLICABLE',r['applicability']);self.assertEqual('WITHHELD',r['publication']);self.assertIsNone(r['value']);self.assertIsNone(a['debt']);self.assertTrue(a['reasons'])
    def test_incomplete_flag_blocks_even_without_manual_reason(self):
        args=copy.deepcopy(material('pfizer')[0]);args['measurement']['unresolved']=[];r,t,o,a=route.resolve_primary(**args);self.assertEqual('WITHHELD',r['publication']);self.assertIn('DEBT_SET_COMPLETENESS_UNPROVEN',a['reasons'])
    def test_overlap_omitted_current_and_duplicate_fact_roles_rejected(self):
        m=copy.deepcopy(material('salesforce')[0]['measurement']['model']);req=['current_borrowings','noncurrent_borrowings','finance_leases']
        for kind in ['overlap','missing_current','same_fact','repeated_formula']:
            x=copy.deepcopy(m)
            if kind=='overlap':x['groups'][1]['coverage'].append('current_borrowings')
            elif kind=='missing_current':x['groups'][0]['coverage'].remove('current_borrowings')
            elif kind=='same_fact':x['inputs']['finance_lease']=x['inputs']['borrowing']
            else:x['groups'][0]['expression']={'op':'add','args':['borrowing','borrowing']};x['expression']={'op':'add','args':[x['groups'][0]['expression'],'finance_lease']}
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate_partition(x,req)
    def test_precision_equal_precision_conflicts_and_unrelated_coarse_value(self):
        def c(v,d,o):return {'value':v,'decimals':d,'ordinal':o}
        self.assertEqual('61641000000',precision_choice([c('62000000000','-9',1),c('61641000000','-6',2)])['value'])
        for cases in [[c('61','0',1),c('62','0',2)],[c('61641000000','-6',1),c('63000000000','-9',2)],[c('1',None,1)]]:
            with self.assertRaises(ValueError):precision_choice(cases)
    def test_same_basis_conflict_cannot_be_erased(self):
        args=copy.deepcopy(material('lumen_technologies')[0])
        for f in args['facts']:
            if f['concept']=='us-gaap:DebtAndCapitalLeaseObligations' and f['period_start']==f['period_end']==args['target']['period_end']:f['value']='18000000000'
        r,t,o,a=route.resolve_primary(**args);self.assertEqual('WITHHELD',r['publication']);self.assertTrue(any('COMPANYFACTS_XBRL_CONFLICT' in x for x in a['reasons']))
    def test_changed_raw_lease_asset_or_payment_cannot_reuse_source_judgment(self):
        args,xmlargs=material('salesforce')
        for before,after in [(b'FinanceLeaseLiability',b'FinanceLeaseRightOfUseAsset'),(b'FinanceLeaseLiability',b'FinanceLeaseLiabilityPaymentsDue'),(b'535000000',b'536000000')]:
            changed={**xmlargs,'raw':xmlargs['raw'].replace(before,after)};self.assertNotEqual(changed['raw'],xmlargs['raw']);self.assertIsNone(scope_inputs(**changed))
            r,t,o,a=route.resolve_primary(**{**args,'measurement':None});self.assertEqual('WITHHELD',r['publication'])
    def test_changed_source_context_or_unit_cannot_reuse_identity(self):
        args,x=material('macys')
        with self.assertRaisesRegex(ValueError,'ACCESSION'):scope_inputs(**{**x,'target':{**x['target'],'accession':'0000000001-26-000001'}})
        with self.assertRaisesRegex(ValueError,'CONTEXT'):scope_inputs(**{**x,'target':{**x['target'],'entity':'1'}})
        with self.assertRaisesRegex(ValueError,'SOURCE'):scope_inputs(**{**x,'source':{**x['source'],'raw_asset_id':'sha256:'+'0'*64}})
    def test_nested_component_expression_uses_existing_trace_no_answer_literals(self):
        text=(ROOT/route.SPEC_PATH).read_text();body=json.loads(text.split('---')[1]);branches=body['inputs']['debt']['choose_first'];b=next(x['derived_role'] for x in branches if 'derived_role' in x and any(isinstance(a,dict) for a in x['derived_role']['args']))
        for bad in ['999','undeclared',{'op':'divide','args':['principal','missing']}]:
            modified=copy.deepcopy(body);target=next(x['derived_role'] for x in modified['inputs']['debt']['choose_first'] if 'derived_role' in x and any(isinstance(a,dict) for a in x['derived_role']['args']));target['args'][0]=bad
            with self.assertRaises(SpecError):compile_spec(text='---\n'+json.dumps(modified)+'\n---\n',dependency_specs={})
        r,t,o,a=self.resolve('macys');step=next(s for s in t['steps'] if s['event']=='DERIVED_BRANCH_SELECTED');self.assertEqual('2445000000',step['value'])

if __name__=='__main__':unittest.main()
