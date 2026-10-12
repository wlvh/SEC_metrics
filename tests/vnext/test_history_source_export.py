"""The public history export uses received source readers, never a fetcher."""
import io
import json
import socket
from unittest import TestCase
from unittest.mock import patch

from tools.vnext_company import main
from vnext import company_handoff as handoff
from vnext.company_history_export import latest_history_source_frame
from tests.vnext import test_selected_source_requirements as fixtures
from tests.vnext.test_selected_historical_fiscal_label import annual
from sec_urls import accession_directory_url, accession_document_url, companyfacts_url, submissions_url


class HistorySourceExportEntryTest(TestCase):
    def test_history_option_enters_received_exporter_instead_of_missing_module(self):
        def export(**kwargs):
            self.assertTrue(kwargs['saved_source_only'])
            self.assertTrue(callable(kwargs['declared_frame']))
            return {'status': 'EXPORTED', 'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0}}
        with patch.object(handoff, 'export_company', side_effect=export), \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            code = main(['export', '--company', 'marriott_international',
                '--source-root', '/unused/source', '--output-root', '/unused/output',
                '--metric', 'B01', '--history-years', '5'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'EXPORTED')

    def test_unconnected_history_metric_is_rejected_before_exporter(self):
        with patch.object(handoff, 'export_company', side_effect=AssertionError('No unconnected export')), \
             patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as raised:
            main(['export', '--company', 'marriott_international',
                '--source-root', '/unused/source', '--output-root', '/unused/output',
                '--trust-root', '/unused/trust', '--metric', 'D04', '--history-years', '5'])
        self.assertEqual(raised.exception.code, 2)

    def test_retained_native_export_still_requires_its_original_trust(self):
        with patch.object(handoff, 'export_company', side_effect=AssertionError('No incomplete retained invocation')), \
             patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as raised:
            main(['export', '--company', 'marriott_international',
                '--source-root', '/unused/source', '--output-root', '/unused/output', '--metric', 'B01'])
        self.assertEqual(raised.exception.code, 2)


class HistorySourceExportSmallTest(TestCase):
    def setUp(self):
        self.fixture = fixtures.SelectedSourceRequirementsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.root = self.fixture.root.resolve()
        self.source = self.fixture.root
        self.fixture.client.workdir = self.source
        self.fixture.client.log_path = self.source/'evidence/requests_log.csv'
        filings, fact_rows = [], []
        for year in range(2025, 2019, -1):
            filing = {'form': '10-K', 'reportDate': f'{year}-12-31',
                'filingDate': f'{year+1}-02-10',
                'accessionNumber': f'0001048286-{str(year+1)[2:]}-000007',
                'primaryDocument': f'annual-{year}.htm'}
            filings.append(filing)
            raw = annual().replace(b'19617', b'1048286').replace(b'2021', str(year).encode())
            self.fixture.record(accession_document_url(cik=fixtures.CIK,
                accession=filing['accessionNumber'], document_name=filing['primaryDocument']), raw)
            directory = {'directory': {'name': '/Archives/edgar/data/1048286/'+filing['accessionNumber'].replace('-', ''),
                'item': [{'name': filing['primaryDocument']}, {'name': f'annual-{year}_htm.xml'}]}}
            self.fixture.record(accession_directory_url(cik=fixtures.CIK,
                accession=filing['accessionNumber']), json.dumps(directory).encode())
            self.fixture.record(accession_document_url(cik=fixtures.CIK,
                accession=filing['accessionNumber'], document_name=f'annual-{year}_htm.xml'), raw)
            fact_rows.append({'accn': filing['accessionNumber'], 'fy': year, 'start': f'{year}-01-01',
                'end': f'{year}-12-31', 'form': '10-K', 'fp': 'FY', 'filed': filing['filingDate'], 'val': 100})
        metadata = {'cik': fixtures.CIK, 'filings': {'recent': {
            key: [filing[key] for filing in filings] for key in filings[0]}, 'files': []}}
        self.fixture.record(submissions_url(cik=fixtures.CIK), json.dumps(metadata).encode())
        self.fixture.record(companyfacts_url(cik=fixtures.CIK), json.dumps({'cik': fixtures.CIK,
            'facts': {'us-gaap': {'Revenues': {'units': {'USD': fact_rows}}}}}).encode())

    def run_export(self, suffix, metric='B01'):
        output = self.source.parent/('package-'+suffix)
        trust = self.source.parent/('trust-'+suffix)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')), \
             patch('vnext.calculator.calculate_metric', side_effect=AssertionError('Source export cannot calculate')), \
             patch.object(handoff, 'checkpoint_installation', side_effect=AssertionError('No old journal')), \
             patch.object(handoff, 'rule_bindings', side_effect=AssertionError('No old Requirement')), \
             patch('sys.stdout', new_callable=io.StringIO) as stream:
            code = main(['export', '--company', fixtures.COMPANY, '--source-root', str(self.source),
                '--output-root', str(output), '--trust-root', str(trust), '--metric', metric,
                '--history-years', '5'])
        return code, json.loads(stream.getvalue()), output, trust

    def test_real_small_public_export_copies_exact_source_and_is_readable_without_journal(self):
        before = self.fixture.digest_tree()
        code, report, output, trust = self.run_export('complete')
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'EXPORTED')
        self.assertEqual(report['source_discovery']['fiscal_range']['fiscal_years'], [2021, 2022, 2023, 2024, 2025])
        self.assertFalse(report['retained_native_install_supported'])
        self.assertFalse(trust.exists())
        self.assertFalse((output/handoff.EXPORT_PATH).exists())
        self.assertEqual((output/'evidence/requests_log.csv').read_bytes(),
                         (self.source/'evidence/requests_log.csv').read_bytes())
        for relative in report['files']:
            self.assertEqual((output/relative).read_bytes(), (self.source/relative).read_bytes())
        copied = latest_history_source_frame(repo_root=output, company_id=fixtures.COMPANY,
                                             years=5, metric_ids=['B01'])
        self.assertEqual(copied, report['source_discovery'])
        self.assertEqual(before, self.fixture.digest_tree())
        self.assertFalse(report['new_call_allowance'])
        self.assertEqual(report['ai_processing_state'], 'NOT_INCLUDED')

    def test_missing_required_source_reports_incomplete_and_publishes_no_partial_package(self):
        self.fixture.remove_get(accession_document_url(cik=fixtures.CIK,
            accession='0001048286-23-000007', document_name='annual-2022_htm.xml'))
        code, report, output, trust = self.run_export('missing')
        self.assertEqual(code, 2)
        self.assertEqual(report['status'], 'SOURCE_EXPORT_INCOMPLETE')
        self.assertFalse(output.exists())
        self.assertFalse(trust.exists())
        self.assertEqual(report['new_business_calls'], {'provider': 0, 'paid': 0, 'sec': 0})
        task = next(t for t in report['source_discovery']['fiscal_range']['tasks'] if t['fiscal_year'] == 2022)
        self.assertFalse(task['source_bytes_available'])

    def test_failed_current_source_is_not_replaced_by_old_success_and_output_is_not_overwritten(self):
        code, report, output, trust = self.run_export('original')
        original = (output/handoff.PACKAGE_FILE).read_bytes()
        url = accession_document_url(cik=fixtures.CIK,
            accession='0001048286-23-000007', document_name='annual-2022_htm.xml')
        self.fixture.record(url, b'failed current response', 503, 'HTTP 503')
        code, failed, new_output, new_trust = self.run_export('failed')
        self.assertEqual(code, 2)
        self.assertEqual(failed['status'], 'SOURCE_EXPORT_INCOMPLETE')
        self.assertFalse(new_output.exists())
        self.assertEqual((output/handoff.PACKAGE_FILE).read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'OUTPUT_EXISTS'):
            self.run_export('original')

    def test_explicit_issuer_latest_label_is_used_instead_of_report_end_year(self):
        filing = '0001048286-26-000007'
        raw = annual().replace(b'19617', b'1048286').replace(b'2021', b'2025')
        raw = raw.replace(b'</body></html>', b'<p>Our fiscal year ends on December 31. '
            b'References to fiscal 2026, for example, refer to the fiscal year ending '
            b'December 31, 2025.</p></body></html>')
        self.fixture.record(accession_document_url(cik=fixtures.CIK,
            accession=filing, document_name='annual-2025.htm'), raw)
        code, report, output, _ = self.run_export('issuer-label')
        self.assertEqual(code, 2)
        window = report['source_discovery']['fiscal_range']
        self.assertEqual(window['fiscal_years'], [2022, 2023, 2024, 2025, 2026])
        task = next(t for t in window['tasks'] if t['fiscal_year'] == 2026)
        self.assertEqual(task['report_end'], '2025-12-31')
        self.assertEqual(next(t for t in window['tasks'] if t['fiscal_year'] == 2025)['status'],
                         'FISCAL_YEAR_SOURCE_UNRESOLVED')
        self.assertFalse(output.exists())

    def test_copy_interruption_removes_staging_and_never_publishes_incomplete_package(self):
        original_write = handoff.write_immutable_bytes
        def interrupt(*, path, content):
            if path.name == 'annual-2022.htm':
                raise OSError('INJECTED_COPY_INTERRUPTION')
            return original_write(path=path, content=content)
        before = self.fixture.digest_tree()
        with patch.object(handoff, 'write_immutable_bytes', side_effect=interrupt), \
             self.assertRaisesRegex(OSError, 'INJECTED_COPY_INTERRUPTION'):
            self.run_export('interrupted')
        self.assertFalse((self.source.parent/'package-interrupted').exists())
        self.assertFalse(list(self.source.parent.glob('.package-interrupted.preparing-*')))
        self.assertEqual(self.fixture.digest_tree(), before)
