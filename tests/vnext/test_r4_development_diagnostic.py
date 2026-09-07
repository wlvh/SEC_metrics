"""Current implementation binding and the same nine-request controller, offline."""
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

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_r4_live_qualification import copy_r4_release_workspace
from tests.vnext.test_r4_reader_responsibilities import no_network
from vnext import ai_adapter, invocation_control
from vnext.canonical import canonical_json_bytes, strict_json_file, content_hash
from vnext.r4_development import (diagnostic_implementation, prepare_diagnostic_context,
    build_diagnostic_plan, execute_diagnostic, replay_diagnostic, validate_diagnostic_prefix,
    RUNTIME_ROOT, REQUEST_SET_ID)
from vnext.r4_live_qualification import execute_r4_qualification, R4QualificationError
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile import validate_execution_authority, RequirementProfileError


def transports(context, plan, failures=False, unknown=False):
    rows = {}
    for entry in plan['entries']:
        response = json.loads(strict_json_file(path=context._root / 'docs/r4_v3/qualified_cases'
            / entry['fixture_id'] / 'scoped_attempt.json')['response_text'])
        if failures and entry['ordinal'] == 1:
            response['candidates'][0]['claimed_raw_value'] = '999'
        if failures and entry['ordinal'] == 2:
            response['unexpected_extra_field'] = 'synthetic schema failure'
        if failures and entry['ordinal'] == 3:
            response['unresolved_competing_claims'] = [{'description':'Synthetic unresolved same-period conflict'}]
        raw = {'id':'recorded-development-'+str(entry['ordinal']), 'model':'deepseek-v4-flash',
            'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(response)}}],
            'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,
                'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000}}
        rows[entry['entry_id']] = ai_adapter.build_recorded_scoped_transport(
            raw_response_bytes=canonical_json_bytes(value=raw),
            expected_provider_request_body_sha256=context._requests[entry['fixture_id']].identity['provider_request_body_sha256'],
            unknown_remote_outcome=unknown and entry['ordinal']==1)
    return rows


class R4DevelopmentDiagnosticTest(unittest.TestCase):
    def workspace(self, stack):
        directory = stack.enter_context(tempfile.TemporaryDirectory(prefix='r4-diagnostic-current-'))
        root = Path(directory)/'current'
        copy_r4_release_workspace(root)
        guards = no_network(stack)
        return root, guards

    def test_nine_controller_samples_continue_content_only_and_independent_replay(self):
        with ExitStack() as stack:
            root, guards = self.workspace(stack)
            requirement = load_requirement_snapshot(snapshot_dir=root/'requirements/issue_28_v3')
            with self.assertRaises(RequirementProfileError):
                validate_execution_authority(repo_root=root, requirement=requirement)
            with diagnostic_implementation(root) as binding:
                validate_execution_authority(repo_root=root, requirement=requirement)
                self.assertEqual(binding.record['request_set_id'],REQUEST_SET_ID)
                self.assertEqual(binding.files['scripts/vnext/r4_development.py']['size'],
                    (root/'scripts/vnext/r4_development.py').stat().st_size)
                context=prepare_diagnostic_context(root)
                plan=build_diagnostic_plan(context,mode='RECORDED_TEST')
                self.assertEqual(len(plan['entries']),9)
                self.assertEqual(plan['counts']['stability_provider_calls'],0)
                with self.assertRaises(R4QualificationError):
                    execute_r4_qualification(repo_root=root,plan=plan,context=context)
                result=execute_diagnostic(context=context,plan=plan,
                    recorded_transports=transports(context,plan,failures=True))
                self.assertEqual(result['status'],'COMPLETED_DIAGNOSTIC')
                self.assertEqual([e['status'] for e in result['entries']],['CONTENT_FAILED']*3+['ACCEPTED']*6)
                self.assertEqual(result['counters']['mock_transport_invocation_count'],9)
                self.assertEqual(result['counters']['real_model_provider_egress_count'],0)
                self.assertEqual(result['qualification_credit'],'NONE')
                with self.assertRaises(FileExistsError):
                    execute_diagnostic(context=context,plan=plan,recorded_transports=transports(context,plan))
                path=root/'recorded_diagnostic_plan.json';path.write_bytes(canonical_json_bytes(value=plan))
            env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET'))}
            env['PYTHONDONTWRITEBYTECODE']='1'
            env['PYTHONPATH']=str(root/'scripts')+os.pathsep+str(root)
            command=[sys.executable,'-c',
                'from pathlib import Path; from contextlib import ExitStack; '
                'from tests.vnext.test_r4_reader_responsibilities import no_network; '
                'from vnext.r4_development import diagnostic_implementation,prepare_diagnostic_context,replay_diagnostic; '
                'from vnext.canonical import strict_json_file; import json; '
                's=ExitStack(); no_network(s); root=Path.cwd(); s.enter_context(diagnostic_implementation(root)); '
                'c=prepare_diagnostic_context(root); r=replay_diagnostic(c,strict_json_file(path=root/"recorded_diagnostic_plan.json")); '
                'assert r["observed_samples"]==9 and r["qualification_credit"]=="NONE"; '
                'print(json.dumps({"independent_replay":"PASS","samples":9,"provider_calls":0})); s.close()']
            cold=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=300)
            self.assertEqual(cold.returncode,0,cold.stdout+cold.stderr)
            print(cold.stdout.strip(),flush=True)
            with diagnostic_implementation(root):
                context=prepare_diagnostic_context(root)
                first=root/RUNTIME_ROOT/plan['pending_plan_id'][7:]/'entries'/plan['entries'][0]['entry_id'][7:]
                (first/'payloads/raw_response.bin').write_bytes(b'tampered')
                with self.assertRaises(ValueError):
                    validate_diagnostic_prefix(context=context,plan=plan,entry_id=plan['entries'][1]['entry_id'])
            for guard in guards: guard.assert_not_called()

    def test_unknown_stops_after_one_mock_call(self):
        with ExitStack() as stack:
            root,guards=self.workspace(stack)
            with diagnostic_implementation(root):
                context=prepare_diagnostic_context(root);plan=build_diagnostic_plan(context,mode='RECORDED_TEST')
                result=execute_diagnostic(context=context,plan=plan,recorded_transports=transports(context,plan,unknown=True))
                self.assertEqual(result['status'],'STOPPED')
                self.assertEqual(result['observed_samples'],1)
                self.assertEqual(result['entries'][0]['execution_status'],'UNKNOWN_REMOTE_OUTCOME')
                self.assertEqual(result['counters']['mock_transport_invocation_count'],1)
                self.assertFalse((root/RUNTIME_ROOT/plan['pending_plan_id'][7:]/'entries'/plan['entries'][1]['entry_id'][7:]).exists())
            for guard in guards: guard.assert_not_called()

    def test_acceptance_persistence_failure_is_not_content_failure(self):
        with ExitStack() as stack:
            root,guards=self.workspace(stack)
            with diagnostic_implementation(root):
                context=prepare_diagnostic_context(root);plan=build_diagnostic_plan(context,mode='RECORDED_TEST')
                with mock.patch.object(invocation_control,'_persist_acceptance_receipt',
                        side_effect=invocation_control.InvocationControlError('synthetic persistence failure')):
                    result=execute_diagnostic(context=context,plan=plan,recorded_transports=transports(context,plan))
                self.assertEqual(result['status'],'STOPPED')
                self.assertEqual(result['observed_samples'],1)
                self.assertEqual(result['entries'][0]['execution_status'],'FAILED_TERMINAL')
                self.assertEqual(result['entries'][0]['response_validation']['status'],'ACCEPTED')
                self.assertEqual(result['counters']['mock_transport_invocation_count'],1)
                self.assertFalse((root/RUNTIME_ROOT/plan['pending_plan_id'][7:]/'entries'/plan['entries'][1]['entry_id'][7:]).exists())
            for guard in guards: guard.assert_not_called()


class DiagnosticArtifactBoundaryTest(unittest.TestCase):
    def test_payload_fields_and_formal_terminal_cannot_escape_diagnostic_closure(self):
        from vnext.r4_development import _read_payloads, _tree
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'payloads').mkdir()
            fields=sorted(['request_body','reader_payload','task_contract','output_schema'])
            for name in fields: (root/'payloads'/(name+'.bin')).write_bytes(b'fixture')
            self.assertEqual(set(_read_payloads(root,fields)),set(fields))
            for bad in (fields+['../../secret'],fields+[fields[0]],fields[:-1]):
                with self.assertRaises(ValueError): _read_payloads(root,bad)
            self.assertEqual(len(_tree(root)),4)
            (root/'qualification_terminal.json').write_bytes(b'{}')
            with self.assertRaises(ValueError): _tree(root)


if __name__=='__main__': unittest.main()
