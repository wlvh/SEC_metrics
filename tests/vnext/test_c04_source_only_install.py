"""Old acquisition roots remain immutable while the explicit C04 route reads them."""
from pathlib import Path
import csv
import json
import socket
import tempfile
import unittest
from unittest.mock import patch

from sec_urls import accession_document_url, submissions_url, companyfacts_url

from vnext import normal_run_v3 as normal
from vnext import ordinary_refresh_cycle as refresh
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


class C04MixedSourceRouteMaterialTest(unittest.TestCase):
    def test_mixed_old_root_refreshes_only_c04_and_blocks_other_metrics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'config/issue28_normal_results_v2.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'config/ordinary_public_projection_v1.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
            urls = [submissions_url(cik=1048286), companyfacts_url(cik=1048286)]
            with (ROOT/'evidence/requests_log.csv').open(newline='') as handle:
                rows = [row for row in csv.DictReader(handle)
                        if row['status_code'] == '200' and row['source_url'] in urls]
            bodies = {url: (ROOT/next(row['repo_relative_path']
                       for row in reversed(rows) if row['source_url'] == url)).read_bytes()
                      for url in urls}
            session.response = bodies[urls[0]]
            captures = []
            native_capture = session.capture
            def capture(**kwargs):
                captures.append(kwargs['url'])
                session.response = bodies[kwargs['url']]
                return native_capture(**kwargs)
            with patch.object(socket.socket, 'connect',
                              side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                              side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                       side_effect=AssertionError('HTTP_FORBIDDEN')), \
                 patch.object(session, 'capture', side_effect=capture):
                result = refresh.refresh_and_process(session=session,
                    state_root=root/'state', company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True)
                prior = root/'prior-report.json'
                prior.write_text(json.dumps(result, ensure_ascii=False)+'\n')
                resumed = refresh.refresh_and_process(session=session,
                    state_root=root/'state', company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True, resume_from=prior)
            self.assertEqual(1, len(result['captures']))
            self.assertEqual('SUCCEEDED', result['captures'][0]['result']['status'])
            self.assertEqual(urls, captures)
            self.assertEqual(urls[0], result['captures'][0]['source_url'])
            self.assertEqual(urls[1], resumed['captures'][0]['source_url'])
            self.assertTrue(result['c04_mixed_source_only'])
            self.assertTrue(resumed['c04_mixed_source_only'])
            self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, result['calls'])
            self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, resumed['calls'])
            self.assertEqual('UPDATES_INCOMPLETE', resumed['status'])
            self.assertEqual([], resumed['companies'][0]['source_refresh']
                             ['deferred_source_urls'])
            self.assertEqual(['UPDATE_BLOCKED', 'NO_SOURCE_CONTENT_CHANGE'],
                [row['status'] for row in resumed['companies'][0]['updates']['metrics']])
            company, = result['companies']
            self.assertEqual('UPDATES_PARTIAL', company['updates']['status'])
            self.assertEqual(['UPDATE_BLOCKED', 'CANDIDATE_READY'],
                [row['status'] for row in company['updates']['metrics']])
            self.assertEqual('SOURCE_SCOPE', company['acquisition_errors'][0]['stage'])
            plan = strict_json_file(path=root/'ledger/calls/0001/sec-plan.json')
            self.assertEqual('C04_REGISTRATION_FOUR_FORM_UPDATE_V1',
                             plan['source_only_processing_route'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 2], session.ledger.snapshot()['counts'])

    def test_mixed_old_root_does_not_capture_unproved_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'config/issue28_normal_results_v2.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            unproved = {'source_url': 'https://www.sec.gov/Archives/unproved.json',
                'refresh_for_new_discovery': True, 'saved_status': 'MISSING_SAVED_SOURCE'}
            with patch.object(refresh, '_pending', return_value=[unproved]), \
                 patch.object(session, 'capture',
                              side_effect=AssertionError('UNPROVED_SOURCE_CLAIMED')):
                result = refresh.refresh_and_process(session=session,
                    state_root=root/'state', company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True)
            self.assertEqual([], result['captures'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 0], session.ledger.snapshot()['counts'])


class C04MixedSourceScopeFastTest(unittest.TestCase):
    def test_current_proof_and_c04_role_are_both_required(self):
        proofs = [{'source_url': 'https://example.test/companyfacts'},
                  {'source_url': 'https://example.test/proxy'}]
        pending = [{'source_url': 'https://example.test/companyfacts',
                    'roles': ['companyfacts']},
                   {'source_url': 'https://example.test/proxy',
                    'roles': ['proxy_primary']},
                   {'source_url': 'https://example.test/unproved',
                    'roles': ['fiscal_event_primary']}]
        self.assertEqual([pending[0]],
            refresh._c04_mixed_pending(pending, proofs))

    def test_verified_submissions_can_name_one_missing_current_annual(self):
        cik = 1048286
        accession = '0001048286-27-000001'
        document = 'new-annual.htm'
        url = accession_document_url(cik=cik, accession=accession,
                                     document_name=document)
        annual = {'source_url': url, 'roles': ['current_annual_primary'],
                  'saved_status': 'MISSING_SAVED_SOURCE'}
        inventory = {'source_url': submissions_url(cik=cik),
                     'roles': ['sec_submissions_inventory'],
                     'saved_status': 'VERIFIED_SAVED_SOURCE', 'proof': {}}
        discovery = {'primary_cik': str(cik),
                     'metadata_declared_annual_selection': {'filing': {
                         'form': '10-K', 'accessionNumber': accession,
                         'primaryDocument': document}},
                     'requirements': [inventory, annual]}
        self.assertEqual([annual],
            refresh._c04_missing_current_annual([annual], discovery))
        self.assertEqual([], refresh._c04_missing_current_annual(
            [dict(annual, roles=['proxy_primary'])], discovery))
        self.assertEqual([], refresh._c04_missing_current_annual(
            [dict(annual, source_url=url+'-other')], discovery))
        self.assertEqual([], refresh._c04_missing_current_annual(
            [annual], {**discovery, 'requirements': [
                {**inventory, 'saved_status': 'SAVED_SOURCE_BLOCKED'}, annual]}))


class C04MissingAnnualBootstrapFastTest(unittest.TestCase):
    def test_declared_missing_annual_reaches_source_only_capture(self):
        cik = 1048286
        accession = '0001048286-27-000001'
        annual_url = accession_document_url(cik=cik, accession=accession,
                                            document_name='new-annual.htm')
        discovery = {'record_type': 'ORDINARY_SOURCE_REQUIREMENTS',
            'company_id': 'marriott_international', 'primary_cik': str(cik),
            'requirements_id': 'recorded-discovery',
            'status': 'METADATA_REFRESH_REQUIRED', 'limitations': [],
            'metadata_declared_annual_selection': {'filing': {
                'form': '10-K', 'accessionNumber': accession,
                'primaryDocument': 'new-annual.htm'}},
            'requirements': [
                {'source_url': submissions_url(cik=cik),
                 'roles': ['sec_submissions_inventory'],
                 'saved_status': 'VERIFIED_SAVED_SOURCE',
                 'refresh_for_new_discovery': True, 'proof': {}},
                {'source_url': annual_url, 'roles': ['current_annual_primary'],
                 'saved_status': 'MISSING_SAVED_SOURCE',
                 'refresh_for_new_discovery': False}]}
        captured = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            def capture(**kwargs):
                captured.append(kwargs)
                return {'status': 'SUCCEEDED', 'calls': [0, 0, 0]}
            with patch.object(refresh, '_check_session'), \
                 patch.object(refresh, 'initialize_source_inputs'), \
                 patch.object(refresh, '_historical_c04_processing_copies',
                              return_value=True), \
                 patch.object(refresh, '_failed_urls', return_value=set()), \
                 patch.object(refresh, 'discover_saved_source_requirements',
                              return_value=discovery), \
                 patch('vnext.normal_run_v3.prepare_case',
                       side_effect=ValueError('SAVED_SOURCE_MISSING:' + annual_url)), \
                 patch.object(session, 'capture', side_effect=capture), \
                 patch('vnext.c04_update_cycle.run_company', return_value={
                     'metrics': [{'metric_id': 'C04', 'status': 'UPDATE_BLOCKED'}]}):
                result = refresh.refresh_and_process(session=session,
                    state_root=root/'state',
                    company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True)
                with patch('vnext.normal_run_v3.prepare_case',
                           side_effect=ValueError('UNRELATED_SOURCE_CONFLICT')):
                    unrelated = refresh.refresh_and_process(session=session,
                        state_root=root/'state',
                        company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True)
            self.assertEqual([annual_url], [item['url'] for item in captured])
            self.assertEqual([True], [item['source_only_c04'] for item in captured])
            self.assertEqual('UPDATES_INCOMPLETE', result['status'])
            self.assertEqual('DISCOVERY', unrelated['companies'][0]
                             ['acquisition_errors'][-1]['stage'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 0], session.ledger.snapshot()['counts'])

    def test_authenticated_resume_mock_can_capture_declared_missing_annual(self):
        cik = 1048286
        accession = '0001048286-27-000001'
        annual_url = accession_document_url(cik=cik, accession=accession,
                                            document_name='new-annual.htm')
        inventory_url = submissions_url(cik=cik)
        discovery = {'record_type': 'ORDINARY_SOURCE_REQUIREMENTS',
            'company_id': 'marriott_international', 'primary_cik': str(cik),
            'requirements_id': 'recorded-discovery',
            'status': 'METADATA_REFRESH_REQUIRED', 'limitations': [],
            'metadata_declared_annual_selection': {'filing': {
                'form': '10-K', 'accessionNumber': accession,
                'primaryDocument': 'new-annual.htm'}},
            'requirements': [
                {'source_url': inventory_url,
                 'roles': ['sec_submissions_inventory'],
                 'saved_status': 'VERIFIED_SAVED_SOURCE',
                 'refresh_for_new_discovery': True, 'proof': {}},
                {'source_url': annual_url, 'roles': ['current_annual_primary'],
                 'saved_status': 'MISSING_SAVED_SOURCE',
                 'refresh_for_new_discovery': False}]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            with session.ledger.locked():
                snapshot = session.ledger.snapshot()
            prior = {'prior_source_url': inventory_url,
                'allowed_next_urls': [annual_url], 'prior_ordinal': 0,
                'prior_intent_id': snapshot['previous_intent_id'],
                'source_ledger_sha256': 'recorded-source-ledger'}
            captured = []
            def capture(**kwargs):
                captured.append(kwargs)
                return {'status': 'SUCCEEDED', 'calls': [0, 0, 0]}
            with patch.object(refresh, '_check_session'), \
                 patch.object(refresh, 'initialize_source_inputs'), \
                 patch.object(refresh, '_historical_c04_processing_copies',
                              return_value=True), \
                 patch.object(refresh, '_failed_urls', return_value=set()), \
                 patch.object(refresh, 'discover_saved_source_requirements',
                              return_value=discovery), \
                 patch.object(refresh, '_resume_one_c04_source',
                              return_value=prior), \
                 patch.object(refresh, 'sha256_file',
                              return_value='recorded-source-ledger'), \
                 patch('vnext.normal_run_v3.prepare_case',
                       side_effect=ValueError('SAVED_SOURCE_MISSING:' + annual_url)), \
                 patch.object(session, 'capture', side_effect=capture), \
                 patch('vnext.c04_update_cycle.run_company', return_value={
                     'metrics': [{'metric_id': 'C04', 'status': 'UPDATE_BLOCKED'}]}):
                result = refresh.refresh_and_process(session=session,
                    state_root=root/'state',
                    company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True, resume_from=root/'prior-report.json')
                with patch('vnext.normal_run_v3.prepare_case',
                           side_effect=ValueError('UNRELATED_SOURCE_CONFLICT')):
                    unrelated = refresh.refresh_and_process(session=session,
                        state_root=root/'state',
                        company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True, resume_from=root/'prior-report.json')
            self.assertEqual([annual_url], [item['url'] for item in captured])
            self.assertEqual([True], [item['source_only_c04'] for item in captured])
            self.assertEqual('UPDATES_INCOMPLETE', result['status'])
            self.assertEqual('DISCOVERY', unrelated['companies'][0]
                             ['acquisition_errors'][-1]['stage'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 0], session.ledger.snapshot()['counts'])


if __name__ == '__main__':
    unittest.main()
