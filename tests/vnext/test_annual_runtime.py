"""New runtime integration: mock only GitHub and provider HTTP, never validators.

Review/owner responses below are explicitly SIMULATED_TEST_BOUNDARY. All real
network is disabled. Native LIVE-shaped records are not real provider evidence.
"""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from vnext import annual_runtime as runtime, annual_update as update
from vnext.canonical import sha256_bytes
from tests.vnext.test_annual_update import OLD_RUN
from tests.vnext.test_annual_candidate import provider_boundary

ROOT=Path(__file__).resolve().parents[2]
URL='https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-999901'


def simulated_comment(stage):
    return {'id':999901,'html_url':URL,'issue_url':'https://api.github.com/repos/wlvh/SEC_metrics/issues/28',
        'user':{'login':'wlvh'},'created_at':'2026-09-08T16:20:00Z','updated_at':'2026-09-08T16:20:00Z',
        'body':json.dumps(stage)}


class AnnualRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='annual-runtime-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        blocker=mock.patch.object(socket.socket,'connect',side_effect=AssertionError('REAL_NETWORK_FORBIDDEN'))
        blocker.start(); self.addCleanup(blocker.stop)
        self.data=self.root/'data'
        runtime.initialize_data_root(data_root=self.data)
        identity=runtime.code_identity()
        review={'reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','conclusion':'NO_BLOCKING_FINDINGS',
                'reviewed_head':identity['exact_head'],'runtime_tree':identity['runtime_tree'],
                'evidence_scope':'SIMULATED_TEST_BOUNDARY_NOT_REAL_REVIEW'}
        self.review=self.root/'review.json';self.review.write_text(json.dumps(review))
        self.stage=runtime.stage_proposal(stage_root=self.root/'stage',data_root=self.data,
                                         baseline_run=OLD_RUN,review_path=self.review)
        self.comment=simulated_comment(self.stage)
        def api(path):
            self.assertEqual('repos/wlvh/SEC_metrics/issues/comments/999901',path,'Runtime must not query PR state')
            return copy.deepcopy(self.comment)
        self.api=mock.patch.object(runtime,'_github',side_effect=api)
        self.api.start();self.addCleanup(self.api.stop)

    def plan(self):
        return runtime.prepare_plan(binding=runtime.verify_stage(approval_url=URL))

    def test_complete_runtime_and_same_input_new_process_no_pr(self):
        watched=[ROOT/'outputs/active_publication.json',ROOT/'outputs/metrics_matrix.csv',ROOT/'evidence/requests_log.csv',OLD_RUN/'records.jsonl']
        before=[p.read_bytes() for p in watched]
        plan=self.plan()
        with provider_boundary(plan) as opened:
            result=runtime.run_update(approval_url=URL)
            self.assertEqual('CANDIDATE_UPDATE_SUCCEEDED',result['status'],result)
            again=runtime.run_update(approval_url=URL)
            self.assertEqual('NO_NEW_ANNUAL_FILING',again['status'],again)
            self.assertEqual(1,opened.call_count)
        self.assertEqual([1,1,0],result['stage_provider_paid_sec_calls'])
        self.assertEqual([0,0,0],again['provider_paid_sec_calls'])
        self.assertEqual('26186000000',result['structured_candidate']['B01']['value'])
        self.assertEqual('2024-12-31',result['old_successful_candidate']['filing']['period_end'])
        self.assertEqual('2025-12-31',result['current_published']['filing']['period_end'])
        self.assertEqual('0.693',result['new_candidate']['results'][0]['value'])
        self.assertEqual('ISOLATED_HISTORICAL_START_NOT_PRODUCTION',result['baseline_mode'])
        self.assertEqual(before,[p.read_bytes() for p in watched])
        capture=self.root/'comment.json';capture.write_text(json.dumps(self.comment))
        code='''import json,socket,sys
from pathlib import Path
from unittest import mock
from vnext import annual_runtime as r,ai_adapter
c=json.loads(Path(sys.argv[1]).read_text())
with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('network')),mock.patch.object(r,'_github',return_value=c),mock.patch.object(ai_adapter._DEEPSEEK_OPENER,'open',side_effect=AssertionError('second provider')):
 x=r.run_update(approval_url=c['html_url']);assert x['status']=='NO_NEW_ANNUAL_FILING',x
print('NEW_PROCESS_ZERO_HTTP')
'''
        done=subprocess.run([sys.executable,'-c',code,str(capture)],cwd=ROOT,text=True,capture_output=True,
            env={**os.environ,'PYTHONPATH':str(ROOT/'scripts'),'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(0,done.returncode,done.stdout+done.stderr)

    def test_failure_retains_old_success_and_consumes_stage(self):
        plan=self.plan()
        with provider_boundary(plan,usage='excess') as opened:
            failed=runtime.run_update(approval_url=URL)
            self.assertEqual('CANDIDATE_UPDATE_FAILED',failed['status'],failed)
            stopped=runtime.run_update(approval_url=URL)
            self.assertEqual('STAGE_STOPPED',stopped['status'],stopped)
            self.assertEqual(1,opened.call_count)
        self.assertFalse((Path(self.stage['stage_root'])/'successful-candidate.json').exists())
        self.assertEqual('2024-12-31',failed['old_successful_candidate']['filing']['period_end'])
        self.assertEqual([1,1,0],stopped['stage_provider_paid_sec_calls'])

    def test_authority_input_and_owner_tamper_fail_before_provider(self):
        plan=self.plan()
        path=self.data/'catalog/table_task_contracts.json'; original=path.read_bytes()
        path.write_bytes(original+b'\n')
        with self.assertRaisesRegex(ValueError,'AUTHORITY_BYTES_CHANGED'):
            runtime.verify_stage(approval_url=URL)
        path.write_bytes(original)
        source=self.data/plan['prepared_input']['source_proofs'][1]['request_repo_relative_path']
        original=source.read_bytes();source.write_bytes(original+b'\n')
        with self.assertRaises(ValueError):self.plan()
        source.write_bytes(original)
        self.comment['user']['login']='not-owner'
        with self.assertRaisesRegex(ValueError,'OWNER_PROVENANCE'):runtime.verify_stage(approval_url=URL)
        with self.assertRaisesRegex(ValueError,'AUTHORIZATION_REQUIRED'):runtime.authorization_fields({})

    def test_stage_slot_is_global_to_input_plan_and_restart(self):
        plan=self.plan();runtime._exclusive_slot(self.stage,plan)
        with self.assertRaisesRegex(ValueError,'ALREADY_CONSUMED'):runtime._exclusive_slot(self.stage,plan)
        changed=copy.deepcopy(plan);changed['plan_id']='sha256:'+'a'*64
        with self.assertRaisesRegex(ValueError,'ALREADY_CONSUMED'):runtime._exclusive_slot(self.stage,changed)
        result=runtime.run_update(approval_url=URL)
        self.assertEqual('STAGE_STOPPED',result['status'])
        self.assertEqual([0,0,0],result['stage_provider_paid_sec_calls'])

    def test_uncommitted_new_input_bytes_do_not_change_code_identity(self):
        import sec_http
        from tests.vnext.test_annual_update import Response
        before=runtime.code_identity()
        inventory=update.saved_source(repo_root=self.data,url='https://data.sec.gov/submissions/CIK0001048286.json')
        payload=json.loads(inventory['raw']);recent=payload['filings']['recent']
        # Simulated list adds an unrelated filing; it is input bytes, not source code.
        for values in recent.values():values.append(values[0])
        recent['form'][-1]='8-K';recent['accessionNumber'][-1]='0001048286-26-009999'
        client=sec_http.SecHttpClient(workdir=self.data,config_path=self.data/'config/sec_config.json',log_path=self.data/'evidence/requests_log.csv')
        client.config={**client.config,'max_retries':0}
        with mock.patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'runtime-tests@secmetrics.org'}),mock.patch.object(sec_http,'urlopen',return_value=Response(json.dumps(payload).encode())):
            client.fetch(url=inventory['proof']['source_url'],purpose='SIMULATED_HTTP_BOUNDARY',local_path=self.data/'evidence/test/new-list.json')
        binding=runtime.verify_stage(approval_url=URL)
        plan=runtime.prepare_plan(binding=binding)
        self.assertNotEqual(inventory['proof']['content_sha256'],plan['prepared_input']['source_proofs'][0]['content_sha256'])
        self.assertEqual(before,runtime.code_identity())
        self.assertFalse((self.data/'.git').exists())
        self.assertEqual('2025-12-31',plan['prepared_input']['table_input']['target_period']['period_end'])


if __name__=='__main__':unittest.main()
