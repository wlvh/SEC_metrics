"""Small full-group gate controls; real company CLI is separate evidence."""
from copy import deepcopy
import unittest
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


if __name__=='__main__':unittest.main()
