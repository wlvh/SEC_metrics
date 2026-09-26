"""The explicit C04 update route completes from saved source without egress."""
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext import c04_update_cycle as update
from vnext import normal_run_v3 as normal
from vnext.canonical import strict_json_file
from vnext.normal_source_authority import ROOT


class C04UpdateCycleMaterialTest(unittest.TestCase):
    def test_saved_marriott_positive_then_unchanged_reuses_run(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')):
            state = Path(temporary)/'c04'
            first = update.run_once(state_root=state, source_root=ROOT,
                company_id='marriott_international')
            self.assertEqual(first['status'], 'CANDIDATE_READY')
            self.assertIsNotNone(first['successful_attempt'])
            terminal = strict_json_file(path=state/'attempts'/
                first['successful_attempt']/'terminal.json')
            self.assertEqual(terminal['metrics']['C04']['publication'], 'PUBLISHED')
            configuration = strict_json_file(path=state/'configuration.json')
            self.assertEqual(configuration['route'], update.ROUTE)
            with patch.object(normal, 'create_normal_run',
                              side_effect=AssertionError('UNCHANGED_MUST_NOT_RERUN')):
                repeated = update.run_once(state_root=state, source_root=ROOT,
                    company_id='marriott_international')
            self.assertEqual(repeated['status'], 'NO_SOURCE_CONTENT_CHANGE')
            self.assertEqual(repeated['successful_attempt'],
                             first['successful_attempt'])
            self.assertFalse(repeated['new_candidate_created'])


if __name__ == '__main__':
    unittest.main()
