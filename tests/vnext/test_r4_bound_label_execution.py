"""One normal controller -> freeze -> fresh-process replay on new bound inputs.

No Checker override, hash bypass, source re-signing or historical Python swap.
The new-request response is explicitly synthetic RECORDED_TEST data. The paid
historical response remains a separately identified OFFLINE_REGRESSION sample.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_r4_live_qualification import copy_r4_release_workspace
from vnext import ai_adapter
import sec_http
from vnext.canonical import canonical_json_bytes, strict_json_file, sha256_bytes
from vnext.r4_label_policy import CURRENT_R4_REQUIREMENT, SOURCE_LABEL_POLICY, RAW_LABEL_POLICY, label_policy, corpus_root
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile import validate_execution_authority
from vnext.r4_live_authority import prepare_r4_execution_context, build_r4_recorded_test_plan, authorize_r4_recorded_test_entry
from vnext.r4_live_qualification import _structured_terminals
from vnext.live_scoped_reader import build_scoped_invocation_acceptance_context
from vnext.r4_run_store import create_r4_scoped_run, finalize_r4_scoped_run


class R4BoundLabelExecutionTest(unittest.TestCase):
    def test_normal_acceptance_freeze_and_independent_replay(self):
        with tempfile.TemporaryDirectory(prefix='r4-bound-label-') as directory, ExitStack() as stack:
            root = Path(directory)/'release'
            # Copies this candidate byte-for-byte; no restoring old Python or
            # rewriting Requirement/activation metadata in the test workspace.
            copy_r4_release_workspace(root)
            guards = [stack.enter_context(mock.patch.object(owner,name,
                side_effect=AssertionError('OFFLINE ONLY'))) for owner,name in (
                (ai_adapter,'_open_provider_request'),(sec_http.SecHttpClient,'fetch'),
                (sec_http,'urlopen'),(socket.socket,'connect'),(socket.socket,'connect_ex'))]
            requirement=load_requirement_snapshot(snapshot_dir=root/'requirements'/CURRENT_R4_REQUIREMENT)
            validate_execution_authority(repo_root=root,requirement=requirement)
            self.assertEqual(label_policy(requirement),SOURCE_LABEL_POLICY)
            parent=load_requirement_snapshot(snapshot_dir=root/'requirements/issue_28_v2')
            self.assertEqual(parent['requirement_closure_hash'],
                'sha256:5b7a386b7c95f8b9542a2251a94ec8d98876e7c833d49132364c77024b27ff9e')
            self.assertEqual(label_policy(parent),RAW_LABEL_POLICY)
            context=prepare_r4_execution_context(repo_root=root)
            print('BOUND_R4: new source/Requirement/request bindings verified',flush=True)
            plan=build_r4_recorded_test_plan(context=context)
            self.assertEqual(plan['requirement_id'],CURRENT_R4_REQUIREMENT)
            self.assertEqual(len(plan['entries']),12)
            entry=plan['entries'][0];request=context._requests[entry['fixture_id']]
            self.assertNotEqual(request.provider_request_body_bytes,
                (root/'tests/fixtures/r4_label_representation/provider_request.json').read_bytes())
            self.assertIn("same located cell's supplied raw_text or text",
                json.loads(request.provider_request_body_bytes)['messages'][0]['content'])
            _structured_terminals(context=context,plan=plan,create=True)
            print('BOUND_R4: native zero-call prerequisites FROZEN',flush=True)
            fixture,_,source,_,authority=context._session._fixture(entry['fixture_id'])
            response=json.loads(strict_json_file(path=root/corpus_root(CURRENT_R4_REQUIREMENT)
                /entry['fixture_id']/'scoped_attempt.json')['response_text'])
            changed=False
            for claim in response['candidates']:
                for label in claim['scope_evidence_locators']:
                    if label['location_type']!='caption':
                        cell=source['evidence'].resolve_cell(derived_asset=authority['full_derived_asset'],locator=label['locator'])
                        changed=changed or cell['text']!=cell['raw_text']
                        label['raw_text']=cell['text']
            self.assertTrue(changed)
            wire={'id':'recorded-new-request-label-v2','model':'deepseek-v4-flash',
                'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(response)}}],
                'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,
                    'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000}}
            transport=ai_adapter.build_recorded_scoped_transport(raw_response_bytes=canonical_json_bytes(value=wire),
                expected_provider_request_body_sha256=request.identity['provider_request_body_sha256'])
            authorization=authorize_r4_recorded_test_entry(context=context,plan=plan,entry_id=entry['entry_id'])
            adapter=ai_adapter.build_scoped_qualification_transport_adapter(authorization=authorization,recorded_transport=transport)
            acceptance=build_scoped_invocation_acceptance_context(request=request,execution_context=context)
            attempt=ai_adapter.run_scoped_ai_attempt(adapter=adapter,prepared_request=request,acceptance_context=acceptance,
                clock=lambda:datetime(2026,9,7,tzinfo=timezone.utc))
            self.assertEqual(attempt.execution_receipt['status'],'SUCCEEDED')
            print('BOUND_R4: normal controller acceptance SUCCEEDED',flush=True)
            self.assertEqual(attempt.acceptance_receipt['validator_semantic_version'],'source-bound-scoped-reader-acceptance-v2')
            workspace=root/'artifacts/vnext/qualification/r4_scoped'/plan['pending_plan_id'][7:]/'entries'/entry['entry_id'][7:]
            run=workspace/'run'
            create_r4_scoped_run(repo_root=root,run_dir=run,attempt_result=attempt,acceptance_context=acceptance)
            frozen=finalize_r4_scoped_run(repo_root=root,run_dir=run,acceptance_context=acceptance)
            self.assertEqual(frozen['status'],'FROZEN')
            print('BOUND_R4: native finalizer FROZEN; starting fresh-process replay',flush=True)
            manifest_before=(run/'manifest.json').read_bytes()
            code='''import json, pathlib, sys, socket
from unittest.mock import patch
from contextlib import ExitStack
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'scripts'))
from vnext.r4_run_store import replay_r4_scoped_run
from vnext import ai_adapter
import sec_http
with ExitStack() as s:
 for owner,name in [(socket.socket,'connect'),(socket.socket,'connect_ex'),(ai_adapter,'_open_provider_request'),(sec_http.SecHttpClient,'fetch'),(sec_http,'urlopen')]:
  s.enter_context(patch.object(owner,name,side_effect=AssertionError('OFFLINE REPLAY')))
 result=replay_r4_scoped_run(repo_root=root,run_dir=root/sys.argv[1])
 print(json.dumps(result,sort_keys=True))
'''
            env={k:v for k,v in os.environ.items() if k not in {'DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','SEC_CONTACT_EMAIL'}}
            env['PYTHONDONTWRITEBYTECODE']='1'
            child=subprocess.run([sys.executable,'-c',code,run.relative_to(root).as_posix()],cwd=root,
                env=env,text=True,capture_output=True,timeout=600)
            self.assertEqual(child.returncode,0,child.stderr)
            replay=json.loads(child.stdout)
            self.assertEqual(replay['run_status'],'FROZEN')
            self.assertEqual((run/'manifest.json').read_bytes(),manifest_before)
            for guard in guards:guard.assert_not_called()
            # Publication-side version/Spec/ReleasePlan readback only: no stage
            # or twelve-call qualification aggregate is claimed by this test.
            from vnext.r4_release import _release_authority
            release=_release_authority(root,CURRENT_R4_REQUIREMENT)[1]
            self.assertEqual(release['requirement_closure_hash'],requirement['requirement_closure_hash'])
            self.assertEqual(len(release['cumulative_vnext_result_keys']),300)
            print(json.dumps({'status':'PASSED','requirement_id':CURRENT_R4_REQUIREMENT,
                'requirement_closure_hash':requirement['requirement_closure_hash'],
                'run_status':'FROZEN','independent_replay':replay,'publication_version_readback':'PASS',
                'response_classification':'NEW_REQUEST_RECORDED_FIXTURE','historical_response_classification':'OFFLINE_REGRESSION_ONLY',
                'historical_request_differs':True,'request_sha256':sha256_bytes(content=request.provider_request_body_bytes),
                'provider_paid_sec_calls':[0,0,0]},sort_keys=True),flush=True)


if __name__=='__main__':unittest.main()
