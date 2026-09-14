"""Captured plans remain original while identical inputs get current checks."""
from dataclasses import replace
from pathlib import Path
import json
import socket
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from vnext.canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_loads
from vnext.continuous_semantic_calls import prepare_requests, build_plan
from vnext.native_assessment_replay import replay_native_response, _original_runtime, _captured_policy_view
from vnext.normal_source_authority import ROOT
from vnext import invocation_control as control


class NativeAssessmentReplayMaterialTest(unittest.TestCase):
    def test_original_plan_survives_consumer_change_and_rebinding_is_rejected(self):
        material = ROOT/'docs/evidence/issue28_continuous/b13-content-guards'
        index = json.loads((material/'native-material-index.json').read_text())
        archive = material/'native-material.tar.gz'
        self.assertEqual(sha256_file(path=archive), index['archive_sha256'])
        prefix = 'final-native/ledger/calls/0001/'
        targets = {}
        for name, binding in index['files'].items():
            if name.startswith(prefix):
                targets.setdefault(binding['sha256'], []).append(name[len(prefix):])
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')):
            path = Path(temporary)/'call'; path.mkdir()
            with tarfile.open(archive, 'r|gz') as source:
                for member in source:
                    digest = member.name.removeprefix('blobs/')
                    if digest not in targets:
                        continue
                    raw = source.extractfile(member).read()
                    for relative in targets[digest]:
                        destination = path/relative; destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(raw)
            request = json.loads((path/'semantic-request.json').read_text())
            prepared = next(p for p in prepare_requests(company_id='enphase_energy', metric_id='B13')
                            if strict_json_loads(text=p.request_bytes.decode())['request_id'] == request['request_id'])
            result = replay_native_response(prepared=prepared, path=path)
            old_plan = result['plan']; old_receipt = result['success']['acceptance_receipt_id']
            self.assertNotEqual(old_plan['requirement_closure_hash'], prepared.requirement['requirement_closure_hash'])
            self.assertEqual(result['revalidation']['original_acceptance_receipt_id'], old_receipt)
            self.assertFalse(result['revalidation']['new_provider_execution'])
            with _original_runtime(path) as root:
                view = _captured_policy_view(root=root, prepared=prepared, plan=old_plan)
                with self.assertRaises(control.InvocationControlError):
                    with control._successor_plan_context(repo_root=ROOT, authority=view):
                        self.fail('Read-only historical view became execution authority')
            changed = dict(request); changed['system_prompt'] += ' changed output contract'
            with self.assertRaisesRegex(ValueError, 'SAVED_REQUEST_OR_SOURCE_CHANGED'):
                replay_native_response(prepared=replace(prepared, request_bytes=canonical_json_bytes(value=changed)), path=path)
            original_response = (path/'wire/assistant-output.bin').read_bytes()
            (path/'wire/assistant-output.bin').write_bytes(original_response+b' ')
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_EVIDENCE_CHANGED'):
                replay_native_response(prepared=prepared, path=path)
            (path/'wire/assistant-output.bin').write_bytes(original_response)
            # Fully hash a new intent/terminal around the current plan. It
            # still cannot relabel the old native success/acceptance receipts.
            _, new_plan = build_plan(prepared)
            intent = json.loads((path/'intent.json').read_text())
            intent.update(plan_id=new_plan['ai_invocation_plan_id'],
                          requirement_closure_hash=new_plan['requirement_closure_hash'])
            intent['intent_id'] = content_hash(value={k:v for k,v in intent.items() if k != 'intent_id'})
            (path/'intent.json').write_bytes(canonical_json_bytes(value=intent))
            new_relative = 'invocation_control/plans/'+new_plan['ai_invocation_plan_id'][7:]+'.json'
            (path/new_relative).write_bytes(canonical_json_bytes(value=new_plan))
            terminal = json.loads((path/'terminal.json').read_text())
            terminal['intent_id'] = intent['intent_id']
            for relative in ['intent.json', new_relative]:
                terminal['evidence'][relative] = sha256_file(path=path/relative)
            terminal['terminal_id'] = content_hash(value={k:v for k,v in terminal.items() if k != 'terminal_id'})
            (path/'terminal.json').write_bytes(canonical_json_bytes(value=terminal))
            with self.assertRaises((ValueError, control.InvocationControlError)):
                replay_native_response(prepared=prepared, path=path)
