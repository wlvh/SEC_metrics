"""Source-root/marked-mode routing, not semantic answers or execution credit."""
from pathlib import Path
import unittest
from unittest.mock import patch
from vnext import regulatory_fact_review as review
from vnext.normal_source_authority import ROOT

class D03SourceRootSeamTest(unittest.TestCase):
    def test_registered_source_rebuild_retains_actual_root_and_mode(self):
        source={'company_id':'constructed','request_context_format':'fixture','external_replay_only':True}
        original={'request_id':'constructed'};data=Path('/external-saved-source')
        def rebuild(**kwargs):
            if kwargs.get('ordinary_registered') is True:return source
            return {k:v for k,v in source.items() if k!='external_replay_only'}
        with patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',side_effect=rebuild) as prepare, \
             patch('vnext.continuous_semantic_calls.source_requests',return_value=[original]):
            review._authenticated_original(original=original,source=source,repo_root=data)
        prepare.assert_called_once_with(repo_root=data,company_id='constructed',request_context_format='fixture',ordinary_registered=True)

    def test_legacy_unmarked_rebuild_keeps_the_original_default_call(self):
        source={'company_id':'constructed','request_context_format':'fixture'};original={'request_id':'constructed'}
        with patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=source) as prepare, \
             patch('vnext.continuous_semantic_calls.source_requests',return_value=[original]):
            review._authenticated_original(original=original,source=source,repo_root=ROOT)
        prepare.assert_called_once_with(repo_root=ROOT,company_id='constructed',request_context_format='fixture')

    def test_changed_source_or_original_request_still_fails(self):
        source={'company_id':'constructed','external_replay_only':True};original={'request_id':'constructed'}
        for rebuilt,requests in (({**source,'changed':True},[original]),(source,[{'request_id':'another'}])):
            with self.subTest(rebuilt=rebuilt),patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=rebuilt), \
                 patch('vnext.continuous_semantic_calls.source_requests',return_value=requests), \
                 self.assertRaisesRegex(ValueError,'AUTHENTIC_ORIGINAL_REQUIRED'):
                review._authenticated_original(original=original,source=source,repo_root=ROOT)

    def test_a_nonboolean_source_mode_is_not_reinterpreted(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_MODE_INVALID'):
            review._authenticated_original(original={},source={'company_id':'constructed','external_replay_only':1},repo_root=ROOT)

    def test_actual_successor_dispatch_passes_the_prepared_source_root(self):
        import tempfile
        from vnext import continuous_semantic_calls as calls
        from vnext.continuous_call_ledger import recorded_ledger
        from vnext.current_request_configuration import load_current_configuration
        from vnext.canonical import strict_json_loads
        class AtSourceBoundary(Exception):pass
        with tempfile.TemporaryDirectory() as folder:
            ledger=recorded_ledger(root=Path(folder).resolve()/'recorded')
            data=ledger.root/'source-inputs'
            source={'metric_id':'D03','required_unit_ids':['unit'],'semantic_source_id':'constructed'}
            request={'source_statement_facts':[{'constructed_routing_only':True}],
                'units':[{'unit_id':'unit'}],'required_candidate_assessments':[]}
            prepared=calls.SemanticRequest(calls._FACTORY,calls._source_json(source),calls._source_json(request),
                b'',b'',load_current_configuration(repo_root=ROOT),{},data_root=data,source_ledger=ledger)
            def reach(original,**kwargs):
                self.assertEqual(kwargs['repo_root'],data)
                self.assertEqual(original,request)
                self.assertEqual(kwargs['source'],source)
                raise AtSourceBoundary()
            with patch.object(calls,'prepare_requests',return_value=[prepared]), \
                 patch.object(review,'candidate_request',side_effect=reach), \
                 self.assertRaises(AtSourceBoundary):
                calls.prepare_d03_replay_only_requests(company_id='constructed',source_root=data,source_ledger=ledger)

    def test_rebuilt_external_requests_still_cannot_claim_or_reach_transport(self):
        import tempfile
        from dataclasses import replace
        from vnext import continuous_semantic_calls as calls,ai_adapter
        from vnext.continuous_call_ledger import recorded_ledger
        with tempfile.TemporaryDirectory() as folder:
            ledger=recorded_ledger(root=Path(folder).resolve()/'recorded')
            request={'metric_id':'D03','external_replay_only':True,
                     'source_fact_review_contract':{'constructed_gate_only':True}}
            source={'metric_id':'D03','external_replay_only':True}
            prepared=calls.SemanticRequest(calls._FACTORY,calls._source_json(source),calls._source_json(request),
                b'',b'',{}, {},data_root=ledger.root/'source-inputs',source_ledger=ledger,replay_only=True)
            for candidate in (prepared,replace(prepared,replay_only=False)):
                with self.subTest(replay=candidate.replay_only), \
                     patch.object(ledger,'claim',side_effect=AssertionError('Claim forbidden')) as claim, \
                     patch.object(ai_adapter,'_open_provider_request',side_effect=AssertionError('Network forbidden')) as transport, \
                     self.assertRaisesRegex(ValueError,'D03_EXTERNAL_REPLAY_EXECUTION_NOT_AUTHORIZED'):
                    calls.execute_feasibility(prepared=candidate,ledger=ledger)
                claim.assert_not_called();transport.assert_not_called()
