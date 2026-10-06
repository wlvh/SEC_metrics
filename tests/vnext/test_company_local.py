"""Local orchestration boundaries; simulated stages are not SEC acceptance."""
from copy import deepcopy
from contextlib import contextmanager
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext import company_local as local
from scripts.vnext import company_local_acquisition as acquisition
from scripts.vnext import continuous_sec_acquisition as capture
from scripts.vnext import normal_source_requirements as discovery
from scripts.vnext.publication import METRIC_FIELDS, _csv_bytes
from scripts.sec_http import SecHttpClient


class Ledger:
    def __init__(self):
        self.count = 0
        self.live = False

    @contextmanager
    def locked(self):
        yield

    def snapshot(self):
        return {'counts': [0, 0, self.count]}


class CompanyLocalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_local_reader_selects_only_the_existing_exact_native_specs(self):
        self.assertTrue(local.native_run({'spec_file_hashes':{'catalog/r5/B13_capacity_disclosures_v1.md':'hash'}}))
        self.assertFalse(local.native_run({'spec_file_hashes':{'catalog/metrics/B01_revenue.md':'hash'}}))
        self.assertFalse(local.native_run({'spec_file_hashes':{
            'catalog/r5/B13_capacity_disclosures_v1.md':'hash','catalog/metrics/B01_revenue.md':'hash'}}))
        self.assertFalse(local.native_run({'spec_file_hashes':{'catalog/fake/B13.md':'hash'}}))

    def test_ordinary_initial_empty_manifest_hash_does_not_claim_records_are_invalid(self):
        from scripts.vnext.company_result_view import _measurement_period
        from scripts.vnext.canonical import sha256_bytes
        record = _measurement_period({'rows_root':str(self.root/'rows'),'metric_id':'B01'},
            {'record_type':'SUCCESSOR_RUN','records_file_hash':sha256_bytes(content=b'')})
        self.assertEqual(record, {'measurement_period':None,'measurement_period_status':'NOT_AVAILABLE'})

    def test_relative_alias_rejected_before_resolving(self):
        target = self.root/'target'
        target.mkdir()
        alias = self.root/'alias'
        alias.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'LOCAL_PATH_ALIAS'):
            local.absolute(alias/'new')

    def test_acquire_only_refreshes_once_and_respects_cap(self):
        class Session:
            def __init__(inner):
                inner.data_root = self.root/'sources'
                inner.ledger = Ledger()
                inner.requirement = {}
                inner.urls = []

            def capture(inner, **kw):
                inner.urls.append(kw['url'])
                inner.ledger.count += 1
                return {'status': 'SUCCEEDED', 'calls': [0, 0, 0], 'receipt': {'stop_reason': ''}}

        session = Session()
        SecHttpClient(workdir=session.data_root,
            config_path=local.ROOT/'config/sec_config.json',
            log_path=session.data_root/'evidence/requests_log.csv')

        def discover(**kw):
            seen = session.urls
            return {'requirements': [
                {'source_url': 'metadata', 'roles': ['sec_submissions_inventory'],
                 'refresh_for_new_discovery': True,
                 'saved_status': 'VERIFIED_SAVED_SOURCE' if 'metadata' in seen else 'MISSING_SAVED_SOURCE'},
                {'source_url': 'annual', 'roles': ['current_annual_primary'],
                 'refresh_for_new_discovery': False,
                 'saved_status': 'VERIFIED_SAVED_SOURCE' if 'annual' in seen else 'MISSING_SAVED_SOURCE'}], 'limitations': []}

        with patch.object(capture, 'initialize_source_inputs'), \
                patch.object(discovery, 'discover_saved_source_requirements', side_effect=discover):
            report = acquisition.acquire_only(session=session, company_id='company', max_requests=1)
        self.assertEqual(session.urls, ['metadata'])
        self.assertEqual(report['stop_reason'], 'INVOCATION_SEC_LIMIT_REACHED')
        self.assertEqual(report['calls']['sec'], 0)
        self.assertEqual(report['simulated_sec_claims'], 1)
        self.assertFalse(report['metric_executed'])

    def test_forbidden_or_rate_limited_capture_stops_and_remains_stopped(self):
        for code in ('403', '429'):
            with self.subTest(code=code):
                source = self.root/code
                client = SecHttpClient(workdir=source, config_path=local.ROOT/'config/sec_config.json',
                    log_path=source/'evidence/requests_log.csv')
                session = type('Session', (), {})()
                session.data_root, session.requirement, session.ledger = source, {}, Ledger()
                urls = []

                def blocked_capture(**kw):
                    urls.append(kw['url'])
                    session.ledger.count += 1
                    response = client._persist_result(url=kw['url'], status_code=int(code),
                        body=b'blocked', headers={'Content-Type': 'text/plain'},
                        local_path=source/'blocked-response.txt', error='HTTP '+code)
                    client._append_log_row(result=response, purpose='RECORDED_BLOCKED_TEST', attempt=0)
                    return {'status': 'FAILED_TERMINAL', 'calls': [0, 0, 0],
                        'receipt': {'stop_reason': '', 'ledger_row': {'status_code': code}}}

                session.capture = blocked_capture
                discovery_report = {'requirements': [
                    {'source_url': u, 'roles': [], 'refresh_for_new_discovery': True,
                     'saved_status': 'MISSING_SAVED_SOURCE'} for u in (
                         'https://data.sec.gov/submissions/CIK0001048286.json',
                         'https://data.sec.gov/api/xbrl/companyfacts/CIK0001048286.json')],
                    'limitations': []}
                with patch.object(capture, 'initialize_source_inputs'), \
                        patch.object(discovery, 'discover_saved_source_requirements', return_value=discovery_report):
                    first = acquisition.acquire_only(session=session, company_id='company', max_requests=120)
                    self.assertEqual(first['stop_reason'], 'HTTP_'+code)
                    self.assertEqual(urls, ['https://data.sec.gov/submissions/CIK0001048286.json'])
                    repeat = acquisition.acquire_only(session=session, company_id='company', max_requests=120)
                    self.assertEqual(repeat['stop_reason'], 'HTTP_'+code)
                    self.assertEqual(urls, ['https://data.sec.gov/submissions/CIK0001048286.json'])
                    self.assertEqual(repeat['charged_sec_claims'], 0)

    def test_run_has_one_compute_and_complete_status_scope(self):
        program = self.root/'program'
        program.mkdir()
        work, output = self.root/'work', self.root/'output'
        calls = []
        checkpoint = 'sha256:installed-source-version'

        def invoke(program, args, **kw):
            calls.append(args[0])
            if args[0] == 'acquire':
                result = {'record_type': 'LOCAL_COMPANY_ACQUISITION_V1',
                    'status': 'SOURCES_READY', 'calls': {'provider': 0, 'paid': 0, 'sec': 2},
                    'captures': [], 'discovery': {}}
            elif args[0] == 'compute':
                result = {'metrics': [{'metric_id': 'B01', 'status': 'CANDIDATE_READY'},
                    {'metric_id': 'D01', 'status': 'INPUT_FAILED'}]}
            elif args[0] == 'results':
                self.assertEqual(program, local.ROOT)
                destination = Path(args[args.index('--output-root')+1])
                destination.mkdir(parents=True)
                matrix = [{**dict.fromkeys(METRIC_FIELDS, ''), 'metric_id': 'B01', 'value': '10', 'status': 'EXACT'}]
                (destination/'metrics_matrix.csv').write_bytes(_csv_bytes(rows=matrix, fieldnames=METRIC_FIELDS))
                (destination/'metric_evidence.csv').write_text('metric_id\nB01\n')
                (destination/'company-results.json').write_text(json.dumps({'source_checkpoint_id': checkpoint}))
                result = {'status': 'EXPORTED'}
            elif args[0] == 'install':
                source_state = work/'company-state'
                source_state.mkdir()
                (source_state/'current_source.json').write_text(json.dumps({'checkpoint_id': checkpoint}))
                result = {'status': 'OK'}
            else:
                result = {'status': 'OK'}
            return {'returncode': 2 if args[0] == 'compute' else 0, 'result': result}

        with patch.object(local, 'prepare_program', return_value=program), \
                patch.object(local, '_invoke', side_effect=invoke):
            # The managed program list is used solely for exact-version readback.
            (work/'programs/program').mkdir(parents=True)
            result = local.run_local(company_id='marriott_international', work_dir=work,
                output_dir=output, metric_ids=['B01', 'D01', 'D03'])
        self.assertEqual(calls, ['acquire', 'export', 'install', 'compute', 'results'])
        saved_summary = json.loads(Path(result['outputs']['run_summary.json']).read_text())
        view = json.loads((Path(result['output_root'])/'company-results.json').read_text())
        installed = json.loads((work/'company-state/current_source.json').read_text())
        self.assertEqual(saved_summary['source_checkpoint_id'], view['source_checkpoint_id'])
        self.assertEqual(saved_summary['source_checkpoint_id'], installed['checkpoint_id'])
        self.assertEqual(len(result['metrics']), 39)
        self.assertEqual(next(r for r in result['metrics'] if r['metric_id'] == 'D03')['status'], 'IMPLEMENTATION_GAP')
        self.assertFalse(result['all_configured_business_metrics_completed'])
        with Path(result['outputs']['metrics_matrix.csv']).open(encoding='utf-8-sig') as stream:
            table = list(csv.DictReader(stream))
        self.assertEqual(len({r['metric_id'] for r in table}), 39)
        self.assertTrue(all(r['company_id'] == 'marriott_international' for r in table))
        self.assertTrue(all(r['company'] == 'Marriott International' for r in table if r['metric_id'] != 'B01'))
        self.assertEqual(table[0]['value'], '10')

    def test_acquisition_crash_cannot_be_reported_as_complete(self):
        program = self.root/'program'
        program.mkdir()
        with patch.object(local, 'prepare_program', return_value=program), \
                patch.object(local, '_invoke', return_value={'returncode': 1,
                    'result': {'status': 'STAGE_FAILED', 'reason': 'capture failed'}}) as invoked:
            result = local.run_local(company_id='marriott_international', work_dir=self.root/'work',
                                     output_dir=self.root/'output')
        self.assertEqual(invoked.call_count, 1)
        self.assertEqual(result['status'], 'FLOW_INCOMPLETE')
        self.assertEqual(len(result['metrics']), 39)
        self.assertEqual(result['failure']['reason'], 'LOCAL_SOURCE_ACQUISITION_STAGE_FAILED')

    def test_non_latest_period_fails_before_any_egress_or_output(self):
        with patch.object(local, '_invoke') as invoked:
            with self.assertRaisesRegex(ValueError, 'LOCAL_PERIOD_NOT_IMPLEMENTED'):
                local.run_local(company_id='marriott_international', work_dir=self.root/'work',
                    output_dir=self.root/'output', period='2020')
        invoked.assert_not_called()
        self.assertFalse((self.root/'output').exists())

    def test_acquire_and_run_keep_the_same_program_and_allowance(self):
        work = self.root/'work'
        work.mkdir()
        program = work/'programs/fixed'
        (program/'requirements/issue_54_v4').mkdir(parents=True)
        with patch.object(local, 'prepare_program', return_value=program):
            self.assertEqual(local.configure_task(work, 'marriott_international', 120), program)
            configuration = work/'local-company.json'
            saved = json.loads(configuration.read_text())
            saved['preparation_program_root'] = str(work/'programs/fixed-preparer')
            configuration.write_text(json.dumps(saved))
            local.configure_task(work, 'marriott_international', 120)
            self.assertEqual(json.loads(configuration.read_text())['preparation_program_root'],
                             saved['preparation_program_root'])
        with patch.object(local, 'prepare_program') as changed:
            with self.assertRaisesRegex(ValueError, 'COMPANY_OR_ALLOWANCE_CHANGED'):
                local.configure_task(work, 'marriott_international', 119)
            with self.assertRaisesRegex(ValueError, 'COMPANY_OR_ALLOWANCE_CHANGED'):
                local.configure_task(work, 'enphase_energy', 120)
            changed.assert_not_called()
        self.assertEqual(local.prepare_program(work), program)

    def test_acquisition_failure_exports_old_native_result_without_current_success(self):
        work = self.root/'work'
        (work/'programs/program').mkdir(parents=True)
        (work/'company-state').mkdir()
        (work/'company-state/current_source.json').write_text('{}')
        calls = []

        def invoke(program, args, **kw):
            calls.append(args[0])
            if args[0] == 'acquire':
                return {'returncode': 1, 'result': {'status': 'STAGE_FAILED'}}
            self.assertEqual(args[0], 'results')
            self.assertEqual(program, local.ROOT)
            dest = Path(args[args.index('--output-root')+1])
            dest.mkdir(parents=True)
            row = {**dict.fromkeys(METRIC_FIELDS, ''), 'metric_id': 'D01', 'value': '38', 'status': 'OK'}
            (dest/'metrics_matrix.csv').write_bytes(_csv_bytes(rows=[row], fieldnames=METRIC_FIELDS))
            (dest/'metric_evidence.csv').write_text('metric_id\nD01\n')
            (dest/'company-results.json').write_text('{}')
            return {'returncode': 0, 'result': {'status': 'EXPORTED'}}

        with patch.object(local, 'prepare_program', return_value=work/'programs/program'), \
                patch.object(local, '_invoke', side_effect=invoke):
            result = local.run_local(company_id='marriott_international', work_dir=work,
                output_dir=self.root/'output', metric_ids=['B01'])
        self.assertEqual(calls, ['acquire', 'results'])
        self.assertEqual(result['status'], 'FLOW_INCOMPLETE')
        self.assertIsNone(result['calls']['sec'])
        with Path(result['outputs']['metrics_matrix.csv']).open(encoding='utf-8-sig') as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row['metric_id'], 'D01')
        self.assertEqual(row['value'], '38')
        self.assertEqual(row['local_run_status'], 'FLOW_INCOMPLETE')
        self.assertEqual(row['requested_in_local_run'], 'False')


class CaptureIdentityTest(unittest.TestCase):
    """Complete comparison must keep payload/order/coverage strict."""
    @staticmethod
    def seal(source):
        from scripts.vnext.canonical import content_hash
        for unit in source['units']:
            unit['unit_id'] = content_hash(value={k:v for k,v in unit.items() if k!='unit_id'})
        ids = [u['unit_id'] for u in source['units']]
        source['documents'][0]['source_unit_ids'] = ids
        source['required_unit_ids'] = ids
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
        return source

    def pair(self):
        old = {'documents': [{'document_id':'old', 'source_reference':{
                    'source_reference_id':'ref','raw_asset_id':'bytes','request_attempt_id':'old-attempt'},
                'registrant_name_binding':{'cover_caption':{'document_id':'old'},
                    'cover_name':{'document_id':'old'}}, 'source_unit_ids':[]}],
            'units':[{'document_id':'old','payload':'annual text','ordinal':0,'kind':'text'},
                     {'document_id':'old','payload':'second block','ordinal':1,'kind':'text'}],
            'required_unit_ids':[], 'source_proofs':[{'content_sha256':'unchanged'}],
            'prepared_annual_input':{'table_input':{'target_period':'FY2025','request_attempt_id':'old-table'}}}
        self.seal(old)
        new = deepcopy(old)
        new['documents'][0]['document_id'] = 'new'
        new['documents'][0]['source_reference']['request_attempt_id'] = 'new-attempt'
        for key in ('cover_caption','cover_name'):
            new['documents'][0]['registrant_name_binding'][key]['document_id'] = 'new'
        for unit in new['units']:unit['document_id'] = 'new'
        new['prepared_annual_input']['table_input']['request_attempt_id'] = 'new-table'
        return self.seal(new), old

    def test_only_observation_identity_changes_with_originals_preserved(self):
        from scripts.vnext.company_processing_read import project_capture_identity
        current, original = self.pair()
        saved = deepcopy(current)
        projected, proof = project_capture_identity(current, original)
        self.assertEqual(projected, original)
        self.assertEqual(current, saved)
        self.assertEqual(proof['actual_current_source_id'], current['semantic_source_id'])
        self.assertFalse(proof['current_source_proofs_rewritten'])
        self.assertFalse(proof['original_records_rewritten'])

    def test_changed_text_reference_or_order_receives_no_projection(self):
        from scripts.vnext.company_processing_read import project_capture_identity
        for change in ('text','reference','order','coverage'):
            with self.subTest(change=change):
                current, original = self.pair()
                if change=='text':current['units'][0]['payload']='changed annual text'
                elif change=='reference':current['documents'][0]['source_reference']['raw_asset_id']='other bytes'
                elif change=='order':current['units'].reverse()
                else:current['units'].pop()
                self.seal(current)
                projected, proof=project_capture_identity(current, original)
                self.assertIsNone(proof)
                self.assertEqual(projected, current)

    def test_changed_period_or_proof_stays_visible_to_strict_checker(self):
        from scripts.vnext.company_processing_read import project_capture_identity
        current, original = self.pair()
        current['prepared_annual_input']['table_input']['target_period']='FY2026'
        current['source_proofs'][0]['content_sha256']='different body'
        self.seal(current)
        projected, proof=project_capture_identity(current, original)
        self.assertIsNotNone(proof)
        self.assertNotEqual(projected['prepared_annual_input'], original['prepared_annual_input'])
        self.assertNotEqual(projected['source_proofs'], original['source_proofs'])

    def test_self_modified_unit_without_valid_identity_is_rejected(self):
        from scripts.vnext.company_processing_read import project_capture_identity
        from scripts.vnext.canonical import content_hash
        current, original = self.pair()
        current['units'][0]['payload']='changed'
        current['semantic_source_id']=content_hash(value={k:v for k,v in current.items() if k!='semantic_source_id'})
        with self.assertRaisesRegex(ValueError,'PROJECTION_UNIT_CHANGED'):
            project_capture_identity(current,original)


if __name__ == '__main__':
    unittest.main()
