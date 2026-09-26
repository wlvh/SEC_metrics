"""The explicit C04 update route completes from saved source without egress."""
from pathlib import Path
import copy
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
    def test_saved_marriott_positive_then_unchanged_reuses_run(self):
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
            terminal_path = state/'attempts'/first['successful_attempt']/'terminal.json'
            original_terminal_bytes = terminal_path.read_bytes()
            self.assertEqual(terminal['metrics']['C04']['publication'], 'PUBLISHED')
            configuration = strict_json_file(path=state/'configuration.json')
            self.assertEqual(configuration['route'], update.ROUTE)
            for field, replacement in [('publication', 'WITHHELD'),
                                       ('source_credit', 'FORGED_CREDIT')]:
                changed = copy.deepcopy(terminal)
                changed['metrics']['C04'][field] = replacement
                with self.assertRaisesRegex(ValueError,
                        'C04_UPDATE_SUCCESS_CREDIT_OR_PUBLICATION_CHANGED'):
                    update._verify_candidate(state, changed, configuration)
                body = {key: value for key, value in changed.items()
                        if key != 'record_id'}
                changed['record_id'] = content_hash(value=body)
                terminal_path.write_text(json.dumps(changed, sort_keys=True)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'C04_UPDATE_SUCCESS_CREDIT_OR_PUBLICATION_CHANGED'):
                    update.run_once(state_root=state, source_root=ROOT,
                        company_id='marriott_international')
                terminal_path.write_bytes(original_terminal_bytes)
            with patch.object(normal, 'create_normal_run',
                              side_effect=AssertionError('UNCHANGED_MUST_NOT_RERUN')):
                repeated = update.run_once(state_root=state, source_root=ROOT,
                    company_id='marriott_international')
            self.assertEqual(repeated['status'], 'NO_SOURCE_CONTENT_CHANGE')
            self.assertEqual(repeated['successful_attempt'],
                             first['successful_attempt'])
            self.assertFalse(repeated['new_candidate_created'])

    def test_duplicate_metric_rejected_before_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SystemExit) as caught:
                vnext_normal_update.main(['--process', '--state-root', temporary,
                    '--company', 'marriott_international', '--metric', 'C04',
                    '--metric', 'C04'])
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((Path(temporary)/'marriott_international').exists())


if __name__ == '__main__':
    unittest.main()
