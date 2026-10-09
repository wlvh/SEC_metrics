"""Two complete saved metadata versions through the same finite coordinator."""
import json
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from sec_urls import submissions_url
from vnext import ordinary_refresh_cycle as refresh
from vnext.canonical import sha256_bytes
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import ROOT


@unittest.skipUnless(os.environ.get('ORDINARY_REFRESH_EXISTING_MATERIAL'), 'Requires completed acquisition material')
class OrdinaryRefreshContentChangeTest(unittest.TestCase):
    def test_actual_metadata_change_creates_candidate_and_then_reuses_it(self):
        root = Path(os.environ['ORDINARY_REFRESH_EXISTING_MATERIAL']).resolve()
        state = root / 'state-metadata-change'; self.assertFalse(state.exists())
        url = submissions_url(cik=19617); company = 'jpmorgan_chase'
        latest_root = Path(os.environ.get('ORDINARY_REFRESH_ORIGINALS_ROOT',
            '/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')).resolve()
        sources = [_Sources(where, company, '19617').read(url, role='sec_submissions_inventory',
            media_type='application/json')['raw_bytes'] for where in (ROOT, latest_root)]
        self.assertNotEqual(sources[0], sources[1])
        session = recorded_sec_session(root=root / 'ledger', response=sources[0])
        capture = session.capture; returned = []

        def reply(**kwargs):
            self.assertEqual(url, kwargs['url'])
            self.assertTrue(kwargs['refresh_metadata'])
            return capture(**kwargs)

        with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN')), \
             patch.object(session, 'capture', side_effect=reply):
            for name, body, maximum in [('older-saved-metadata', sources[0], 1),
                                        ('newer-saved-metadata', sources[1], 1),
                                        ('unchanged-saved-metadata', sources[1], 0)]:
                session.response = body
                result = refresh.refresh_and_process(session=session, state_root=state, company_ids=[company],
                    metric_ids=['B01'], max_sec_requests=maximum)
                path = root / (name + '.json'); self.assertFalse(path.exists())
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
                self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, result['calls'])
                returned.append(result['companies'][0]['updates']['metrics'][0])
        first, changed, repeated = returned
        self.assertEqual(['CANDIDATE_READY', 'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'],
                         [row['status'] for row in returned])
        self.assertNotEqual(first['successful_attempt'], changed['successful_attempt'])
        self.assertEqual(changed['successful_attempt'], repeated['successful_attempt'])
        self.assertEqual(first['last_verified_candidate']['results']['B01']['value'],
                         changed['last_verified_candidate']['results']['B01']['value'])
        (root / 'metadata-change-summary.json').write_text(json.dumps({'status': 'PASS',
            'source_versions': [sha256_bytes(content=body) for body in sources],
            'successful_attempts': [row['successful_attempt'] for row in returned],
            'same_value_new_source_candidate': True, 'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'recorded_sec_slots_added': 2, 'actual_new_fiscal_year': False,
            'source_credit': 'RECORDED_TEST_ONLY', 'production_authorized': False}, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
