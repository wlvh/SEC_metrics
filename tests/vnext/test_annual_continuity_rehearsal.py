"""Complete historical sources; only GitHub and HTTP I/O are simulated.

Run with CONTINUITY_REHEARSAL_ROOT (new external directory) and
CONTINUITY_MATERIAL_AUDIT (the independently inspected original Run index).
These tests execute native validators and publication transactions. They do not
claim a fresh provider execution, real Owner approval, or production publication.
"""
import copy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import socket
import unittest
from unittest import mock

from vnext import annual_continuity as flow, annual_publication as annual, publication as pub
from vnext import annual_candidate, ai_adapter
from vnext.canonical import sha256_bytes

URL='https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-9999041'


def saved(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


class AnnualContinuityRehearsalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=os.environ.get('CONTINUITY_REHEARSAL_ROOT');audit=os.environ.get('CONTINUITY_MATERIAL_AUDIT')
        if not root or not audit:
            raise unittest.SkipTest('Requires saved complete historical materials and a new isolated root')
        cls.root=Path(root).resolve();cls.audit=json.loads(Path(audit).read_text())
        if cls.root.exists():raise ValueError('Rehearsal root already exists; preserve it and use a fresh offline test root')
        cls.root.mkdir(parents=True)
        cls.initial=(flow.ROOT/'outputs/active_publication.json').read_bytes()
        cls.log=[]

    def test_two_complete_updates_and_reentry(self):
        root=self.root
        flow.initialize_data(data_root=root/'data')
        code=flow.code_identity()
        review={'reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','conclusion':'NO_BLOCKING_FINDINGS',
            'reviewed_head':code['exact_head'],'runtime_tree':code['runtime_tree'],
            'evidence_scope':'SIMULATED_TEST_BOUNDARY_NOT_REAL_REVIEW'}
        saved(root/'review.json',review)
        visibility=root/'visibility.json'
        saved(visibility,{'record_type':'SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY','as_of_utc':'2025-12-31T23:59:59Z'})
        stage=flow.stage_proposal(stage_root=root/'stage',data_root=root/'data',budget_root=root/'budget',
            review_file=root/'review.json',seed_b01=self.audit['s0_feasibility']['B01']['run_directory'],
            seed_b10=self.audit['s0_feasibility']['B10']['run_directory'],visibility_file=visibility,
            expires_at_utc=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
            historical_period_start='2023-01-01',historical_period_end='2025-12-31')
        timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        comment={'id':9999041,'html_url':URL,'issue_url':'https://api.github.com/repos/wlvh/SEC_metrics/issues/28',
            'user':{'login':'wlvh'},'body':json.dumps(stage),'created_at':timestamp,'updated_at':timestamp}
        saved(root/'simulated-comment.json',comment)
        # Exact request bytes must match a saved original full-document request.
        envelopes={}
        for item in self.audit['existing_real_provider_B10_runs']:
            run=Path(item['run_directory'])
            records=[json.loads(x) for x in (run/'records.jsonl').read_text().splitlines()]
            attempt=next(x for x in records if x['record_type']=='AI_EXTRACTION_ATTEMPT')
            expected=(run/attempt['request_body_path']).read_bytes()
            envelopes[sha256_bytes(content=expected)]=(expected,(run/attempt['raw_response_path']).read_bytes())
        requests=[]
        def github(path):
            self.assertEqual('repos/wlvh/SEC_metrics/issues/comments/9999041',path)
            return copy.deepcopy(comment)
        def http(*,fullurl,timeout):
            identity=sha256_bytes(content=fullurl.data)
            self.assertIn(identity,envelopes,'Request does not match the immutable historical response fixture')
            expected,raw=envelopes[identity];self.assertEqual(expected,fullurl.data)
            requests.append(identity)
            response=io.BytesIO(raw);response.headers={'x-request-id':'SIMULATED_HTTP_REPLAY'}
            return response
        with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')), \
             mock.patch.object(annual_candidate,'_github',side_effect=github), \
             mock.patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-only-not-a-secret'}), \
             mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=http):
            first=flow.run_once(approval_url=URL);saved(root/'first.json',first)
            self.assertEqual('COMPLETE_UPDATE_COMMITTED',first['status'],first)
            first_view=pub.PublicationView.open(publication_root=Path(stage['publication_root']))
            s1=first_view.publication_id;s0=first_view.manifest['previous_publication_id']
            self.assertEqual(s1,first['current_published']['provenance']['publication_id'])
            self.assertEqual(s0,first['published_before']['provenance']['publication_id'])
            for metric in ('B01','B10'):
                self.assertEqual('2024-12-31',first_view.native_result(company_id=stage['policy']['company_id'],metric_id=metric)['result']['period_end'])
            repeated=flow.run_once(approval_url=URL);saved(root/'repeat-first.json',repeated)
            self.assertEqual('NO_CHANGE',repeated['status']);self.assertEqual(1,len(requests))
            saved(visibility,{'record_type':'SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY','as_of_utc':'2026-09-01T00:00:00Z'})
            second=flow.run_once(approval_url=URL);saved(root/'second.json',second)
            self.assertEqual('COMPLETE_UPDATE_COMMITTED',second['status'],second)
            second_view=pub.PublicationView.open(publication_root=Path(stage['publication_root']))
            self.assertEqual(s1,second_view.manifest['previous_publication_id'])
            self.assertEqual(second_view.publication_id,second['current_published']['provenance']['publication_id'])
            for metric in ('B01','B10'):
                self.assertEqual('2025-12-31',second_view.native_result(company_id=stage['policy']['company_id'],metric_id=metric)['result']['period_end'])
            complete=json.loads(second_view.read_bytes(relative_path=annual.BATCH))
            self.assertEqual((240,2,238),(len(complete['cumulative_result_bindings']),complete['selected_result_count'],complete['inherited_result_count']))
            repeated=flow.run_once(approval_url=URL);saved(root/'repeat-second.json',repeated)
            self.assertEqual('NO_CHANGE',repeated['status']);self.assertEqual(2,len(requests))
            self.assertEqual(2,len(set(requests)))
        self.assertEqual(self.initial,(flow.ROOT/'outputs/active_publication.json').read_bytes())
        saved(root/'binding.json',{'status':'PASSED_OFFLINE_HTTP_REPLAY_NOT_FRESH_PROVIDER','code':code,'stage_id':stage['stage_id'],
            's0':s0,'s1':s1,'s2':second_view.publication_id,'request_hashes':requests,
            'actual_new_provider_paid_sec_calls':[0,0,0],'simulated_native_controller_calls':flow.budget_counts(stage)})

    def test_lost_reference_recovery_and_partial_failure(self):
        root=self.root/'failure-case'
        flow.initialize_data(data_root=root/'data')
        code=flow.code_identity()
        review={'reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','conclusion':'NO_BLOCKING_FINDINGS',
            'reviewed_head':code['exact_head'],'runtime_tree':code['runtime_tree'],
            'evidence_scope':'SIMULATED_TEST_BOUNDARY_NOT_REAL_REVIEW'}
        saved(root/'review.json',review)
        visibility=root/'visibility.json'
        saved(visibility,{'record_type':'SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY','as_of_utc':'2025-12-31T23:59:59Z'})
        stage=flow.stage_proposal(stage_root=root/'stage',data_root=root/'data',budget_root=root/'budget',
            review_file=root/'review.json',seed_b01=self.audit['s0_feasibility']['B01']['run_directory'],
            seed_b10=self.audit['s0_feasibility']['B10']['run_directory'],visibility_file=visibility,
            expires_at_utc=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
            historical_period_start='2023-01-01',historical_period_end='2025-12-31')
        timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        comment={'id':9999041,'html_url':URL,'issue_url':'https://api.github.com/repos/wlvh/SEC_metrics/issues/28',
            'user':{'login':'wlvh'},'body':json.dumps(stage),'created_at':timestamp,'updated_at':timestamp}
        saved(root/'simulated-comment.json',comment)
        # Exact request bytes must match a saved original full-document request.
        envelopes={}
        for item in self.audit['existing_real_provider_B10_runs']:
            run=Path(item['run_directory'])
            records=[json.loads(x) for x in (run/'records.jsonl').read_text().splitlines()]
            attempt=next(x for x in records if x['record_type']=='AI_EXTRACTION_ATTEMPT')
            expected=(run/attempt['request_body_path']).read_bytes()
            envelopes[sha256_bytes(content=expected)]=(expected,(run/attempt['raw_response_path']).read_bytes())
        requests=[];bad={'enabled':False}
        def github(path):
            self.assertEqual('repos/wlvh/SEC_metrics/issues/comments/9999041',path)
            return copy.deepcopy(comment)
        def http(*,fullurl,timeout):
            identity=sha256_bytes(content=fullurl.data)
            self.assertIn(identity,envelopes,'Request does not match the immutable historical response fixture')
            expected,raw=envelopes[identity];self.assertEqual(expected,fullurl.data)
            requests.append(identity)
            if bad['enabled']:
                from vnext.canonical import canonical_json_bytes
                malformed=json.loads(raw);malformed['choices'][0]['message']['content']='{}'
                raw=canonical_json_bytes(value=malformed)
            response=io.BytesIO(raw);response.headers={'x-request-id':'SIMULATED_HTTP_REPLAY'}
            return response
        from vnext import canonical
        original_replace=os.replace
        def lost_reference(src,dst,*args,**kwargs):
            if Path(dst)==Path(stage['stage_root'])/'successful-candidate.json':
                raise OSError('SIMULATED_LOST_SUCCESS_REFERENCE')
            return original_replace(src,dst,*args,**kwargs)
        class HardCrash(BaseException):pass
        def crash_after_pointer(*,fault_point):
            if fault_point=='POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT':raise HardCrash(fault_point)
        with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')), \
             mock.patch.object(annual_candidate,'_github',side_effect=github), \
             mock.patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-only-not-a-secret'}), \
             mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=http):
            with mock.patch.object(os,'replace',side_effect=lost_reference):
                with self.assertRaisesRegex(OSError,'LOST_SUCCESS_REFERENCE'):flow.run_once(approval_url=URL)
            self.assertEqual(1,len(requests))
            self.assertFalse((Path(stage['stage_root'])/'successful-candidate.json').exists())
            old=pub.PublicationView.open(publication_root=Path(stage['publication_root'])).publication_id
            with mock.patch.object(pub,'_fault_injection_checkpoint',side_effect=crash_after_pointer):
                with self.assertRaises(HardCrash):flow.run_once(approval_url=URL)
            self.assertEqual(1,len(requests))
            with self.assertRaises(pub.PublicationError):pub.PublicationView.open(publication_root=Path(stage['publication_root']))
            recovered=flow.run_once(approval_url=URL);saved(root/'recovery.json',recovered)
            self.assertEqual('RECOVERED_PRIOR_TRANSACTION',recovered['status'])
            current=pub.PublicationView.open(publication_root=Path(stage['publication_root']))
            self.assertNotEqual(old,current.publication_id)
            first_reference=(Path(stage['stage_root'])/'successful-candidate.json').read_bytes()
            pointer=(Path(stage['publication_root'])/'outputs/active_publication.json').read_bytes()
            bad['enabled']=True
            saved(visibility,{'record_type':'SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY','as_of_utc':'2026-09-01T00:00:00Z'})
            failed=flow.run_once(approval_url=URL);saved(root/'failure.json',failed)
            self.assertEqual('CANDIDATE_UPDATE_FAILED',failed['status'],failed)
            self.assertEqual('PASS',failed['structured_candidate']['B01']['reason_code'])
            self.assertEqual(2,len(requests))
            self.assertEqual(pointer,(Path(stage['publication_root'])/'outputs/active_publication.json').read_bytes())
            self.assertEqual(first_reference,(Path(stage['stage_root'])/'successful-candidate.json').read_bytes())
            with self.assertRaisesRegex(ValueError,'FAILED_INPUT_REQUIRES'):flow.run_once(approval_url=URL)
            self.assertEqual(2,len(requests))
            # The summary flag cannot turn the original failed native terminal into success.
            failures=flow.budget_counts(stage)['failed_plans'];self.assertEqual(1,len(failures))
            path=Path(stage['stage_root'])/'candidates'/failures[0][7:]/'outcome.json'
            original=path.read_bytes()
            try:
                tampered=json.loads(original);tampered['status']='CANDIDATE_UPDATE_SUCCEEDED';saved(path,tampered)
                self.assertEqual(failures,flow.budget_counts(stage)['failed_plans'])
            finally:path.write_bytes(original)
        saved(root/'negative-binding.json',{'status':'PASSED_NATIVE_FAILURE_AND_RECOVERY_OFFLINE_IO',
            'code':code,'stage_id':stage['stage_id'],'old_publication':old,'recovered_publication':current.publication_id,
            'actual_new_provider_paid_sec_calls':[0,0,0],'simulated_native_counts':flow.budget_counts(stage)})
        self.assertEqual(self.initial,(flow.ROOT/'outputs/active_publication.json').read_bytes())

    def test_current_active_start_without_historical_parameters(self):
        root=self.root/'current-start';flow.initialize_data(data_root=root/'data');code=flow.code_identity()
        saved(root/'review.json',{'reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','conclusion':'NO_BLOCKING_FINDINGS',
            'reviewed_head':code['exact_head'],'runtime_tree':code['runtime_tree'],
            'evidence_scope':'SIMULATED_TEST_BOUNDARY_NOT_REAL_REVIEW'})
        stage=flow.stage_proposal(stage_root=root/'stage',data_root=root/'data',budget_root=root/'budget',review_file=root/'review.json',
            expires_at_utc=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
            historical_period_start='2023-01-01',historical_period_end='2025-12-31')
        self.assertIsNone(stage['seed']);self.assertIsNone(stage['visibility_file'])
        timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        comment={'id':9999041,'html_url':URL,'issue_url':'https://api.github.com/repos/wlvh/SEC_metrics/issues/28',
            'user':{'login':'wlvh'},'body':json.dumps(stage),'created_at':timestamp,'updated_at':timestamp}
        with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')), \
             mock.patch.object(annual_candidate,'_github',return_value=comment), \
             mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=AssertionError('NO_NEW_PROVIDER')):
            result=flow.run_once(approval_url=URL);saved(root/'result.json',result)
            self.assertEqual('NO_CHANGE',result['status']);self.assertEqual('CURRENT_ACTIVE',result['start_mode'])
            self.assertEqual(0,result['counts']['provider_reserved'])
            self.assertEqual(stage['initial_publication_pointer']['publication_id'],result['current_published']['provenance']['publication_id'])
            self.assertFalse((Path(stage['stage_root'])/'seed-candidate').exists())
            self.assertFalse((Path(stage['stage_root'])/'seed-publication-result.json').exists())
        self.assertEqual(self.initial,(flow.ROOT/'outputs/active_publication.json').read_bytes())

if __name__=='__main__':unittest.main()
