"""Independent small probes. No source mutation or financial-source/network call."""
import ast
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_b03_current_input_scope import original, observation, PERIOD
from tests.vnext.test_b03_calculator import fact, ACCESSION
from vnext import normal_zero_ai_results as resolver
from vnext import ordinary_current_update as update
from vnext import text_results_v2 as context_rules
from vnext.ordinary_b03_input_scope import inspect_depreciation_input
from vnext import company_current_records as current
from vnext.ordinary_saved_result import read_saved_result


def canonical_original(rows):
    return original(rows).replace(b'xmlns:gaap=', b'xmlns:us-gaap=').replace(b'name="gaap:', b'name="us-gaap:')


class BoundaryProbes(unittest.TestCase):
    def test_context_policy_change_changes_scope_but_not_update_configuration(self):
        raw=canonical_original([('DepreciationDepletionAndAmortization','20','INF')])
        args=dict(raw_bytes=raw,entity='195',period=PERIOD,observations=[observation('DepreciationDepletionAndAmortization','20')])
        self.assertEqual(inspect_depreciation_input(**args)['status'],'KEEP')
        before=update._configuration(REPO_ROOT,'marriott_international','B03')
        changed=deepcopy(context_rules._CAPABILITY_POLICY)
        changed['cik_identifier_schemes']=['https://www.sec.gov/CIK']
        real_hash=update.sha256_file
        def changed_hash(*,path):
            return 'changed-policy-hash' if Path(path).name=='text_results_v2_policy.json' else real_hash(path=path)
        with patch.object(context_rules,'_CAPABILITY_POLICY',changed), patch.object(update,'sha256_file',side_effect=changed_hash):
            with self.assertRaisesRegex(ValueError,'D02_FACT_ENTITY_SCHEME_NOT_PROVEN'):
                inspect_depreciation_input(**args)
            after=update._configuration(REPO_ROOT,'marriott_international','B03')
            previous={'company_id':'marriott_international','metric_id':'B03','version':'old',
                'configuration':before,'source_census':[],'result_id':'saved-old-result'}
            saved={'manifest':{'company_id':'marriott_international','metric_id':'B03','source_proofs':[]},
                'result':{'result_id':'saved-old-result'}}
            with tempfile.TemporaryDirectory() as temporary, patch.object(update,'_recover',return_value=previous), \
                patch.object(update,'_source_census',return_value=[]),patch.object(update,'read_saved_result',return_value=saved), \
                patch.object(update,'create_saved_result',side_effect=AssertionError('reuse bypasses revalidation')):
                report=update.run_once(state_root=Path(temporary)/'state',source_root=REPO_ROOT,
                    company_id='marriott_international',metric_id='B03')
                self.assertEqual(report['status'],'NO_SOURCE_CONTENT_CHANGE')
                self.assertEqual(report['result_id'],'saved-old-result')
        self.assertEqual(before,after)
        self.assertNotIn('catalog/r6/text_results_v2_policy.json',before['processing_files'])
        print('CONFIRMED: scope policy changes acceptance but real updater reuses saved-old-result as NO_SOURCE_CONTENT_CHANGE')

    def test_valid_namespace_alias_composition_is_falsely_rejected(self):
        rows=[('Depreciation','7','INF'),('AmortizationOfIntangibleAssets','13','INF')]
        observations=[{'semantic_role':role,'value':value,'source_binding':{'concept':'us-gaap:'+concept}}
            for role,concept,value in [('depreciation','Depreciation','7'),('amortization','AmortizationOfIntangibleAssets','13')]]
        args=dict(entity='195',period=PERIOD,observations=observations)
        self.assertEqual(inspect_depreciation_input(raw_bytes=canonical_original(rows),**args)['status'],'KEEP')
        with self.assertRaisesRegex(ValueError,'B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NOT_IN_ORIGINAL:depreciation'):
            inspect_depreciation_input(raw_bytes=original(rows),**args)
        print('CONFIRMED: identical namespace URI with gaap prefix rejects composed input; us-gaap prefix keeps it')

    def _resolve(self, *, selected_later_available=True, guard=True):
        rows=[('DepreciationDepletionAndAmortization','10','INF'),('DepreciationAndAmortization','20','INF'),
              ('Depreciation','7','INF'),('AmortizationOfIntangibleAssets','13','INF')]
        raw=canonical_original(rows)
        structured=[fact(concept='us-gaap:'+c,value=v,entity='195') for c,v in
            [('Revenues','1000'),('OperatingIncomeLoss','100'),('DepreciationDepletionAndAmortization','10'),
             ('Depreciation','7'),('AmortizationOfIntangibleAssets','13')]]
        if selected_later_available:
            structured.append(fact(concept='us-gaap:DepreciationAndAmortization',value='20',entity='195'))
        prepared={'company_id':'company_fixture','entity':'195','table_input':{'target_period':PERIOD},
                  'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},'filing':{'accessionNumber':ACCESSION},
                  'amendments':[],'source_proofs':[]}
        class Sources:
            def __init__(self,*args):
                self.proofs={};self.records={};self.failed_attempts={}
            def primary(self,filing):return {'raw_bytes':raw}
            def read(self,*args,**kwargs):return {'raw_bytes':b'{}','source_reference':{}}
        with ExitStack() as stack:
            for name,value in [('_authority',lambda *args:{}),('prepare_saved_annual_input',lambda **kwargs:prepared),
                ('verify_ordinary_source_proofs',lambda **kwargs:{}),('_Sources',Sources),
                ('repository_company_traits',lambda **kwargs:['non_financial']),('_exact_set',lambda *args,**kwargs:{}),
                ('companyfacts_structured_facts',lambda **kwargs:structured),('adapt_companyfacts',lambda **kwargs:[])]:
                stack.enter_context(patch.object(resolver,name,value))
            scope=stack.enter_context(patch('vnext.ordinary_b03_input_scope.inspect_depreciation_input',wraps=inspect_depreciation_input))
            calc=stack.enter_context(patch.object(resolver,'calculate_metric',wraps=resolver.calculate_metric))
            stack.enter_context(patch('vnext.b03_contract_amortization_scope.assess_current_b03_scope',
                return_value={'status':'NO_EXPLICIT_NARROW_SCOPE_FOUND','blocked':False}))
            answer=resolver.resolve_ordinary_zero_ai_metric(repo_root=REPO_ROOT,company_id='company_fixture',
                metric_id='B03',validate_depreciation_scope=guard)
            return answer,scope.call_count,calc.call_count

    def test_actual_resolver_retake_uses_real_calculator_once_and_retains_decision(self):
        answer,scope_count,calc_count=self._resolve()
        self.assertEqual(answer['result']['value'],'0.12')
        selected=[o for o in answer['observations'] if o['semantic_role']=='depreciation_and_amortization']
        self.assertEqual(selected[0]['source_binding']['concept'],'us-gaap:DepreciationAndAmortization')
        decision=answer['selection']['depreciation_scope']
        self.assertEqual(decision['status'],'KEEP');self.assertEqual(decision['retake_decision']['status'],'RETAKE')
        self.assertEqual((scope_count,calc_count),(2,3)) # B01, B03, exactly one B03 retake
        print('PASS: actual resolver/calculator retake selects20, ratio0.12, original decision preserved')

    def test_retake_without_selected_companyfacts_stops_and_withholds(self):
        answer,scope_count,calc_count=self._resolve(selected_later_available=False)
        self.assertEqual(answer['result']['publication'],'WITHHELD')
        self.assertEqual(answer['result']['reason_code'],'B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN')
        self.assertEqual(answer['observations'],[])
        self.assertEqual(answer['selection']['depreciation_scope']['why'],'ONE_APPROVED_RETAKE_DID_NOT_PROVE_PRIMARY_QUANTITY')
        self.assertEqual((scope_count,calc_count),(2,3))
        print('PASS: failed single retake withholds and clears selected B03 observations')

    def test_legacy_default_is_opt_in_and_keeps_original_chain(self):
        answer,scope_count,calc_count=self._resolve(guard=False)
        self.assertEqual(answer['result']['value'],'0.11')
        self.assertNotIn('depreciation_scope',answer['selection'])
        self.assertEqual((scope_count,calc_count),(0,2))
        print('PASS: omitted legacy scope option keeps chain10/ratio0.11')

    def test_two_exact_withdrawals_and_unrelated_identity(self):
        registry=current._registry()
        defects=[d for d in registry['defects'] if d['defect_id'].startswith('B03_SALESFORCE_FY2026_')]
        self.assertEqual(len(defects),2)
        for d in defects:
            result={k:d[k] for k in ['company_id','metric_id','period_end','result_id']}
            self.assertEqual(current._defects(result,registry),[d['defect_id']])
            result['result_id']='independent-corrected-identity'
            self.assertEqual(current._defects(result,registry),[])
        print('PASS: both exact old wrong IDs held; unrelated result identity not withdrawn')

    def test_sidecar_reader_links_coordinates_and_does_not_calculate(self):
        answer,_,_=self._resolve()
        def encoded(value):return (json.dumps(value,sort_keys=True)+'\n').encode()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            result=answer['result']
            assessment={'record_type':'ORDINARY_INPUT_ASSESSMENTS_V1','company_id':result['company_id'],
                'metric_id':'B03','input_id':'probe-input','result_id':result['result_id'],
                'target_period':PERIOD,'assessments':{'depreciation_scope':answer['selection']['depreciation_scope']}}
            files={'records.jsonl':b''.join(encoded(r) for r in answer['records']),
                'receipt.json':encoded({}), 'metrics_matrix.csv':b'fixture\n', 'metric_evidence.csv':b'fixture\n',
                'input-assessments.json':encoded(assessment)}
            manifest={'record_type':'ORDINARY_SAVED_RESULT_V1','status':'CALCULATED','company_id':result['company_id'],
                'metric_id':'B03','result_id':result['result_id'],'input_id':'probe-input','target_period':PERIOD,
                'compiled_specs':{'B03':answer['compiled_spec']},
                'files':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}}
            for name,raw in files.items():(root/name).write_bytes(raw)
            (root/'manifest.json').write_bytes(encoded(manifest))
            with patch.object(resolver,'calculate_metric',side_effect=AssertionError('reader must not recalculate')):
                saved=read_saved_result(output_root=root)
                self.assertEqual(saved['input_assessments'],assessment['assessments'])
            # Ordinary stale-coordinate accident, with byte hash correctly recorded.
            assessment['input_id']='another-input'
            raw=encoded(assessment);(root/'input-assessments.json').write_bytes(raw)
            manifest['files']['input-assessments.json']=hashlib.sha256(raw).hexdigest()
            (root/'manifest.json').write_bytes(encoded(manifest))
            with self.assertRaisesRegex(ValueError,'SAVED_INPUT_ASSESSMENT_COORDINATE_CHANGED'):
                read_saved_result(output_root=root)
        print('PASS: sidecar read retains decision without calculation; mismatched input coordinate is rejected')

    def test_extracted_financial_helper_ast_is_identical(self):
        base=subprocess.run(['git','show','4e2f4b2dddabd0ab2847a583e5acf457282c2b95:scripts/vnext/normal_candidates.py'],
            check=True,capture_output=True,text=True).stdout
        old=next(n for n in ast.parse(base).body if isinstance(n,ast.FunctionDef) and n.name=='_prepare_b06')
        new=next(n for n in ast.parse((REPO_ROOT/'scripts/vnext/normal_governance_input.py').read_text()).body
            if isinstance(n,ast.FunctionDef) and n.name=='prepare_saved_original_financial_sources')
        old.name=new.name
        # _Sources previously imported inside old function; it is defined in new module.
        self.assertEqual(ast.dump(old.body[0],include_attributes=False),"ImportFrom(module='normal_governance_input', names=[alias(name='_Sources')], level=1)")
        old.body=old.body[1:]
        self.assertEqual(ast.dump(old,include_attributes=False),ast.dump(new,include_attributes=False))
        from vnext.normal_candidates import _prepare_b06
        from vnext.normal_governance_input import prepare_saved_original_financial_sources
        self.assertIs(_prepare_b06,prepare_saved_original_financial_sources)
        print('PASS: extracted helper AST unchanged apart from import relocation/name; legacy alias same callable')


if __name__=='__main__':unittest.main(verbosity=2)
