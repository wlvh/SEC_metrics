"""Source routing and complete-set semantics, not model accuracy."""
from pathlib import Path
from unittest.mock import patch
import unittest

from vnext import d03_native_preparation as prepare
from vnext import d03_complete_interpretation as interpret
from vnext.normal_source_authority import ROOT


class D03InterpretationSourceRootTest(unittest.TestCase):
    def inputs(self):
        request={'request_id':'original','source_id':'source','company_id':'constructed',
                 'units':[{'unit_id':'unit'}],'required_candidate_assessments':[],
                 'source_statement_facts':[]}
        source={'semantic_source_id':'source','required_unit_ids':['unit'],'company_id':'constructed'}
        with patch.object(prepare,'prepare_regulatory_semantic_source',return_value=source), \
             patch.object(prepare,'requests_from_source',return_value=[request]):
            prepared=prepare.prepare_native_input(company_id='constructed')
        return source,request,prepared

    def test_prepare_and_interpret_use_the_same_external_source_root(self):
        source,request,prepared=self.inputs();data=Path('/external-registered-source')
        with patch.object(prepare,'prepare_regulatory_semantic_source',return_value=source) as rebuild, \
             patch.object(prepare,'requests_from_source',return_value=[request]):
            actual=prepare.prepare_native_input(company_id='constructed',source_root=data)
        self.assertEqual(prepared,actual)
        rebuild.assert_called_once_with(repo_root=data,company_id='constructed',
            request_context_format=prepare.FORMAT_VERSION,ordinary_registered=True)
        checked={'findings':[],'unresolved':['constructed uncertainty']}
        with patch.object(interpret,'prepare_native_input',return_value=prepared) as reprepare, \
             patch.object(interpret,'requests_from_source',return_value=[request]), \
             patch.object(interpret,'validate_response',return_value=checked):
            proposal=interpret.validate_complete_interpretation(prepared_input=prepared,
                response_bytes_by_request={'original':b'constructed'},source_root=data)
        reprepare.assert_called_once_with(company_id='constructed',source_root=data)
        self.assertEqual('UNRESOLVED_REQUIRES_REVIEW',proposal['proposed_branch'])
        self.assertEqual([0],proposal['unresolved_group_indices'])
        self.assertFalse(proposal['native_result_or_run_created'])

    def test_legacy_default_is_preserved_and_missing_group_is_rejected(self):
        source,request,prepared=self.inputs()
        with patch.object(prepare,'prepare_regulatory_semantic_source',return_value=source) as rebuild, \
             patch.object(prepare,'requests_from_source',return_value=[request]):
            prepare.prepare_native_input(company_id='constructed')
        rebuild.assert_called_once_with(repo_root=ROOT,company_id='constructed',request_context_format=prepare.FORMAT_VERSION)
        with patch.object(interpret,'prepare_native_input',return_value=prepared) as reprepare, \
             self.assertRaisesRegex(ValueError,'RESPONSE_SET_CHANGED'):
            interpret.validate_complete_interpretation(prepared_input=prepared,response_bytes_by_request={})
        reprepare.assert_called_once_with(company_id='constructed')

    def test_positive_proposal_stays_pending_and_empty_answer_never_means_absence(self):
        source,request,prepared=self.inputs()
        positive={'kind':'CURRENT_REGULATORY_ACTION','subject':'TARGET_REGISTRANT',
                  'timing':'CURRENT_REPORT','reported_status':'ONGOING_AS_REPORTED',
                  'evidence':[]}
        for findings,branch in (([positive],'CURRENT_DISCLOSURE_REQUIRES_NATIVE_REVIEW'),
                                ([], 'ABSENCE_RULE_NOT_APPROVED')):
            with self.subTest(branch=branch),patch.object(interpret,'prepare_native_input',return_value=prepared), \
                 patch.object(interpret,'requests_from_source',return_value=[request]), \
                 patch.object(interpret,'validate_response',return_value={'findings':findings,'unresolved':[]}):
                result=interpret.validate_complete_interpretation(prepared_input=prepared,
                    response_bytes_by_request={'original':b'constructed'},source_root=Path('/external-registered-source'))
            self.assertEqual(branch,result['proposed_branch'])
            self.assertFalse(result['provider_execution_identity_verified'])
            self.assertFalse(result['native_candidate_or_evidence_created'])
            self.assertFalse(result['native_result_or_run_created'])

    def test_anchor_request_and_response_use_external_root_without_fact_credit(self):
        source,original,_=self.inputs();data=Path('/external-registered-source')
        original['source_statement_facts']=[{'constructed_anchor':True}]
        effective={k:v for k,v in original.items() if k!='source_statement_facts'}
        effective['request_id']='effective';effective['source_fact_review_contract']={
            'version':prepare.ANCHOR_VERSION,'original_request_id':'original'}
        with patch.object(prepare,'prepare_regulatory_semantic_source',return_value=source), \
             patch.object(prepare,'requests_from_source',return_value=[original]), \
             patch.object(prepare,'candidate_request',return_value=effective) as candidate:
            prepared=prepare.prepare_native_input(company_id='constructed',source_root=data)
        self.assertEqual(data,candidate.call_args.kwargs['repo_root'])
        checked={'findings':[],'unresolved':['constructed anchor uncertainty'],
                 'source_fact_current_status_proven_by_program':False}
        with patch.object(interpret,'prepare_native_input',return_value=prepared), \
             patch.object(interpret,'requests_from_source',return_value=[original]), \
             patch.object(interpret,'validate_candidate_response',return_value=checked) as validate:
            result=interpret.validate_complete_interpretation(prepared_input=prepared,
                response_bytes_by_request={'effective':b'constructed'},source_root=data)
        self.assertEqual(data,validate.call_args.kwargs['repo_root'])
        self.assertEqual('UNRESOLVED_REQUIRES_REVIEW',result['proposed_branch'])
        checked['source_fact_current_status_proven_by_program']=True
        with patch.object(interpret,'prepare_native_input',return_value=prepared), \
             patch.object(interpret,'requests_from_source',return_value=[original]), \
             patch.object(interpret,'validate_candidate_response',return_value=checked), \
             self.assertRaisesRegex(ValueError,'OLD_FACT_CREDIT_RESTORED'):
            interpret.validate_complete_interpretation(prepared_input=prepared,
                response_bytes_by_request={'effective':b'constructed'},source_root=data)
