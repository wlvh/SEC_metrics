"""New scope through normal CLI and saved-plan replay; no real GitHub/provider.

The temporary checkout contains current code and a real clean test Git commit.
Only GitHub responses are synthetic for owner-preflight boundary tests; those
objects never leave this test or authorize a provider connection.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.vnext.test_r4_live_qualification import copy_r4_release_workspace
from tests.vnext.test_r4_reader_responsibilities import no_network
from tests.vnext.test_r4_cell_selection import synthetic_response
from vnext import ai_adapter, r4_live_authority as authority
from vnext.canonical import canonical_json_bytes, content_hash, strict_json_file
from vnext.cell_selection import REVISION
from vnext.r4_development import (REQUEST_SET_ID, SELECTION_REQUEST_SET_ID,
    SELECTION_SCOPE_PATH, RUNTIME_ROOT, approved_scope, diagnostic_implementation,
    diagnostic_implementation_for_plan, prepare_diagnostic_context,
    build_diagnostic_plan, execute_diagnostic)


class SelectionDiagnosticWiringTest(unittest.TestCase):
    def test_cli_plan_owner_boundary_three_controller_samples_and_cold_cli_replay(self):
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='r4-selection-wiring-')))/'current'
            copy_r4_release_workspace(root)
            guards = no_network(stack)
            env = {k:v for k,v in os.environ.items()
                   if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET')) and not k.startswith('GIT_')}
            env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(root/'scripts')+os.pathsep+str(root))
            for args in (['init','-q'], ['config','user.name','Offline Test'],
                         ['config','user.email','offline-test@example.invalid'],
                         ['add','.'], ['-c','commit.gpgsign=false','commit','-qm','Current offline test checkout']):
                subprocess.run(['git',*args],cwd=root,env=env,check=True,capture_output=True)

            def cli(args, expected=0):
                child = subprocess.run([sys.executable,'-c',
                    'from contextlib import ExitStack; '
                    'from tests.vnext.test_r4_reader_responsibilities import no_network; '
                    'from tools.vnext_r4_qualification import main; '
                    's=ExitStack(); g=no_network(s); r=main('+repr(args)+'); '
                    '[x.assert_not_called() for x in g]; s.close(); raise SystemExit(r)'],
                    cwd=root,env=env,capture_output=True,text=True,timeout=300)
                self.assertEqual(child.returncode,expected,child.stdout+child.stderr)
                return json.loads(child.stdout)

            live = cli(['diagnostic-plan','--request-set-id',SELECTION_REQUEST_SET_ID])
            approval = cli(['diagnostic-authorization','--plan-id',live['pending_plan_id']])
            self.assertEqual(live['execution_mode'],'LIVE')
            self.assertEqual(live['owner_authorization'],'NOT_ISSUED')
            self.assertEqual(live['call_bounds']['hard_maximum'],9)
            self.assertEqual(approval['request_set_id'],SELECTION_REQUEST_SET_ID)
            self.assertEqual(approval['interface_revision'],REVISION)
            self.assertEqual(approval['authorized_entry_ids'],[e['entry_id'] for e in live['entries']])

            with diagnostic_implementation_for_plan(root,live) as binding:
                self.assertFalse(binding.offline_only)
                context = prepare_diagnostic_context(root)
                authority.validate_r4_execution_plan(plan=live,context=context,
                    expected_plan_id=live['pending_plan_id'],mode='LIVE')
                for row, entry in zip(approved_scope(root,SELECTION_REQUEST_SET_ID)['entries'],live['entries']):
                    request = context._requests[row['fixture_id']]
                    self.assertEqual(entry['request_identity']['provider_request_body_sha256'],row['request_sha256'])
                    self.assertEqual(len(request.provider_request_body_bytes),row['request_bytes'])
                    self.assertEqual(request.identity['request_interface_revision'],REVISION)
                with self.assertRaisesRegex(ValueError,'requires owner preflight'):
                    execute_diagnostic(context=context,plan=live)
                with mock.patch.object(authority,'REPOSITORY_ROOT',root), self.assertRaisesRegex(ValueError,'not verified owner-comment'):
                    authority.authorize_r4_live_entry(context=context,plan=live,
                        entry_id=live['entries'][0]['entry_id'],owner_receipt=approval)
                self.assertFalse((root/RUNTIME_ROOT/live['pending_plan_id'][7:]/'execution_started').exists())

                # Exercise the actual preflight with explicit test-only GitHub
                # fixtures. Real git/source/hash checks remain intact.
                url = 'https://github.com/wlvh/SEC_metrics/pull/123#issuecomment-456'
                real_run = subprocess.run
                def preflight(body):
                    def response(command, **kwargs):
                        if command[:2] != ['gh','api']:
                            return real_run(command,**kwargs)
                        if '/issues/comments/' in command[-1]:
                            value = {'id':456,'html_url':url,'user':{'login':'wlvh'},
                                'body':json.dumps(body),'created_at':'2026-09-07T00:00:00Z',
                                'updated_at':'2026-09-07T00:00:00Z'}
                        else:
                            value = {'state':'open','merged':False,'base':{'ref':'main'},
                                'head':{'sha':live['implementation_head'],'repo':{'full_name':'wlvh/SEC_metrics'}}}
                        return subprocess.CompletedProcess(command,0,json.dumps(value),'')
                    with mock.patch.object(authority,'REPOSITORY_ROOT',root), mock.patch.object(
                            authority.subprocess,'run',side_effect=response):
                        owner = authority.verify_r4_live_owner_comment(context=context,plan=live,source_url=url)
                        cap = authority.authorize_r4_live_entry(context=context,plan=live,
                            entry_id=live['entries'][0]['entry_id'],owner_receipt=owner)
                        self.assertEqual(authority.authorization_binding(cap)['pending_plan'],live)
                preflight(approval)
                for change in ({'request_set_id':REQUEST_SET_ID}, {'interface_revision':'SOURCE_BOUND_MODEL_RESPONSIBILITIES_V1'},
                               {'exact_head':'f'*40}, {'authorized_entry_ids':approval['authorized_entry_ids'][:-1]},
                               {'maximum_provider_calls':12}):
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        preflight({**approval,**change})

                recorded = build_diagnostic_plan(context,mode='RECORDED_TEST')
                transports = {}
                for entry in recorded['entries']:
                    request = context._requests[entry['fixture_id']]
                    scope = context._session._fixture(entry['fixture_id'])[-2]
                    response = synthetic_response(json.loads(request.request_bytes),scope)
                    if entry['ordinal'] == 1:
                        response['selected_value_text'] = '999'
                    wire = {'id':'SYNTHETIC_SELECTION_WIRING_'+str(entry['ordinal']),
                        'model':'deepseek-v4-flash','choices':[{'finish_reason':'stop',
                        'message':{'role':'assistant','content':json.dumps(response)}}],
                        'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,
                            'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000}}
                    transports[entry['entry_id']] = ai_adapter.build_recorded_scoped_transport(
                        raw_response_bytes=canonical_json_bytes(value=wire),
                        expected_provider_request_body_sha256=request.identity['provider_request_body_sha256'],
                        unknown_remote_outcome=entry['ordinal']==3)
                result = execute_diagnostic(context=context,plan=recorded,recorded_transports=transports)
                self.assertEqual([e['status'] for e in result['entries']],['CONTENT_FAILED','ACCEPTED','STOP'])
                self.assertEqual(result['unstarted_samples'],6)
                self.assertEqual(result['counters']['mock_transport_invocation_count'],3)
                self.assertEqual(result['counters']['real_model_provider_egress_count'],0)
                with self.assertRaises(FileExistsError):
                    execute_diagnostic(context=context,plan=recorded,recorded_transports=transports)
                path = root/RUNTIME_ROOT/'plans'/(recorded['pending_plan_id'][7:]+'.json')
                path.write_bytes(canonical_json_bytes(value=recorded))
            cold = cli(['diagnostic-replay','--plan-id',recorded['pending_plan_id']],expected=1)
            self.assertEqual(cold,result)
            print('SELECTION_WIRING: clean CLI LIVE plan; exact test owner preflight; old/altered grants rejected; '
                  '3 mock samples CONTENT_FAILED/ACCEPTED/STOP; fresh CLI replay identical; real provider/SEC=0',flush=True)

            # Preserve the old exact request generation and offline-only guard.
            with diagnostic_implementation(root):
                old_context = prepare_diagnostic_context(root)
                old = build_diagnostic_plan(old_context,mode='RECORDED_TEST')
                old_approval = authority.expected_r4_owner_approval(plan=old,
                    exact_head=live['implementation_head'],exact_tree=live['implementation_tree'])
                self.assertEqual(old_approval['request_set_id'],REQUEST_SET_ID)
                self.assertNotIn('interface_revision',old_approval)
                self.assertNotEqual(old['entries'][0]['entry_id'],live['entries'][0]['entry_id'])
            with diagnostic_implementation(root,offline_interface_revision=REVISION):
                offline_context = prepare_diagnostic_context(root)
                with self.assertRaises(ValueError): build_diagnostic_plan(offline_context,mode='LIVE')
                experiment = build_diagnostic_plan(offline_context,mode='RECORDED_TEST')
            with self.assertRaisesRegex(ValueError,'Offline experimental'):
                with diagnostic_implementation_for_plan(root,experiment): pass
            for field,value in (('request_set_id',REQUEST_SET_ID),('interface_revision','wrong')):
                tampered = copy.deepcopy(recorded);tampered['implementation_authority'][field]=value
                tampered['pending_plan_id']=content_hash(value={k:v for k,v in tampered.items() if k!='pending_plan_id'})
                with self.assertRaisesRegex(ValueError,'binding differs'):
                    with diagnostic_implementation_for_plan(root,tampered): pass
            scope_path = root/SELECTION_SCOPE_PATH
            scope_path.write_bytes(scope_path.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'binding differs'):
                with diagnostic_implementation_for_plan(root,recorded): pass
            for guard in guards: guard.assert_not_called()
            if os.environ.get('R4_SELECTION_WIRING_EVIDENCE_DIR'):
                out=Path(os.environ['R4_SELECTION_WIRING_EVIDENCE_DIR']);out.mkdir(parents=True,exist_ok=True)
                (out/'recorded-replay.json').write_bytes(canonical_json_bytes(value=cold))


if __name__ == '__main__': unittest.main()
