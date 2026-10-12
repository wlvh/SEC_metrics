"""Small full-group gate controls; real company CLI is separate evidence."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.vnext import ordinary_current_update as update
from vnext.current_d04_result import require_complete_assessment


class CurrentD04CompanyGateTest(unittest.TestCase):
    def complete(self):
        return {'all_source_requests_accepted':True,'missing_request_ids':[],
            'failed_requests':[],'required_request_ids':['one','two'],
            'proposed_branch':'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW',
            'completed':[{'request_id':name,'evidence':{'status':'PASS'},
                'candidate':{'selected':{'source_assessment':{'findings':[
                    {'kind':'CONDITIONAL_OR_BOILERPLATE','subject':'TARGET_REGISTRANT',
                     'timing':'CONDITIONAL'}]}}}} for name in ('one','two')]}

    def test_complete_nonempty_findings_are_allowed_without_inventing_doubt(self):
        value=self.complete();before=deepcopy(value)
        require_complete_assessment(value)
        self.assertEqual(value,before)

    def test_missing_group_cannot_be_complete_even_with_a_stale_true_flag(self):
        value=self.complete();value['completed'].pop()
        with self.assertRaisesRegex(ValueError,'COMPLETE_SAVED_RESPONSE_SET'):
            require_complete_assessment(value)

    def test_missing_failed_and_conflicting_groups_are_rejected(self):
        for key,value in [('all_source_requests_accepted',False),
                ('missing_request_ids',['two']),('failed_requests',[{'request_id':'two'}]),
                ('proposed_branch','CROSS_REQUEST_GOING_CONCERN_RECONCILIATION_REQUIRED')]:
            with self.subTest(key=key):
                current=self.complete();current[key]=value
                with self.assertRaisesRegex(ValueError,'COMPLETE_SAVED_RESPONSE_SET'):
                    require_complete_assessment(current)

    def test_unresolved_or_failed_evidence_is_never_company_credit(self):
        for key in ('kind','subject','timing'):
            current=self.complete();current['completed'][0]['candidate']['selected']['source_assessment']['findings'][0][key]='UNRESOLVED'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'SAVED_RESPONSE_UNRESOLVED'):
                require_complete_assessment(current)
        current=self.complete();current['completed'][0]['evidence']['status']='FAIL'
        with self.assertRaisesRegex(ValueError,'SAVED_RESPONSE_UNRESOLVED'):
            require_complete_assessment(current)


class CurrentD04DependencyUpdateTest(unittest.TestCase):
    def test_source_or_interpretation_change_rechecks_once_then_reuses(self):
        # Real configuration and controller; source observation and saved
        # business records are isolated small substitutes, never AI evidence.
        root=Path(__file__).resolve().parents[2]
        original_hash=update.sha256_file
        for relative in ('scripts/vnext/going_concern_source.py',
                'catalog/r6/going_concern_source_rules_v1.json',
                'catalog/r6/semantic_source_v1.json',
                'catalog/r6/regulatory_investigation_candidates_v1.json',
                'scripts/vnext/r6_semantic_review.py',
                'scripts/vnext/invocation_control.py'):
            with self.subTest(dependency=relative),tempfile.TemporaryDirectory() as folder:
                records={};calls=[]
                def create(**kwargs):
                    calls.append(kwargs);path=kwargs['output_root'];path.mkdir(parents=True)
                    record={'manifest':{'company_id':'enphase_energy','metric_id':'D04','source_proofs':[]},
                        'result':{'company_id':'enphase_energy','metric_id':'D04','publication':'WITHHELD',
                            'period_end':'2025-12-31','result_id':'synthetic-d04-'+str(len(calls)),
                            'reason_code':'SYNTHETIC_DEPENDENCY_CONTROL'}}
                    records[str(path)]=deepcopy(record);return record
                args=dict(state_root=Path(folder)/'state',source_root=root,
                    company_id='enphase_energy',metric_id='D04')
                with patch.object(update,'_source_census',return_value=[]), \
                     patch.object(update,'_current_sources',return_value=[]), \
                     patch.object(update,'create_saved_result',side_effect=create), \
                     patch.object(update,'read_saved_result',side_effect=lambda **kwargs:records[str(kwargs['output_root'])]):
                    first=update.run_once(**args)
                    previous=deepcopy(records[first['result_root']])
                    def changed(*,path):
                        return 'changed-consumed-d04-rule' if path==root/relative else original_hash(path=path)
                    with patch.object(update,'sha256_file',side_effect=changed):
                        second=update.run_once(**args)
                        with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated D04 processing')):
                            repeated=update.run_once(**args)
                self.assertEqual(second['status'],'CANDIDATE_WITHHELD')
                self.assertNotEqual(second['version'],first['version'])
                self.assertEqual(repeated['status'],'PREVIOUS_INPUT_WITHHELD')
                self.assertEqual(repeated['result_id'],second['result_id'])
                self.assertFalse(repeated['calculation_performed'])
                self.assertEqual(len(calls),2)
                self.assertEqual(records[first['result_root']],previous)
                self.assertTrue(Path(first['result_root']).is_dir())


if __name__=='__main__':unittest.main()


class CurrentD04ParsedReuseTest(unittest.TestCase):
    """Small controller states, constructed saved result and explicit parse stub."""
    def setUp(self):
        from tests.vnext.test_ordinary_current_update import CurrentUpdateTest
        CurrentUpdateTest.setUp(self)
        self.publication='WITHHELD'
        self.old_task={'method':'ORDINARY_D04_COMPLETE_TASK_INPUT_V1','body':'complete-task-a'}
        from vnext.canonical import content_hash
        self.old_task['task_input_id']=content_hash(value=self.old_task)
        self.new_task=dict(self.old_task)
        self.current_proof=dict(self.proof)
        self.created=[]
        def create(**kwargs):
            self.created.append(kwargs);path=kwargs['output_root'];path.mkdir(parents=True)
            record={'manifest':{'company_id':'marriott_international','metric_id':'D04',
                'source_proofs':[dict(self.current_proof)]},'result':{
                'company_id':'marriott_international','metric_id':'D04','publication':self.publication,
                'period_end':'2025-12-31','result_id':'d04-result-'+str(len(self.created)),
                'reason_code':'SYNTHETIC_FULL_TASK'},
                'input_assessments':{'d04_task_input':dict(self.new_task)}}
            self.records[str(path)]=record;return record
        p=patch.object(update,'create_saved_result',side_effect=create);p.start();self.addCleanup(p.stop)
        p=patch.object(update,'_current_sources',side_effect=lambda *a:[dict(self.current_proof)]);p.start();self.addCleanup(p.stop)
        p=patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=lambda **kw:dict(self.new_task));p.start();self.addCleanup(p.stop)

    def run_d04(self):
        return update.run_once(state_root=self.root,source_root=Path(__file__).resolve().parents[2],
            company_id='marriott_international',metric_id='D04')

    def changed_raw(self):
        self.current_proof['content_sha256']='script-only-new-bytes'
        self.census[0]['content_sha256']='script-only-new-bytes'

    def test_changed_raw_same_task_reuses_withheld_then_no_second_parse(self):
        first=self.run_d04();self.changed_raw()
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No full assessment replay')):
            same=self.run_d04()
            self.assertEqual(same['status'],'PREVIOUS_INPUT_WITHHELD')
            self.assertFalse(same['raw_input_unchanged']);self.assertTrue(same['task_input_unchanged'])
            self.assertEqual(first['result_id'],same['result_id'])
            with patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('No second parse')):
                third=self.run_d04()
        self.assertEqual(third['status'],'PREVIOUS_INPUT_WITHHELD')
        self.assertEqual(len(self.created),1)

    def test_check_only_change_with_same_raw_reuses_without_parsing(self):
        self.config['processing_files']={'scripts/vnext/request_bindings.py':'check-one'}
        first=self.run_d04()
        self.config['processing_files']={'scripts/vnext/request_bindings.py':'check-two'}
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No unchanged-raw calculation')), \
             patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('No unchanged-raw parse')):
            repeated=self.run_d04()
        self.assertEqual('PREVIOUS_INPUT_WITHHELD',repeated['status'])
        self.assertEqual(first['result_id'],repeated['result_id'])
        self.assertEqual('check-two',repeated['source_check_versions']['scripts/vnext/request_bindings.py'])
        self.assertEqual(1,len(self.created))

    def test_changed_raw_and_check_version_does_not_relax_parsed_equivalence(self):
        self.config['processing_files']={'scripts/vnext/request_bindings.py':'check-one'}
        first=self.run_d04();self.changed_raw()
        self.config['processing_files']={'scripts/vnext/request_bindings.py':'check-two'}
        # Exact configuration is still required for interpreting new bytes.
        # This fallback uses an explicit constructed saved-response processor;
        # it gives no new provider execution permission.
        with patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('Changed config must not use parsed equivalence')):
            changed=self.run_d04()
        self.assertEqual('CANDIDATE_WITHHELD',changed['status'])
        self.assertNotEqual(first['result_id'],changed['result_id'])
        self.assertEqual(2,len(self.created))

    def test_changed_business_input_or_configuration_does_not_reuse(self):
        first=self.run_d04();self.changed_raw();self.new_task={'method':'ORDINARY_D04_COMPLETE_TASK_INPUT_V1','body':'new-business-task'}
        from vnext.canonical import content_hash
        self.new_task['task_input_id']=content_hash(value=self.new_task)
        second=self.run_d04();self.assertEqual(len(self.created),2)
        self.assertNotEqual(first['result_id'],second['result_id'])
        self.config['processing_version']='two'
        with patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('Do not parse under changed rules')):
            third=self.run_d04()
        self.assertEqual(len(self.created),3)

    def test_new_company_source_dependency_cannot_be_ignored_by_equal_parse(self):
        self.run_d04();self.changed_raw()
        self.census.append({'source_url':'new-annual-or-relation','content_sha256':'new',
                            'status_code':'200','error':''})
        with patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('No incomplete census comparison')):
            second=self.run_d04()
        self.assertEqual(second['status'],'CANDIDATE_WITHHELD');self.assertEqual(len(self.created),2)

    def test_parse_failure_falls_back_to_complete_processing(self):
        self.run_d04();self.changed_raw()
        with patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=ValueError('Source parse unresolved')):
            second=self.run_d04()
        self.assertEqual(second['status'],'CANDIDATE_WITHHELD');self.assertEqual(len(self.created),2)

    def test_success_and_withheld_both_preserve_original_credit_on_equal_task(self):
        self.publication='PUBLISHED'
        first=self.run_d04();self.changed_raw()
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated company assessment')):
            second=self.run_d04()
        self.assertEqual(second['status'],'NO_SOURCE_CONTENT_CHANGE')
        self.assertEqual(first['result_id'],second['result_id'])
        self.assertEqual(len(self.created),1)

    def test_old_record_without_task_assessment_uses_original_processing(self):
        first=self.run_d04();self.records[first['result_root']].pop('input_assessments');self.changed_raw()
        second=self.run_d04();self.assertEqual(len(self.created),2)
        self.assertNotEqual(first['result_id'],second['result_id'])

    def test_source_failures_are_not_cleared_by_equal_task(self):
        self.run_d04();self.changed_raw();self.census[0]['status_code']='503'
        with patch('scripts.vnext.ordinary_d04_task_input.fingerprint',side_effect=AssertionError('No parsed reuse during source failure')):
            self.run_d04()
        self.assertEqual(len(self.created),2)

    def test_reuse_pointer_interruption_recovers_original_result(self):
        first=self.run_d04();self.changed_raw();original=update._write
        def interrupted(path,value):
            if path.name=='completed-check.json':raise RuntimeError('after comparison terminal')
            return original(path,value)
        with patch.object(update,'_write',side_effect=interrupted),patch.object(update,'create_saved_result',side_effect=AssertionError('No new result')):
            failed=self.run_d04()
        self.assertEqual(failed['status'],'INPUT_OR_EXECUTION_FAILED')
        # Existing failure recording overwrites the terminal, so this attempt
        # must be safely recomputed as a comparison, never as a fake Result.
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No new result')):
            recovered=self.run_d04()
        self.assertEqual(first['result_id'],recovered['result_id'])
        self.assertEqual(len(self.created),1)


class D04SavedResponseOnlyBoundaryTest(unittest.TestCase):
    def test_saved_response_object_cannot_execute_even_if_replay_flag_is_cleared(self):
        from dataclasses import replace
        from vnext import continuous_semantic_calls as calls
        prepared=calls.SemanticRequest(calls._FACTORY,b'{}',b'{}',b'{}',b'{}',{}, {},
            replay_only=True,d04_saved_response_only=True)
        for value in (prepared,replace(prepared,replay_only=False)):
            with self.subTest(replay=value.replay_only):
                with self.assertRaisesRegex(ValueError,'D04_SAVED_RESPONSE_CANNOT_EXECUTE'):
                    calls._execute_semantic(prepared=value,ledger=None,recorded_wire=None,native_assessment=True)

    def test_default_request_is_not_saved_response_only(self):
        from vnext import continuous_semantic_calls as calls
        request=calls.SemanticRequest(calls._FACTORY,b'{}',b'{}',b'{}',b'{}',{}, {})
        self.assertFalse(request.d04_saved_response_only)
