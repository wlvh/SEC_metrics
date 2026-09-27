"""The explicit C04 update route completes from saved source without egress."""
from pathlib import Path
import json
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext import c04_update_cycle as update
from vnext import normal_run_v3 as normal
from vnext.canonical import content_hash, strict_json_file
from vnext.normal_source_authority import ROOT
from tools import vnext_normal_update


class C04UpdateCycleMaterialTest(unittest.TestCase):
    def test_saved_marriott_positive_creates_native_result(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')):
            state = (Path(temporary)/'c04').resolve()
            first = update.run_once(state_root=state, source_root=ROOT,
                company_id='marriott_international')
            self.assertEqual(first['status'], 'CANDIDATE_READY')
            self.assertIsNotNone(first['successful_attempt'])
            terminal = strict_json_file(path=state/'attempts'/
                first['successful_attempt']/'terminal.json')
            self.assertEqual(terminal['metrics']['C04']['publication'], 'PUBLISHED')
            self.assertEqual(terminal['metrics']['C04']['result_id'],
                first['last_verified_candidate']['results']['C04']['result_id'])
            configuration = strict_json_file(path=state/'configuration.json')
            self.assertEqual(configuration['route'], update.ROUTE)

            # Simulate a completed terminal whose pointer write was interrupted.
            # C04 credit must be checked before recovery makes it current.
            pointer = state/'current.json'
            pointer.unlink()
            terminal_path = state/'attempts'/first['successful_attempt']/'terminal.json'
            original_terminal = terminal_path.read_bytes()
            forged = json.loads(original_terminal)
            forged['metrics']['C04']['source_credit'] = 'FORGED_CREDIT'
            forged['record_id'] = content_hash(value={key: value for key, value
                in forged.items() if key != 'record_id'})
            terminal_path.write_text(json.dumps(forged) + '\n')
            with self.assertRaisesRegex(ValueError,
                    'C04_UPDATE_SUCCESS_CREDIT_OR_PUBLICATION_CHANGED'):
                update.run_once(state_root=state, source_root=ROOT,
                    company_id='marriott_international')
            self.assertFalse(pointer.exists())
            terminal_path.write_bytes(original_terminal)
            with update.cycle._locked(state):
                restored = update.cycle._recover(state,
                    update.cycle._state(state, configuration), configuration,
                    verify_candidate=update._verify_candidate)
            self.assertEqual(restored['successful_attempt'], first['successful_attempt'])
            self.assertEqual(json.loads(pointer.read_text())['successful_attempt'],
                first['successful_attempt'])
            self.assertEqual(len(list((state/'attempts').iterdir())), 1)

    def test_duplicate_metric_rejected_before_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SystemExit) as caught:
                vnext_normal_update.main(['--process', '--state-root', temporary,
                    '--company', 'marriott_international', '--metric', 'C04',
                    '--metric', 'C04'])
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((Path(temporary)/'marriott_international').exists())


class C04UpdateCreditBoundaryTest(unittest.TestCase):
    def test_resigned_terminal_cannot_change_publication_or_source_credit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work = root/'attempts'/('a'*32)
            (work/'runs/C04').mkdir(parents=True)
            (work/'data'/normal.BINDING_DIRECTORY).mkdir(parents=True)
            (work/'runs/C04/manifest.json').write_text(json.dumps({
                'run_id': normal.PREFIX + 'receipt'}) + '\n')
            (work/'data'/normal.BINDING_DIRECTORY/'receipt.json').write_text(
                json.dumps({'source_admission': {'source_credit': 'VERIFIED'}}) + '\n')
            terminal = {'attempt_id': 'a'*32, 'metrics': {'C04': {
                'result_id': 'result', 'publication': 'PUBLISHED',
                'source_credit': 'VERIFIED', 'files': {}}}}
            replayed = {'C04': {'publication': 'PUBLISHED'}}
            with patch.object(update.cycle, '_verify_candidate', return_value=replayed):
                self.assertEqual(update._verify_candidate(root, terminal, {}), replayed)
                for field, replacement in [('publication', 'WITHHELD'),
                                           ('source_credit', 'FORGED_CREDIT')]:
                    changed = json.loads(json.dumps(terminal))
                    changed['metrics']['C04'][field] = replacement
                    with self.assertRaisesRegex(ValueError,
                            'C04_UPDATE_SUCCESS_CREDIT_OR_PUBLICATION_CHANGED'):
                        update._verify_candidate(root, changed, {})


if __name__ == '__main__':
    unittest.main()
