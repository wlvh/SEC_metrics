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
