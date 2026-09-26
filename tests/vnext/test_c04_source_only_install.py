"""Old acquisition roots remain immutable while the explicit C04 route reads them."""
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sec_urls import submissions_url

from vnext import normal_run_v3 as normal
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.continuous_sec_acquisition import (
    initialize_source_inputs, recorded_sec_session)
from vnext.canonical import strict_json_file
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import ROOT


class C04SourceOnlyInstallTest(unittest.TestCase):
    def test_old_processing_files_remain_old_and_unrelated_drift_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            stale = ('config/issue28_normal_results_v2.json',
                     'config/ordinary_public_projection_v1.json')
            for name in stale:
                (source/name).write_bytes(b'{"historical_processing_copy":true}\n')
            (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
            initialize_source_inputs(root=source, requirement=session.requirement,
                                     c04_source_only=True)
            self.assertTrue(all((source/name).read_bytes() ==
                b'{"historical_processing_copy":true}\n' for name in stale))
            self.assertFalse((source/'catalog/r5/C04_auditor_changes_v3.md').exists())
            case = normal.prepare_case(data_root=source,
                company_id='marriott_international', metric_id='C04',
                c04_event_forms=EVENT_FORMS)
            self.assertEqual('PUBLISHED', case['results']['C04']['publication'])
            url = submissions_url(cik=1048286)
            session.response = _Sources(ROOT, 'marriott_international', '1048286').read(
                url, role='sec_submissions_inventory',
                media_type='application/json')['raw_bytes']
            with patch.object(socket.socket, 'connect',
                              side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                              side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                       side_effect=AssertionError('HTTP_FORBIDDEN')):
                captured = session.capture(company_id='marriott_international',
                    url=url, refresh_metadata=True, source_only_c04=True)
            self.assertEqual('SUCCEEDED', captured['status'])
            self.assertEqual([0, 0, 0], captured['calls'])
            plan = strict_json_file(path=root/'ledger/calls/0001/sec-plan.json')
            self.assertEqual('C04_REGISTRATION_FOUR_FORM_UPDATE_V1',
                             plan['source_only_processing_route'])
            with self.assertRaisesRegex(ValueError, 'Immutable receipt bytes differ'):
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'catalog/zero_ai_public_projection.json').write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError, 'Immutable receipt bytes differ'):
                initialize_source_inputs(root=source, requirement=session.requirement,
                                         c04_source_only=True)


if __name__ == '__main__':
    unittest.main()
