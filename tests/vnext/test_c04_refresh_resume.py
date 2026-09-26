"""One prior authenticated C04 SEC capture can continue without redrawing it."""
import csv
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sec_urls import companyfacts_url, submissions_url
from vnext import ordinary_refresh_cycle as refresh
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_source_authority import ROOT


class C04RefreshResumeMaterialTest(unittest.TestCase):
    def test_one_prior_source_skipped_only_with_exact_ledger_and_history(self):
        urls = [submissions_url(cik=1048286), companyfacts_url(cik=1048286)]
        with (ROOT/'evidence/requests_log.csv').open(newline='') as handle:
            rows = [row for row in csv.DictReader(handle)
                    if row['status_code'] == '200' and row['source_url'] in urls]
        bodies = {url: (ROOT/next(row['repo_relative_path'] for row in reversed(rows)
                              if row['source_url'] == url)).read_bytes()
                  for url in urls}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=bodies[urls[0]])
            state = root/'state'
            captured = []
            native_capture = session.capture
            def capture(**kwargs):
                captured.append(kwargs['url'])
                session.response = bodies[kwargs['url']]
                return native_capture(**kwargs)
            def advance(resume=None):
                return refresh.refresh_and_process(session=session, state_root=state,
                    company_ids=['marriott_international'], metric_ids=['C04'],
                    max_sec_requests=1, c04_successor=True, resume_from=resume)
            with patch.object(socket.socket, 'connect',
                              side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                              side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                       side_effect=AssertionError('HTTP_FORBIDDEN')), \
                 patch.object(session, 'capture', side_effect=capture):
                first = advance()
                self.assertEqual([urls[0]], captured)
                self.assertEqual('UPDATES_INCOMPLETE', first['status'])
                prior = root/'prior-report.json'
                prior.write_text(json.dumps(first, ensure_ascii=False)+'\n')
                altered = json.loads(prior.read_text())
                altered['captures'][0]['source_url'] = urls[1]
                forged = root/'forged-report.json'
                forged.write_text(json.dumps(altered, ensure_ascii=False)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_SEC_SOURCE_CHANGED'):
                    advance(forged)
                altered = json.loads(prior.read_text())
                altered['companies'][0]['source_refresh'][
                    'deferred_source_urls'].append(urls[0])
                forged_deferred = root/'forged-deferred-report.json'
                forged_deferred.write_text(json.dumps(altered, ensure_ascii=False)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_DEFERRED_SET_CHANGED'):
                    advance(forged_deferred)
                self.assertEqual([urls[0]], captured)
                second = advance(prior)
                self.assertEqual(urls, captured)
                self.assertEqual('UPDATES_READY', second['status'])
                self.assertEqual(urls[0],
                    second['resumed_c04_source']['prior_source_url'])
                self.assertEqual(urls[1], second['captures'][0]['source_url'])
                self.assertIn(second['companies'][0]['updates']['metrics'][0]['status'],
                    {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'})
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_PREDECESSOR_INVALID'):
                    advance(prior)
            with session.ledger.locked():
                self.assertEqual([0, 0, 2], session.ledger.snapshot()['counts'])


if __name__ == '__main__':
    unittest.main()
