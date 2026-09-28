"""D03 may inspect a registered current source without opening live calls."""
from dataclasses import replace
import hashlib
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext.continuous_call_ledger import recorded_ledger
from vnext.batch_workflow import BatchWorkflowError
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.continuous_sec_acquisition import initialize_source_inputs
from vnext.continuous_semantic_calls import (
    execute_d03_recorded_assessment, execute_feasibility,
    prepare_d03_replay_only_requests,
)
from vnext.d03_native_assessment import collect_recorded_assessments
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.canonical import strict_json_loads
from tests.vnext.test_d03_native_assessment import _response, _wire


class D03CurrentSourceReplayTest(unittest.TestCase):
    def test_registered_source_replays_one_group_without_live_credit(self):
        with tempfile.TemporaryDirectory(prefix='d03-current-source-replay-') as temporary:
            ledger = recorded_ledger(root=Path(temporary)/'ledger')
            source_root = ledger.root/'source-inputs'
            requirement = load_requirement_snapshot(
                snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
            with ledger.locked():
                self.assertEqual([0, 0, 0], ledger.snapshot()['counts'])
            initialize_source_inputs(root=source_root, requirement=requirement,
                                     clone_baseline=True)
            with patch.object(socket.socket, 'connect',
                    side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                    side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                    side_effect=AssertionError('HTTP_FORBIDDEN')):
                prepared = prepare_d03_replay_only_requests(
                    company_id='marriott_international', source_root=source_root,
                    source_ledger=ledger)
                self.assertTrue(prepared)
                self.assertTrue(all(row.replay_only and row.data_root == source_root
                    and row.source_ledger is ledger for row in prepared))
                source = strict_json_loads(text=prepared[0].source_bytes.decode())
                self.assertIs(True, source['external_replay_only'])
                requests = [strict_json_loads(text=row.request_bytes.decode())
                            for row in prepared]
                self.assertEqual(source['required_unit_ids'],
                    [unit['unit_id'] for request in requests
                     for unit in request['units']])
                self.assertTrue(all(request['external_replay_only'] is True
                    for request in requests))
                selected = next(row for row, request in zip(prepared, requests)
                    if request['required_candidate_assessments'])
                request = strict_json_loads(text=selected.request_bytes.decode())
                wire = _wire(_response(request))
                path, outcome = execute_d03_recorded_assessment(
                    prepared=selected, ledger=ledger, recorded_wire=wire)
                self.assertEqual('SUCCEEDED', outcome['terminal']['status'])
                self.assertFalse(outcome['native_result_created'])
                collection = collect_recorded_assessments(
                    company_id='marriott_international', ledger=ledger,
                    source_root=source_root)
                self.assertEqual(1, len(collection['completed']))
                self.assertTrue(collection['missing_request_ids'])
                self.assertFalse(collection['native_result_or_run_created'])
                with ledger.locked():
                    counts = ledger.snapshot()['counts']
                self.assertEqual([1, 1, 0], counts)
                with self.assertRaisesRegex(ValueError,
                        'D03_EXTERNAL_REPLAY_EXECUTION_NOT_AUTHORIZED'):
                    execute_feasibility(prepared=replace(selected,
                        replay_only=False), ledger=ledger, recorded_wire=wire)
                with self.assertRaisesRegex(ValueError,
                        'D03_EXTERNAL_REPLAY_EXECUTION_NOT_AUTHORIZED'):
                    execute_feasibility(prepared=replace(selected,
                        replay_only=False, data_root=ROOT, source_ledger=None),
                        ledger=ledger, recorded_wire=wire)
                with self.assertRaisesRegex(ValueError,
                        'D03_REPLAY_ONLY_EXTERNAL_SOURCE_NOT_LEDGER_OWNED'):
                    prepare_d03_replay_only_requests(
                        company_id='marriott_international', source_root=ROOT,
                        source_ledger=ledger)
                with ledger.locked():
                    self.assertEqual(counts, ledger.snapshot()['counts'])
                policy = source_root/'catalog/r6/regulatory_semantic_review_v6.json'
                policy.parent.mkdir(parents=True, exist_ok=True)
                policy.write_text('{}\n')
                with self.assertRaisesRegex(ValueError,
                        'D03_INSTALLED_POLICY_CHANGED'):
                    prepare_d03_replay_only_requests(
                        company_id='marriott_international', source_root=source_root,
                        source_ledger=ledger)
                policy.unlink()
                relative = source['documents'][0]['raw_blob']['storage_uri']
                copied = source_root/relative
                original = ROOT/relative
                original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
                copied.write_bytes(copied.read_bytes() + b' ')
                with self.assertRaisesRegex(BatchWorkflowError,
                        'Request-ledger locator evidence is invalid'):
                    prepare_d03_replay_only_requests(
                        company_id='marriott_international', source_root=source_root,
                        source_ledger=ledger)
                self.assertEqual(original_hash,
                    hashlib.sha256(original.read_bytes()).hexdigest())
                with ledger.locked():
                    self.assertEqual(counts, ledger.snapshot()['counts'])


if __name__ == '__main__':
    unittest.main()
