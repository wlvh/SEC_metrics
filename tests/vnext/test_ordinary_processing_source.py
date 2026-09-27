"""Current ordinary rules can consume admitted source without rewriting history."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from vnext.c04_registration_successor import EVENT_FORMS
from vnext.continuous_sec_acquisition import (
    initialize_source_inputs, recorded_sec_session)
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT
from vnext.ordinary_refresh_cycle import refresh_and_process
from vnext.ordinary_processing_source import (
    current_processing_source, verify_processing_source)


class OrdinaryProcessingSourceTest(unittest.TestCase):
    def test_stale_acquisition_rules_do_not_block_current_saved_source_cases(self):
        self.enterContext(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.enterContext(patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')))
        self.enterContext(patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')))
        original_popen = subprocess.Popen
        def local_git_only(*args, **kwargs):
            command = args[0] if args else kwargs.get('args')
            if (not isinstance(command, (list, tuple)) or not command
                    or Path(command[0]).name != 'git'
                    or any(part in {'fetch', 'pull', 'push', 'clone',
                                    'ls-remote', 'submodule'} for part in command)):
                raise AssertionError('NONLOCAL_SUBPROCESS_FORBIDDEN')
            return original_popen(*args, **kwargs)
        self.enterContext(patch.object(subprocess, 'Popen',
            side_effect=local_git_only))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'recorded-ledger',
                                           response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                pass
            initialize_source_inputs(root=source, requirement=session.requirement)
            ledger = source/'evidence/requests_log.csv'
            policy = source/'config/issue28_normal_results_v2.json'
            original_ledger = ledger.read_bytes()
            stale = json.loads(policy.read_text())
            stale['freeze_enabled'] = not stale['freeze_enabled']
            policy.write_text(json.dumps(stale, ensure_ascii=False) + '\n')
            stale_policy = policy.read_bytes()
            from vnext.normal_run_v3 import _policy
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_INTEGRATED_INSTALLED_POLICY_CHANGED'):
                _policy(source)
            first = current_processing_source(acquisition_root=source,
                output_parent=root/'processing', requirement=session.requirement)
            second = current_processing_source(acquisition_root=source,
                output_parent=root/'processing', requirement=session.requirement)
            self.assertFalse(first['reused'])
            self.assertTrue(second['reused'])
            self.assertEqual(first['snapshot_id'], second['snapshot_id'])
            self.assertEqual([0, 0, 0], first['new_calls'])
            b01 = prepare_case(data_root=first['data_root'],
                company_id='salesforce', metric_id='B01')
            self.assertEqual('PUBLISHED', b01['results']['B01']['publication'])
            # The frozen repo baseline lacks this company's extra C04 source.
            # A current processing rule cannot manufacture the missing input.
            with self.assertRaisesRegex(ValueError,
                    'C04_REGISTRATION_BASE_INPUT_UNRESOLVED'):
                prepare_case(data_root=first['data_root'],
                    company_id='salesforce', metric_id='C04',
                    c04_event_forms=EVENT_FORMS)
            mixed = refresh_and_process(session=session,
                state_root=root/'update-state',
                company_ids=['salesforce'], metric_ids=['B01', 'C04'],
                max_sec_requests=0, max_provider_requests=0,
                c04_successor=True)
            outcomes = {row['metric_id']: row for row in
                mixed['companies'][0]['updates']['metrics']}
            self.assertEqual('CANDIDATE_READY', outcomes['B01']['status'],
                             outcomes['B01'])
            self.assertNotEqual('CANDIDATE_READY', outcomes['C04']['status'])
            self.assertEqual('UPDATES_INCOMPLETE', mixed['status'])
            self.assertEqual([0, 0, 0], mixed['ledger_counts_after'])
            self.assertEqual(mixed['ledger_counts_before'],
                             mixed['ledger_counts_after'])
            self.assertTrue(mixed['current_processing_source_snapshot_id'])
            self.assertEqual(original_ledger, ledger.read_bytes())
            self.assertEqual(stale_policy, policy.read_bytes())

            original = ROOT/'config/b06_special_scope_v1.json'
            original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
            private = first['data_root']/'config/b06_special_scope_v1.json'
            with private.open('ab') as handle:
                handle.write(b' ')
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_PROCESSING_SNAPSHOT_RULE_CHANGED'):
                verify_processing_source(acquisition_root=source,
                    processing_root=first['data_root'],
                    requirement=session.requirement)
            self.assertEqual(original_hash,
                hashlib.sha256(original.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
