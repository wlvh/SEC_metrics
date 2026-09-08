"""Ordinary B10 integration: simulated GitHub/HTTP, real authorization and Run.

These tests require a clean committed checkout because code identity is part
of production authorization. No validator, Reader or controller is mocked.
HTTP responses are test returns for the exact saved FY2025 request, not new
model-understanding evidence. Native LIVE-shaped counters here are simulated.
"""
import copy
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from vnext import ai_adapter, annual_candidate as candidate, qualification, workflow
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.run_store import load_open_run
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile_v1 import _live_call_bound, RequirementProfileError
from tests.vnext.test_annual_input import historical_response, HISTORICAL_RUN

REPO_ROOT = Path(__file__).resolve().parents[2]
UTC = '2026-09-08T06:00:00Z'


def approval_api(plan):
    """Simulated external GitHub responses, explicitly not saved owner grants."""
    repository = 'wlvh/SEC_metrics'
    def comment(number, body):
        return {'id':number,'html_url':f'https://github.com/{repository}/pull/999#issuecomment-{number}',
            'issue_url':f'https://api.github.com/repos/{repository}/issues/999',
            'user':{'login':'wlvh'},'created_at':UTC,'updated_at':UTC,
            'body':json.dumps(body)}
    responses = {
        f'repos/{repository}/issues/comments/991':comment(991,candidate.expected_activation_approval(plan)),
        f'repos/{repository}/issues/comments/992':comment(992,candidate.expected_owner_approval(plan)),
        f'repos/{repository}/pulls/999':{'number':999,'state':'open','merged':False,
            'head':{'sha':plan['code_identity']['exact_head'],'repo':{'full_name':repository}},'base':{'ref':'main'}},
    }
    return responses


def authorize(plan, responses=None):
    with mock.patch.object(candidate,'_github',side_effect=lambda path:copy.deepcopy((responses or approval_api(plan))[path])):
        return candidate.verify_candidate_authorization(plan=plan,
            activation_url='https://github.com/wlvh/SEC_metrics/pull/999#issuecomment-991',
            owner_url='https://github.com/wlvh/SEC_metrics/pull/999#issuecomment-992')


@contextmanager
def provider_boundary(plan, *, usage='valid', failure=None, bad_content=False):
    original, response = historical_response()
    reader = (HISTORICAL_RUN / original['reader_payload_path']).read_bytes()
    policy = ai_adapter.approved_transport_policy(requirement=load_requirement_snapshot(
        snapshot_dir=REPO_ROOT/'requirements/issue_15_v1'))
    expected, _ = ai_adapter.build_provider_request_body(policy=policy, reader_request_bytes=reader)
    assert sha256_bytes(content=expected) == plan['request']['provider_request_body_sha256']
    output = '{}' if bad_content else response.decode()
    envelope = {'id':'mock-http-ordinary-b10','model':policy.model,
        'choices':[{'message':{'role':'assistant','content':output},'finish_reason':'stop'}]}
    if usage == 'valid':
        envelope['usage']={'prompt_tokens':160000,'completion_tokens':500,'total_tokens':160500}
    elif usage == 'excess':
        envelope['usage']={'prompt_tokens':200001,'completion_tokens':500,'total_tokens':200501}
    elif usage == 'inconsistent':
        envelope['usage']={'prompt_tokens':160000,'completion_tokens':500,'total_tokens':160501}
    raw = canonical_json_bytes(value=envelope)
    def http(*, fullurl, timeout):
        assert fullurl.data == expected, 'Mock response cannot be rebound to another request'
        if failure == '429':
            raise HTTPError(fullurl.full_url,429,'test retryable response',{},io.BytesIO(b'{"error":"test-only"}'))
        if failure == 'unknown':
            raise OSError('test-only connection lost after egress')
        result = io.BytesIO(raw);result.headers={'x-request-id':'mock-http-ordinary-b10'}
        return result
    with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')), \
         mock.patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-only-not-a-secret'}), \
         mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=http) as opened:
        yield opened


class AnnualCandidateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='b10-offline-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.network = mock.patch.object(socket.socket,'connect',side_effect=AssertionError('REAL_NETWORK_FORBIDDEN'))
        self.network.start();self.addCleanup(self.network.stop)

    def plan(self, name='candidate', year=None):
        return candidate.prepare_candidate_plan(output_root=self.root/name, fiscal_year=year)

    def test_source_years_are_plan_data_and_current_request_is_complete(self):
        current, previous = self.plan(), self.plan('prior',2024)
        self.assertEqual(68,current['request']['table_count'])
        self.assertEqual(67,previous['request']['table_count'])
        self.assertEqual(2025,current['prepared_input']['table_input']['target_period']['fiscal_year'])
        self.assertEqual(2024,previous['prepared_input']['table_input']['target_period']['fiscal_year'])
        self.assertNotEqual(current['prepared_input']['input_id'],previous['prepared_input']['input_id'])
        self.assertNotEqual(current['request']['provider_request_body_sha256'],previous['request']['provider_request_body_sha256'])
        self.assertGreater(current['request']['estimated_context_tokens'],200000)
        self.assertEqual(current['request']['provider_request_bytes'],current['request']['estimated_context_tokens'])
        self.assertEqual('NOT_ACTIVATED',candidate._requirement()['activation_state'])
        self.assertFalse(candidate.execution_paths(current)[0].exists())

    def test_success_native_chain_and_new_process_reentry(self):
        plan=self.plan();authority=authorize(plan)
        watched=[REPO_ROOT/'outputs/active_publication.json',REPO_ROOT/'outputs/metrics_matrix.csv',REPO_ROOT/'evidence/requests_log.csv']
        before=[p.read_bytes() for p in watched]
        with provider_boundary(plan) as opened:
            candidate.execute_candidate(plan=plan,authorization=authority)
            candidate.execute_candidate(plan=plan,authorization=authorize(plan))
            self.assertEqual(1,opened.call_count)
        _,run_dir,_=candidate.execution_paths(plan)
        manifest,records,decisions=load_open_run(run_dir=run_dir)
        self.assertEqual('SUCCESSOR_RUN',manifest['record_type'])
        self.assertEqual('issue_28_v4',manifest['requirement_id'])
        self.assertNotIn('qualification_authorization',manifest)
        result=next(r for r in records if r['record_type']=='METRIC_RESULT')
        self.assertEqual(('B10','0.693','ratio','2025-01-01','2025-12-31'),tuple(result[k] for k in
            ('metric_id','value','unit','period_start','period_end')))
        self.assertEqual('SYSTEM',decisions[0]['reviewer_type'])
        attempt=next(r for r in records if r['record_type']=='AI_EXTRACTION_ATTEMPT')
        self.assertEqual('SUCCEEDED',attempt['status'])
        for field in ('raw_response_path','assistant_output_path','request_body_path'):
            self.assertTrue((run_dir/attempt[field]).is_file())
        self.assertTrue(any(r['record_type']=='EVIDENCE_CHECK' and r['status']=='PASS' for r in records))
        plan_file=self.root/'plan.json';plan_file.write_text(json.dumps(plan))
        code='''import sys,json,socket
from pathlib import Path
from unittest import mock
from tests.vnext.test_annual_candidate import authorize
from vnext import annual_candidate as c, ai_adapter
p=json.loads(Path(sys.argv[1]).read_text())
with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('network')), mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=AssertionError('second HTTP request')):
    assert c.execute_candidate(plan=p,authorization=authorize(p))['status']=='SAVED_RUN_ONLY'
print('NEW_PROCESS_ZERO_HTTP')
'''
        checked=subprocess.run([sys.executable,'-c',code,str(plan_file)],cwd=REPO_ROOT,env={**os.environ,
            'PYTHONPATH':str(REPO_ROOT/'scripts'),'PYTHONDONTWRITEBYTECODE':'1'},text=True,capture_output=True)
        self.assertEqual(0,checked.returncode,checked.stdout+checked.stderr)
        self.assertIn('NEW_PROCESS_ZERO_HTTP',checked.stdout)
        self.assertEqual(before,[p.read_bytes() for p in watched])
        # Missing original controller evidence cannot be replaced by native response files alone.
        executions=next((candidate.execution_paths(plan)[0]/'invocation_control/executions').glob('*.json'))
        saved=executions.read_bytes();executions.unlink()
        try:
            with self.assertRaises((ValueError,OSError)):
                candidate.validate_run_binding(repo_root=REPO_ROOT,run_dir=run_dir,manifest=manifest,records=records)
        finally:
            executions.write_bytes(saved)

    def test_bad_approval_and_plan_identity_fail_before_provider(self):
        plan=self.plan()
        with mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=AssertionError('HTTP before authorization')):
            with self.assertRaisesRegex(ValueError,'AUTHORIZATION_REQUIRED'):
                ai_adapter.build_annual_candidate_transport_adapter(authorization={})
            for field,value in (('user',{'login':'not-owner'}),('body','{}'),('updated_at','2026-09-08T06:00:01Z')):
                api=approval_api(plan);api['repos/wlvh/SEC_metrics/issues/comments/992'][field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):authorize(plan,api)
            for field in ('request','task_contract_id','code_identity','prepared_input','output_root'):
                wrong=copy.deepcopy(plan)
                if field=='request':wrong[field]['provider_request_body_sha256']='0'*64
                elif field=='code_identity':wrong[field]['exact_head']='0'*40
                elif field=='prepared_input':wrong[field]['table_input']['target_period']['fiscal_year']=2024
                elif field=='output_root':wrong[field]=str(self.root/'changed-output')
                else:wrong[field]='lodging_revpar_table_v2'
                wrong['plan_id']=content_hash(value={k:v for k,v in wrong.items() if k!='plan_id'})
                with self.subTest(field=field),self.assertRaises(ValueError):
                    # Even a caller-rehashed plan with correct-looking source fields is not authorized.
                    authorize(wrong,approval_api(plan))

    def test_wrong_workflow_bindings_and_qualification_misuse(self):
        plan=self.plan();authority=authorize(plan)
        adapter=ai_adapter.build_annual_candidate_transport_adapter(authorization=authority)
        _,run_dir,run_id=candidate.execution_paths(plan)
        arguments=dict(repo_root=REPO_ROOT,run_dir=run_dir,run_id=run_id,task_contract_id=plan['task_contract_id'],
            adapter=adapter,clock=None,candidate_authorization=authority,**plan['prepared_input']['table_input'])
        for field,value in (('company_id','wrong-company'),('run_id','run:other'),('run_dir',self.root/'other'),
            ('accession','wrong-accession'),('request_attempt_id','request:wrong'),('source_url','https://www.sec.gov/wrong'),
            ('target_period',{'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}),
            ('task_contract_id','lodging_revpar_table_v2'),('candidate_authorization',None)):
            with self.subTest(field=field),self.assertRaises((ValueError,RuntimeError)):
                workflow.create_table_task_review_run(**{**arguments,field:value})
        self.assertFalse(run_dir.exists())
        old=json.loads((HISTORICAL_RUN/'manifest.json').read_text())['qualification_authorization']
        opaque=qualification.TableQualificationAuthorization(binding=old,capability=qualification._QUALIFICATION_AUTHORIZATION_CAPABILITY)
        with self.assertRaisesRegex(ValueError,'AUTHORIZATION_REQUIRED'):
            ai_adapter.build_annual_candidate_transport_adapter(authorization=opaque)
        normal=ai_adapter.build_invocation_controlled_transport_adapter(release_input_plan_id=plan['plan_id'],
            workspace_dir=self.root/'ordinary-generic',owner_token='test-only')
        with self.assertRaisesRegex(RuntimeError,'TABLE_QUALIFICATION_AUTHORIZATION_REQUIRED'):
            workflow.create_table_task_review_run(**{**arguments,'candidate_authorization':None,'adapter':normal})
        # The historical typed bound and closed qualification API retain their meaning.
        current=load_requirement_snapshot(snapshot_dir=REPO_ROOT/'requirements/issue_28_v3')
        bound=next(d['choice'] for d in current['effective_decisions'].values() if d.get('choice',{}).get('kind')=='LIVE_CALL_BOUND')
        with self.assertRaises(RequirementProfileError):
            _live_call_bound(choice={**bound,'target_minimum_provider_calls':1,'target_maximum_provider_calls':1,'hard_maximum_provider_calls':1})

    def test_usage_content_retryable_and_unknown_stop_after_one_http(self):
        for case in ('missing','excess','inconsistent','bad-content','429','unknown'):
            with self.subTest(case=case):
                plan=self.plan(case);authority=authorize(plan)
                with provider_boundary(plan,usage=case if case in ('missing','excess','inconsistent') else 'valid',
                    failure=case if case in ('429','unknown') else None,bad_content=case=='bad-content') as opened:
                    candidate.execute_candidate(plan=plan,authorization=authority)
                    candidate.execute_candidate(plan=plan,authorization=authorize(plan))
                    self.assertEqual(1,opened.call_count)
                workspace,run_dir,_=candidate.execution_paths(plan)
                manifest,records,decisions=load_open_run(run_dir=run_dir)
                attempt=next(r for r in records if r['record_type']=='AI_EXTRACTION_ATTEMPT')
                self.assertEqual('FAILED',attempt['status'])
                self.assertFalse(decisions)
                self.assertFalse(any(r['record_type']=='METRIC_RESULT' for r in records))
                self.assertEqual(1,len(list((workspace/'invocation_control/egress').rglob('*.json'))))
                receipt=json.loads(next((workspace/'invocation_control/executions').glob('*.json')).read_text())
                self.assertEqual('UNKNOWN_REMOTE_OUTCOME' if case=='unknown' else
                    'FAILED_RETRYABLE_FINAL' if case=='429' else 'FAILED_TERMINAL',receipt['status'])
                if case in ('missing','excess','inconsistent'):self.assertEqual('CONTEXT_LIMIT',attempt['error_class'])


if __name__=='__main__':unittest.main()
