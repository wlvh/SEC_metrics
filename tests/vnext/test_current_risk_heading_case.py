"""Small current D01 adapter controls; source doubles are not content acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import BODY, annual, binding
from tests.vnext.test_text_results import source_arguments
from vnext import current_risk_heading_case as current
from vnext import d01_emphasis_results as api
from vnext import ordinary_current_update as update
from vnext import company_current_records as company
from vnext.specs import compile_spec_file
from vnext.canonical import content_hash


class CurrentRiskHeadingCaseTest(unittest.TestCase):
    def args(self, count):
        raw=annual(BODY.replace('<p>A supply constraint could affect production.</p>',
            ''.join('<p><b>Risk number %s</b>. Explanation.</p>'%i for i in range(count))))
        args=source_arguments(binding(raw))
        args['compiled_spec']=compile_spec_file(path=REPO_ROOT/current.SPEC_PATH, dependency_specs={})
        scope=args['compiled_spec']['compiled']['required_claims']
        args['target'].update(scope=scope, scope_key=content_hash(value=scope))
        args['d01_emphasis_policy']=api.RUNNING_HEADER_POLICY
        return args

    def test_old_capacity_is_kept_and_only_true_overflow_uses_successor(self):
        for count,path in ((2,current.SPEC_PATH),(64,current.SPEC_PATH),(68,current.CAPACITY_SPEC_PATH),(128,current.CAPACITY_SPEC_PATH)):
            with self.subTest(count=count):
                args=self.args(count);candidate,used=current._candidate(api,args,REPO_ROOT)
                self.assertEqual(used,path);self.assertEqual(len(candidate['selected']),count)
                api.build_text_evidence(candidate=candidate,**args)

    def test_zero_and_129_never_become_partial_results(self):
        for count in (0,129):
            with self.subTest(count=count),self.assertRaises(ValueError):
                current._candidate(api,self.args(count),REPO_ROOT)

    def test_source_error_does_not_enter_capacity_fallback(self):
        args=self.args(2);args['target']['entity']='54321'
        with patch('vnext.specs.compile_spec_file') as unused:
            with self.assertRaisesRegex(ValueError,'filing identity differs'):
                current._candidate(api,args,REPO_ROOT)
            unused.assert_not_called()

    def test_changed_successor_scope_is_refused(self):
        successor=compile_spec_file(path=REPO_ROOT/current.CAPACITY_SPEC_PATH,dependency_specs={})
        successor['compiled']['required_claims']['extra']='Changed business scope'
        args=self.args(68)
        with patch('vnext.specs.compile_spec_file',return_value=successor):
            with self.assertRaisesRegex(ValueError,'CAPACITY_SEMANTICS_CHANGED'):
                current._candidate(api,args,REPO_ROOT)

    def test_complete_factory_uses_source_heading_and_current_period(self):
        args=self.args(2);ref=args['source_references'][0];blob=next(iter(args['raw_blobs'].values()))
        prepared={'entity':'12345','filing':{'accessionNumber':ref['accession']},'amendments':[],
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},'source_proofs':[],
            'table_input':{'target_period':{'period_start':'2025-01-01','period_end':'2025-12-31','fiscal_year':2025}}}
        class Reader:
            def __init__(self,*args):self.records={'blob':blob,'ref':ref};self.proofs={}
            def primary(self,filing):return {'source_reference':ref,'raw_blob':blob,'raw_bytes':next(iter(args['raw_bytes_by_id'].values()))}
        with patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',return_value=prepared),\
             patch('vnext.normal_governance_input._Sources',Reader),\
             patch('vnext.traits.repository_company_traits',return_value=[]),\
             patch('vnext.ordinary_source_authority.verify_ordinary_source_proofs',return_value={'test_only':True}):
            case=current.prepare_current_risk_heading_case(repo_root=REPO_ROOT,company_id='sample_entity',metric_id='D01')
            self.assertEqual(case['results']['D01']['value'],'Risk number 0\nRisk number 1')
            self.assertEqual(case['target_period']['fiscal_year'],2025)
            self.assertEqual(case['selection']['heading_count'],2)
            self.assertFalse(case['selection']['risk_occurrence_asserted'])
            for changed in ({'amendments':[{'form':'10-K/A'}]}, {'subject_policy':{'mode':'SUCCESSOR'}}):
                with patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',return_value={**prepared,**changed}),self.assertRaisesRegex(current.CurrentRiskHeadingError,'NOT_RECEIVED'):
                    current.prepare_current_risk_heading_case(repo_root=REPO_ROOT,company_id='sample_entity',metric_id='D01')

    def test_cli_selects_current_d01_without_opening_shared_default(self):
        from vnext.company_local import run_local
        with patch.object(company,'run_saved_company',return_value={'test_only':True}) as run:
            run_local(company_id='enphase_energy',source_root=REPO_ROOT,work_dir='/tmp/d01-work',
                output_dir='/tmp/d01-output',metric_ids=['D01'])
            self.assertIs(run.call_args.kwargs['current_case_factories']['D01'],current.prepare_current_risk_heading_case)
            self.assertEqual(run.call_args.kwargs['processing_files_by_metric']['D01'],current.PROCESSING_FILES)
        with patch.object(company,'run_saved_company',return_value={}) as run:
            current.run_current_saved_company(company_id='enphase_energy',source_root=REPO_ROOT,
                work_dir='/tmp/work',output_dir='/tmp/out',metric_ids=['B01'])
            self.assertNotIn('current_case_factories',run.call_args.kwargs)

    def test_current_factory_is_incompatible_with_historical_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'CURRENT_FACTORY_SCOPE_INVALID'):
                update.run_once(state_root=Path(temp)/'state',source_root=REPO_ROOT,
                    company_id='enphase_energy',metric_id='D01',fiscal_year=2024,
                    case_factory=current.prepare_current_risk_heading_case,
                    current_case_factory=current.prepare_current_risk_heading_case)


if __name__=='__main__':unittest.main()
