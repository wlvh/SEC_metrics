"""Small recorded SEC bodies, real source reading and event adaptation."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sec_http import REQUEST_LOG_FIELDNAMES, request_log_csv_bytes, refresh_request_log_manifest
from sec_urls import accession_document_url, hdr_sgml_url, submissions_url, submissions_file_url
from scripts.vnext.normal_zero_ai_results import NormalZeroAiError
from scripts.vnext.request_bindings import BatchWorkflowError
from scripts.vnext.ordinary_current_update import _current_sources
from scripts.vnext.selected_event_source_v1 import read_selected_event_sources, SelectedEventSourceError

ROOT = Path(__file__).resolve().parents[2]
PERIOD = {'period_start': '2025-01-01', 'period_end': '2025-12-31', 'fiscal_year': 2025}


class SelectedEventSourceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.source = Path(temp.name)
        (self.source / 'config').mkdir()
        shutil.copyfile(ROOT / 'config/company_registry.csv', self.source / 'config/company_registry.csv')
        (self.source / 'evidence/accession_materials').mkdir(parents=True)
        self.rows = []

    def save(self, url, body, accession=''):
        name = url.rsplit('/', 1)[-1]
        relative = 'evidence/recorded/' + str(len(self.rows)) + '/' + name
        path = self.source / relative; path.parent.mkdir(parents=True)
        path.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        (self.source / (relative + '.headers.json')).write_text(json.dumps({
            'url': url, 'status_code': 200, 'content_length': len(body), 'sha256': digest,
            'saved_at_utc': '2026-10-09T00:00:00Z'}))
        row = {field: '' for field in REQUEST_LOG_FIELDNAMES}
        row.update(timestamp_utc='2026-10-09T00:00:00Z', method='GET', source_url=url,
                   status_code='200', purpose='RECORDED_SMALL_TEST', repo_relative_path=relative,
                   headers_repo_relative_path=relative + '.headers.json', content_length=str(len(body)),
                   content_sha256=digest, accession=accession, document_name=name, retry_attempt='0')
        self.rows.append(row); self.write_ledger()
        return path

    def write_ledger(self):
        log = self.source / 'evidence/requests_log.csv'
        log.write_bytes(request_log_csv_bytes(rows=self.rows))
        refresh_request_log_manifest(workdir=self.source, log_path=log)

    def add_issuer(self, cik, accession, *, history=False):
        filing = {'form': ['8-K'], 'reportDate': ['2025-01-08'], 'filingDate': ['2025-01-08'],
                  'accessionNumber': [accession], 'primaryDocument': ['event.htm']}
        payload = {'cik': int(cik), 'filings': {'recent': filing, 'files': []}}
        if history:
            name = 'CIK' + cik.zfill(10) + '-submissions-001.json'
            payload['filings']['recent'] = {key: [] for key in filing}
            payload['filings']['files'] = [{'name': name, 'filingFrom': '2025-01-01',
                'filingTo': '2025-12-31', 'filingCount': 2}]
            # An unretained form must still be visible to the full-body check.
            whole = {key: value + ['S-1' if key == 'form' else
                                  '2025-01-08' if key in {'reportDate', 'filingDate'} else
                                  '0000000000-25-000001' if key == 'accessionNumber' else 'other.htm']
                     for key, value in filing.items()}
            self.save(submissions_file_url(file_name=name), json.dumps(whole).encode())
        self.save(submissions_url(cik=int(cik)), json.dumps(payload).encode())
        self.save(accession_document_url(cik=int(cik), accession=accession, document_name='event.htm'),
                  b'<html><body>Item 5.02. Appointment of an officer.</body></html>', accession)
        self.header = self.save(hdr_sgml_url(cik=int(cik), accession=accession),
            ('<ACCESSION-NUMBER>' + accession + '\n<TYPE>8-K\n<FILING-DATE>20250108\n'
             '<ITEMS>5.02</ITEMS>\n').encode(), accession)

    def read(self, *, company='marriott_international', cik='1048286', **kwargs):
        return read_selected_event_sources(data_root=self.source, rules_root=ROOT,
            prepared={'company_id': company, 'entity': cik}, period=PERIOD, **kwargs)

    def test_source_only_nonempty_claims_keep_real_requests_and_no_results(self):
        self.add_issuer('1048286', '0001048286-25-000011')
        output = self.read()
        self.assertEqual(len(output['claims']), 1)
        self.assertEqual(len(output['source_proofs']), 3)
        self.assertEqual(output['source_admission']['source_credit'], 'RECORDED_TEST_ONLY')
        self.assertEqual(output['native_run_status'], 'NOT_CREATED')
        self.assertNotIn('result', output)
        self.assertFalse((self.source / 'catalog').exists())
        self.assertFalse((self.source / 'scripts').exists())
        self.assertEqual(_current_sources(self.source, output['source_proofs']),
            [{key: proof[key] for key in ('source_url', 'accession', 'document_name', 'content_sha256')}
             for proof in output['source_proofs']])

    def test_registered_union_reads_both_issuers_and_rules_from_code_root(self):
        self.add_issuer('2041610', '0002041610-25-000011')
        self.add_issuer('813828', '0000813828-25-000012')
        output = self.read(company='paramount_skydance_paramount_global', cik='2041610', registered_union=True)
        self.assertEqual(len(output['claims']), 2)
        self.assertEqual(set(output['registered_event_scope']['registered_ciks']), {'2041610', '813828'})
        self.assertFalse(output['registered_event_scope']['financial_cross_entity_combination_authorized'])
        self.assertEqual(len(output['source_proofs']), 6)

    def test_same_blob_key_does_not_hide_a_conflicting_media_record(self):
        from scripts.vnext.normal_governance_input import _Sources
        self.add_issuer('2041610', '0002041610-25-000011')
        self.add_issuer('813828', '0000813828-25-000012')
        class ConflictingReader(_Sources):
            def read(self, url, **kwargs):
                item = super().read(url, **kwargs)
                if self.cik == '813828' and kwargs['role'] == 'fy_8k_primary':
                    key = item['raw_blob']['raw_asset_id']
                    self.records[key] = {**self.records[key], 'media_type': 'application/octet-stream'}
                return item
        with patch('scripts.vnext.normal_zero_ai_results._Sources', ConflictingReader):
            with self.assertRaisesRegex(NormalZeroAiError, 'RECORD_CONFLICT'):
                self.read(company='paramount_skydance_paramount_global', cik='2041610', registered_union=True)

    def test_explicit_history_check_receives_full_body_and_conflict_is_not_empty_success(self):
        self.add_issuer('1048286', '0001048286-25-000011', history=True)
        self.assertEqual(len(self.read()['claims']), 1)  # original default unchanged
        def check(**context):
            self.assertEqual(context['body']['form'], ['8-K', 'S-1'])
            self.assertEqual(len(context['rows']), 1)
            self.assertEqual(context['shards'][0]['filingCount'], 2)
            self.assertEqual(context['period'], PERIOD)
            return {'reason': 'RECORDED_BLOCK_CONFLICT'}
        with self.assertRaisesRegex(NormalZeroAiError, 'HISTORY_SNAPSHOT_CONFLICT'):
            self.read(history_validator=check)

    def test_missing_header_and_header_date_conflict_remain_failures(self):
        self.add_issuer('1048286', '0001048286-25-000011')
        raw = self.header.read_bytes(); self.header.unlink()
        with self.assertRaises(BatchWorkflowError): self.read()
        self.header.write_bytes(raw.replace(b'20250108', b'20240108'))
        # Hash inconsistency is rejected before classification.
        with self.assertRaisesRegex(BatchWorkflowError, 'locator bytes'): self.read()

    def test_repeated_legacy_gets_are_bound_but_latest_failure_is_visible(self):
        self.add_issuer('1048286', '0001048286-25-000011')
        first = self.read(); self.rows.append(dict(self.rows[-1])); self.write_ledger()
        second = self.read()
        self.assertNotEqual(first['source_proofs'][-1]['request_attempt_id'],
                            second['source_proofs'][-1]['request_attempt_id'])
        self.assertEqual(_current_sources(self.source, first['source_proofs']),
            _current_sources(self.source, second['source_proofs']))
        self.rows.append({**self.rows[-1], 'status_code': '503', 'error': 'recorded failure'})
        self.write_ledger()
        with self.assertRaisesRegex(ValueError, 'LATEST_SOURCE_REQUEST_FAILED'): self.read()
        with self.assertRaisesRegex(ValueError, 'LATEST_SOURCE_REQUEST_FAILED'):
            _current_sources(self.source, first['source_proofs'])

    def test_wrong_registry_selected_entity_or_window_is_rejected(self):
        with self.assertRaisesRegex(SelectedEventSourceError, 'NOT_REGISTERED'):
            self.read(cik='813828')
        with self.assertRaisesRegex(SelectedEventSourceError, 'WINDOW_INVALID'):
            read_selected_event_sources(data_root=self.source, rules_root=ROOT,
                prepared={'company_id': 'marriott_international', 'entity': '1048286'},
                period={**PERIOD, 'period_start': '2026-01-01'})
        (self.source / 'config/company_registry.csv').write_text(
            (self.source / 'config/company_registry.csv').read_text().replace('primary:1048286', 'primary:813828'))
        with self.assertRaisesRegex(SelectedEventSourceError, 'REGISTRY_CHANGED'): self.read()


if __name__ == '__main__': unittest.main()
