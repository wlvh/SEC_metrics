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
            self.assertNotIn('ordinary_pre_capture_state', plan)
            self.assertNotIn('resume_predecessor', plan)
            with self.assertRaisesRegex(ValueError, 'Immutable receipt bytes differ'):
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'catalog/zero_ai_public_projection.json').write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError, 'Immutable receipt bytes differ'):
                initialize_source_inputs(root=source, requirement=session.requirement,
                                         c04_source_only=True)


class C04MixedSourceRouteMaterialTest(unittest.TestCase):
    def test_historical_b01_pointer_without_new_attempt_can_resume(self):
        from vnext import ordinary_update_cycle as update
        from vnext.ordinary_processing_source import current_processing_source
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
            with session.ledger.locked():
                processing = current_processing_source(acquisition_root=source,
                    output_parent=root/'initial-processing',
                    requirement=session.requirement)
            b01 = update.run_company(state_root=root/'state/marriott_international',
                source_root=processing['data_root'], source_identity_root=source,
                company_id='marriott_international', metric_ids=['B01'],
                native_assessment_mode='RECORDED_TEST_ONLY',
                native_assessment_ledger=session.ledger)
            self.assertEqual('CANDIDATE_READY', b01['metrics'][0]['status'])
            b01_root = root/'state/marriott_international/metrics/B01'
            historical_pointer = (b01_root/'current.json').read_bytes()
            urls = [submissions_url(cik=1048286), companyfacts_url(cik=1048286)]
            with (ROOT/'evidence/requests_log.csv').open(newline='') as handle:
                rows = [row for row in csv.DictReader(handle)
                        if row['status_code'] == '200' and row['source_url'] in urls]
            bodies = {url: (ROOT/next(row['repo_relative_path']
                       for row in reversed(rows) if row['source_url'] == url)).read_bytes()
                      for url in urls}
            captures = []
            native_capture = session.capture
            def capture(**kwargs):
                if len(captures) == 1:
                    with self.assertRaisesRegex(update.OrdinaryUpdateError,
                                                'UPDATE_ALREADY_RUNNING'):
                        with update._locked(root/'state/marriott_international'):
                            pass
                    wrong = dict(kwargs['resume_predecessor'])
                    wrong['counts'] = [0, 0, 0]
                    with self.assertRaisesRegex(ValueError,
                            'SEC_ACQUISITION_RESUME_LEDGER_CHANGED_BEFORE_CLAIM'):
                        native_capture(**{**kwargs, 'resume_predecessor': wrong})
                    with session.ledger.locked():
                        self.assertEqual([0, 0, 1],
                                         session.ledger.snapshot()['counts'])
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
                with patch('vnext.ordinary_processing_source.current_processing_source',
                           side_effect=ValueError('INJECTED_PRIVATE_COPY_FAILURE')):
                    first = refresh.refresh_and_process(session=session,
                        state_root=root/'state',
                        company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True)
                self.assertEqual('FAILED', first['current_processing_source_status'])
                self.assertEqual(['UPDATE_BLOCKED', 'CANDIDATE_READY'],
                    [row['status'] for row in first['companies'][0]['updates']['metrics']])
                self.assertEqual(historical_pointer,
                    (b01_root/'current.json').read_bytes())
                prior = root/'prior-report.json'
                prior.write_text(json.dumps(first, ensure_ascii=False)+'\n')
                changed = json.loads(historical_pointer)
                changed['latest_attempt'] = '0'*32
                (b01_root/'current.json').write_text(json.dumps(changed)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED'):
                    refresh.refresh_and_process(session=session,
                        state_root=root/'state',
                        company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True, resume_from=prior)
                self.assertEqual([urls[0]], captures)
                (b01_root/'current.json').write_bytes(historical_pointer)
                original_resume = refresh._resume_one_c04_source
                resume_checks = [0]
                def mutate_after_first_check(**kwargs):
                    verified = original_resume(**kwargs)
                    resume_checks[0] += 1
                    if resume_checks[0] == 1:
                        (b01_root/'current.json').write_text(json.dumps(changed)+'\n')
                    return verified
                with patch.object(refresh, '_resume_one_c04_source',
                                  side_effect=mutate_after_first_check):
                    with self.assertRaisesRegex(ValueError,
                            'ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED'):
                        refresh.refresh_and_process(session=session,
                            state_root=root/'state',
                            company_ids=['marriott_international'],
                            metric_ids=['B01', 'C04'], max_sec_requests=1,
                            c04_successor=True, resume_from=prior)
                self.assertEqual([urls[0]], captures)
                self.assertEqual(1, resume_checks[0])
                (b01_root/'current.json').write_bytes(historical_pointer)
                c04_current = (root/'state/marriott_international/metrics/'
                    'C04-registration-v3/current.json')
                prior_c04_pointer = c04_current.read_bytes()
                with patch.object(session, 'capture',
                                  side_effect=ValueError('INJECTED_PRECLAIM_REJECTION')):
                    with self.assertRaisesRegex(ValueError,
                            'INJECTED_PRECLAIM_REJECTION'):
                        refresh.refresh_and_process(session=session,
                            state_root=root/'state',
                            company_ids=['marriott_international'],
                            metric_ids=['B01', 'C04'], max_sec_requests=1,
                            c04_successor=True, resume_from=prior)
                self.assertEqual(prior_c04_pointer, c04_current.read_bytes())
                self.assertEqual([urls[0]], captures)
                resumed = refresh.refresh_and_process(session=session,
                    state_root=root/'state',
                    company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True, resume_from=prior)
            self.assertEqual(urls, captures)
            self.assertEqual('UPDATES_READY', resumed['status'])
            self.assertIn(resumed['companies'][0]['updates']['metrics'][0]['status'],
                          {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'})
            with session.ledger.locked():
                self.assertEqual([0, 0, 2], session.ledger.snapshot()['counts'])

    def test_mixed_old_root_resumes_current_rule_metric_and_c04(self):
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
                changed = json.loads(prior.read_text())
                changed['companies'][0]['updates']['metrics'][0]['attempt_id'] = '0'*32
                tampered = root/'tampered-report.json'
                tampered.write_text(json.dumps(changed, ensure_ascii=False)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED'):
                    refresh.refresh_and_process(session=session,
                        state_root=root/'state', company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True, resume_from=tampered)
                changed = json.loads(prior.read_text())
                changed['companies'][0]['updates']['metrics'][0] = {
                    'metric_id': 'B01', 'status': 'UPDATE_BLOCKED',
                    'last_verified_candidate': None,
                    'production_authorized': False}
                downgraded = root/'downgraded-report.json'
                downgraded.write_text(json.dumps(changed, ensure_ascii=False)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED'):
                    refresh.refresh_and_process(session=session,
                        state_root=root/'state', company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True, resume_from=downgraded)
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
            self.assertEqual('UPDATES_READY', resumed['status'])
            self.assertEqual([], resumed['companies'][0]['source_refresh']
                             ['deferred_source_urls'])
            self.assertEqual(['NO_SOURCE_CONTENT_CHANGE', 'NO_SOURCE_CONTENT_CHANGE'],
                [row['status'] for row in resumed['companies'][0]['updates']['metrics']])
            company, = result['companies']
            self.assertEqual('UPDATES_READY', company['updates']['status'])
            self.assertEqual(['CANDIDATE_READY', 'CANDIDATE_READY'],
                [row['status'] for row in company['updates']['metrics']])
            self.assertEqual([], company['acquisition_errors'])
            self.assertTrue(result['current_processing_source_snapshot_id'])
            plan = strict_json_file(path=root/'ledger/calls/0001/sec-plan.json')
            self.assertEqual('C04_REGISTRATION_FOUR_FORM_UPDATE_V1',
                             plan['source_only_processing_route'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 2], session.ledger.snapshot()['counts'])

    def test_failed_processing_copy_preserves_recorded_capture_for_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'config/issue28_normal_results_v2.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
            from vnext import ordinary_update_cycle as update
            b01_root = root/'state/marriott_international/metrics/B01'
            update._config(b01_root, source, 'marriott_international',
                           ['B01'], 'RECORDED_TEST_ONLY')
            self.assertTrue((b01_root/'configuration.json').is_file())
            self.assertFalse((b01_root/'current.json').exists())
            self.assertFalse((b01_root/'attempts').exists())
            urls = [submissions_url(cik=1048286), companyfacts_url(cik=1048286)]
            with (ROOT/'evidence/requests_log.csv').open(newline='') as handle:
                rows = [row for row in csv.DictReader(handle)
                        if row['status_code'] == '200' and row['source_url'] in urls]
            bodies = {url: (ROOT/next(row['repo_relative_path']
                       for row in reversed(rows) if row['source_url'] == url)).read_bytes()
                      for url in urls}
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
                with patch('vnext.ordinary_processing_source.current_processing_source',
                           side_effect=ValueError('INJECTED_PRIVATE_COPY_FAILURE')):
                    first = refresh.refresh_and_process(session=session,
                        state_root=root/'state', company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True)
                self.assertEqual('FAILED', first['current_processing_source_status'])
                self.assertNotIn('current_processing_source_snapshot_id', first)
                self.assertEqual('SUCCEEDED', first['captures'][0]['result']['status'])
                self.assertEqual(['UPDATE_BLOCKED', 'CANDIDATE_READY'],
                    [row['status'] for row in first['companies'][0]['updates']['metrics']])
                self.assertEqual('PROCESSING_SOURCE',
                    first['companies'][0]['acquisition_errors'][0]['stage'])
                prior = root/'failed-copy-report.json'
                prior.write_text(json.dumps(first, ensure_ascii=False)+'\n')
                forged = json.loads(prior.read_text())
                forged['companies'][0]['acquisition_errors'][0]['stage'] = 'SOURCE_SCOPE'
                bad = root/'forged-copy-report.json'
                bad.write_text(json.dumps(forged, ensure_ascii=False)+'\n')
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_REFRESH_RESUME_PROCESSING_FAILURE_INVALID'):
                    refresh.refresh_and_process(session=session,
                        state_root=root/'state', company_ids=['marriott_international'],
                        metric_ids=['B01', 'C04'], max_sec_requests=1,
                        c04_successor=True, resume_from=bad)
                self.assertEqual([urls[0]], captures)
                resumed = refresh.refresh_and_process(session=session,
                    state_root=root/'state', company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True, resume_from=prior)
            self.assertEqual(urls, captures)
            self.assertEqual('READY', resumed['current_processing_source_status'])
            self.assertEqual('UPDATES_READY', resumed['status'])
            self.assertEqual(['CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'],
                [row['status'] for row in resumed['companies'][0]['updates']['metrics']])
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
            self.assertTrue(any(error['stage'] == 'DISCOVERY' for error in
                unrelated['companies'][0]['acquisition_errors']))
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
            self.assertTrue(any(error['stage'] == 'DISCOVERY' for error in
                unrelated['companies'][0]['acquisition_errors']))
            with session.ledger.locked():
                self.assertEqual([0, 0, 0], session.ledger.snapshot()['counts'])


if __name__ == '__main__':
    unittest.main()
