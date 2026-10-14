"""OFFLINE checks for tools/databricks: the package builder, the shipped package and the notebook.

GitHub is an in-memory fake and the company run is a stub CLI, so nothing here
reaches the network, SEC or a model. Passing these tests is not evidence that a
real Databricks cluster or the real company run works; see
docs/databricks_offline_run.md.
"""
from contextlib import redirect_stderr, redirect_stdout
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import runpy
import tempfile
import unittest
from unittest import mock
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools' / 'databricks'
REF = 'ab' * 20
LEDGER_FIELDS = ('timestamp_utc', 'method', 'source_url', 'status_code', 'purpose', 'repo_relative_path',
                 'headers_repo_relative_path', 'content_length', 'content_sha256', 'accession',
                 'document_name', 'user_agent', 'retry_attempt', 'error')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def blob_sha(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location('databricks_build_offline_package',
                                                  TOOLS / 'build_offline_package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger_row(url, path, body, headers_path=''):
    return {'timestamp_utc': '2026-01-02T00:00:00+00:00', 'method': 'GET', 'source_url': url,
            'status_code': '200', 'purpose': 'test', 'repo_relative_path': path,
            'headers_repo_relative_path': headers_path, 'content_length': str(len(body)),
            'content_sha256': sha256(body), 'accession': '', 'document_name': path.rsplit('/', 1)[-1],
            'user_agent': 'test', 'retry_attempt': '0', 'error': ''}


def fake_repository():
    """One small commit: program files, a two-company registry and a request ledger.

    The first company has an immutable attempt with its headers, a current working
    copy, and a working copy a later capture overwrote. The second has one attempt.
    """
    files = {
        'scripts/vnext/example.py': b'VALUE = 1\n',
        'config/sec_config.json': b'{}\n',
        'catalog/metrics.json': b'{}\n',
        'tools/vnext_company.py': b'print("cli")\n',
        'tools/check_main_scalability.py': b'\n',
        'tools/probe_securegpt.py': b'\n',
        'tools/unrelated_tool.py': b'\n',
        'docs/evidence/issue28_continuous/known_result_defects.json': b'[]\n',
        'config/company_registry.csv': (
            'company_id,display_name,primary_cik,ticker,industry_profile,related_ciks\n'
            'acme_hotels,Acme Hotels,1234567,ACM,lodging,\n'
            'other_air,Other Air,7654321,OTH,airline,\n').encode(),
    }
    attempt = b'{"facts": "acme"}'
    attempt_headers = b'{"content-type": "application/json"}'
    attempt_path = f'evidence/request_attempts/{sha256(attempt)[:2]}/{sha256(attempt)}/CIK0001234567.json'
    attempt_headers_path = f'{attempt_path}.{sha256(attempt_headers)}.headers.json'
    current = b'{"filings": "acme"}'
    current_path = 'evidence/submissions/CIK0001234567.json'
    recorded_old, overwritten_now = b'{"old": 1}', b'{"new": 2}'
    overwritten_path = 'evidence/accession_materials/1234567/report.htm'
    other = b'{"facts": "other"}'
    other_path = f'evidence/request_attempts/{sha256(other)[:2]}/{sha256(other)}/CIK0007654321.json'
    files.update({attempt_path: attempt, attempt_headers_path: attempt_headers,
                  current_path: current, current_path + '.headers.json': b'{}',
                  overwritten_path: overwritten_now, overwritten_path + '.headers.json': b'{}',
                  other_path: other})
    rows = [ledger_row('https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json',
                       attempt_path, attempt, attempt_headers_path),
            ledger_row('https://data.sec.gov/submissions/CIK0001234567.json',
                       current_path, current, current_path + '.headers.json'),
            ledger_row('https://www.sec.gov/Archives/edgar/data/1234567/000000000000000001/report.htm',
                       overwritten_path, recorded_old, overwritten_path + '.headers.json'),
            ledger_row('https://data.sec.gov/api/xbrl/companyfacts/CIK0007654321.json', other_path, other)]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    ledger = stream.getvalue().encode()
    files['evidence/requests_log.csv'] = ledger
    files['evidence/requests_log_manifest.json'] = json.dumps(
        {'schema_version': 1, 'row_count': len(rows), 'content_sha256': sha256(ledger)}).encode()
    paths = {'attempt': attempt_path, 'attempt_headers': attempt_headers_path, 'current': current_path,
             'overwritten': overwritten_path, 'other': other_path}
    return files, paths


class FakeGitHub:
    """Serve one commit's tree listings and raw files the way the builder asks for them."""

    def __init__(self, files):
        self.files = files
        self.served = {}  # path -> bytes that differ from the commit

    def get(self, url, *, api=False):
        if api:
            prefix = 'https://api.github.com/repos/wlvh/SEC_metrics/git/trees/'
            spec, _, query = url[len(prefix):].partition('?')
            ref, _, directory = urllib.parse.unquote(spec).partition(':')
            assert url.startswith(prefix) and ref == REF, url
            tree = [{'path': path[len(directory) + 1:], 'type': 'blob', 'sha': blob_sha(data)}
                    for path, data in sorted(self.files.items())
                    if path.startswith(directory + '/')
                    and (query == 'recursive=1' or '/' not in path[len(directory) + 1:])]
            return json.dumps({'tree': tree, 'truncated': False}).encode()
        prefix = f'https://raw.githubusercontent.com/wlvh/SEC_metrics/{REF}/'
        assert url.startswith(prefix), url
        path = urllib.parse.unquote(url[len(prefix):])
        return self.served.get(path, self.files[path])


class PackageBuilderTest(unittest.TestCase):
    def setUp(self):
        self.builder = load_builder()
        self.files, self.paths = fake_repository()
        self.github = FakeGitHub(self.files)
        patcher = mock.patch.object(self.builder, '_get', self.github.get)
        patcher.start()
        self.addCleanup(patcher.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.out = Path(temp.name)

    def build(self, name='package.zip'):
        path = self.out / name
        with redirect_stdout(io.StringIO()):
            self.builder.build(REF, 'acme_hotels', str(path))
        return path

    def test_package_holds_program_and_only_this_companys_recorded_bodies(self):
        with zipfile.ZipFile(self.build()) as archive:
            names = {name.split('/', 1)[1] for name in archive.namelist()}
            package = json.loads(archive.read('sec_metrics_package/PACKAGE.json'))
            for name, digest in package['files'].items():
                self.assertEqual(sha256(archive.read('sec_metrics_package/' + name)), digest, name)
        self.assertEqual(names, set(package['files']) | {'PACKAGE.json'})
        source = {'source/' + self.paths[key] for key in ('attempt', 'attempt_headers', 'current')}
        source |= {'source/' + self.paths['current'] + '.headers.json', 'source/config/company_registry.csv',
                   'source/evidence/requests_log.csv', 'source/evidence/requests_log_manifest.json'}
        program = {'program/' + path for path in self.files
                   if path.split('/')[0] in ('scripts', 'config', 'catalog')}
        program |= {'program/' + path for path in self.builder.PROGRAM_FILES}
        self.assertEqual(set(package['files']), source | program)
        self.assertEqual((package['company_id'], package['ciks'], package['ref']), ('acme_hotels', ['1234567'], REF))
        self.assertEqual((package['sec_requests'], package['sec_bodies'], package['new_sec_requests']), (3, 2, 0))
        self.assertEqual(package['skipped_overwritten_working_copies'], [self.paths['overwritten']])

    def test_rebuilding_the_same_commit_gives_identical_bytes(self):
        self.assertEqual(self.build('one.zip').read_bytes(), self.build('two.zip').read_bytes())

    def test_download_that_differs_from_the_commit_writes_nothing(self):
        self.github.served['catalog/metrics.json'] = b'{"changed": true}\n'
        with self.assertRaisesRegex(self.builder.PackageError, 'catalog/metrics.json differs'):
            self.build()
        self.assertFalse((self.out / 'package.zip').exists())

    def test_ledger_must_match_its_manifest(self):
        manifest = json.loads(self.files['evidence/requests_log_manifest.json'])
        manifest['row_count'] += 1
        self.files['evidence/requests_log_manifest.json'] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(self.builder.PackageError, 'does not match its manifest'):
            self.build()

    def test_immutable_headers_must_match_the_hash_in_their_name(self):
        self.files[self.paths['attempt_headers']] = b'{"content-type": "text/html"}'
        with self.assertRaisesRegex(self.builder.PackageError, 'differs from the hash in its name'):
            self.build()

    def test_cli_requires_a_company_and_reports_an_unknown_one(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            self.builder.main([])
        self.assertEqual(raised.exception.code, 2)
        error = io.StringIO()
        with redirect_stderr(error):
            code = self.builder.main(['--company', 'missing_co', '--ref', REF, '--out', str(self.out / 'x.zip')])
        self.assertEqual(code, 1)
        self.assertIn('PACKAGE_FAILED', error.getvalue())
        self.assertFalse((self.out / 'x.zip').exists())

    def test_list_companies_counts_each_companys_saved_requests(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.builder.list_companies(REF)
        lines = {line.split()[0]: line for line in output.getvalue().splitlines()}
        self.assertIn('   3 SEC requests', lines['acme_hotels'])
        self.assertIn('   1 SEC requests', lines['other_air'])


class CommittedPackageTest(unittest.TestCase):
    """The prebuilt package next to the builder must stay the builder's default package."""

    def test_committed_package_matches_its_listing_the_default_ref_and_the_ledger(self):
        builder = load_builder()
        packages = sorted(path.name for path in TOOLS.glob('*.zip'))
        self.assertEqual(packages, [f'sec_metrics_marriott_international_{builder.DEFAULT_REF[:8]}.zip'])
        with zipfile.ZipFile(TOOLS / packages[0]) as archive:
            package = json.loads(archive.read('sec_metrics_package/PACKAGE.json'))
            files = {name: archive.read('sec_metrics_package/' + name) for name in package['files']}
            self.assertEqual({name.split('/', 1)[1] for name in archive.namelist()},
                             set(files) | {'PACKAGE.json'})
        for name, data in files.items():
            self.assertEqual(sha256(data), package['files'][name], name)
        self.assertEqual((package['ref'], package['company_id'], package['new_sec_requests']),
                         (builder.DEFAULT_REF, 'marriott_international', 0))
        ledger = files['source/evidence/requests_log.csv']
        manifest = json.loads(files['source/evidence/requests_log_manifest.json'])
        self.assertEqual(sha256(ledger), manifest['content_sha256'])
        # Every packaged SEC body is a response the current, append-only ledger recorded.
        with (ROOT / 'evidence' / 'requests_log.csv').open(encoding='utf-8', newline='') as stream:
            recorded = {(row['repo_relative_path'], row['content_sha256'], row['content_length'])
                        for row in csv.DictReader(stream)}
        bodies = {name[len('source/'):]: data for name, data in files.items()
                  if name.startswith('source/evidence/') and not name.endswith('.headers.json')
                  and name not in ('source/evidence/requests_log.csv',
                                   'source/evidence/requests_log_manifest.json')}
        self.assertEqual(len(bodies), package['sec_bodies'])
        for path, data in bodies.items():
            self.assertIn((path, sha256(data), str(len(data))), recorded, path)


def write_package(path, files, *, listed=None):
    """A minimal zip in the builder's layout; PACKAGE.json lists every file's SHA-256 unless overridden."""
    package = {'record_type': 'SEC_METRICS_OFFLINE_PACKAGE', 'schema_version': 1, 'ref': REF,
               'company_id': 'acme_hotels', 'sec_bodies': 1,
               'files': {name: sha256(data) for name, data in files.items()}}
    package['files'].update(listed or {})
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in files.items():
            archive.writestr('sec_metrics_package/' + name, data)
        archive.writestr('sec_metrics_package/PACKAGE.json', json.dumps(package))


def run_notebook(path, settings, init_globals=None):
    """Run a notebook source file with its settings lines replaced.

    Returns the printed summary (None if the notebook stopped before printing it),
    the RuntimeError the notebook raised (or None) and the captured output.
    """
    source = path.read_text(encoding='utf-8')
    for name, value in settings.items():
        source, count = re.subn(rf'^{name} = .*$', f'{name} = {value!r}', source, count=1, flags=re.M)
        if count != 1:
            raise AssertionError(f'setting {name} not found in {path.name}')
    output, raised = io.StringIO(), None
    with tempfile.TemporaryDirectory() as temp:
        copy = Path(temp) / path.name
        copy.write_text(source, encoding='utf-8')
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            try:
                runpy.run_path(str(copy), init_globals=dict(init_globals or {}), run_name='__main__')
            except RuntimeError as error:
                raised = error
    text = output.getvalue()
    start = 0 if text.startswith('{\n') else text.rfind('\n{\n') + 1
    summary = json.loads(text[start:]) if start or text.startswith('{\n') else None
    return summary, raised, text


STUB_COMPANY_CLI = r'''
import argparse, csv, json, sys
from pathlib import Path
parser = argparse.ArgumentParser()
for name in ('command', '--company', '--source-root', '--work-dir', '--output-dir'):
    parser.add_argument(name)
parser.add_argument('--metric', action='append')
args = parser.parse_args()
behaviour = json.loads((Path(args.source_root) / 'behaviour.json').read_text())
Path(args.work_dir).mkdir(parents=True, exist_ok=True)
(Path(args.work_dir) / 'invocation.json').write_text(json.dumps({'args': vars(args), 'isolated': sys.flags.isolated}))
if behaviour.get('crash'):
    print('Traceback (most recent call last): boom')
    sys.exit(3)
output = Path(args.output_dir) / 'run-1'
output.mkdir(parents=True, exist_ok=True)
with (output / 'metrics_matrix.csv').open('w', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=['metric_id', 'value', 'status'])
    writer.writeheader()
    for metric in args.metric:
        writer.writerow({'metric_id': metric, 'value': '7', 'status': 'OK'})
statuses = behaviour.get('statuses', {})
print(json.dumps({'status': behaviour.get('status', 'FLOW_COMPLETED'), 'calls': behaviour['calls'],
                  'output_root': str(output),
                  'metrics': [{'metric_id': m, 'status': statuses.get(m, 'CANDIDATE_READY'), 'reason': 'stub'}
                              for m in args.metric]}))
'''


class CompanyMetricsNotebookTest(unittest.TestCase):
    notebook = TOOLS / 'company_metrics_notebook.py'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)

    def run_with(self, behaviour, *, tamper=False, save=False):
        files = {'program/tools/vnext_company.py': STUB_COMPANY_CLI.encode(),
                 'source/behaviour.json': json.dumps(behaviour).encode()}
        zip_path = self.temp / 'package.zip'
        write_package(zip_path, files, listed={'source/behaviour.json': '0' * 64} if tamper else None)
        settings = {'PACKAGE_ZIP': str(zip_path), 'METRICS': ['B01', 'B04'], 'WORK_ROOT': str(self.temp / 'work'),
                    'SAVE_TO': str(self.temp / 'saved') if save else None}
        return run_notebook(self.notebook, settings)

    def invocation(self):
        return json.loads((self.temp / 'work' / 'state-acme_hotels' / 'invocation.json').read_text())

    def test_completed_run_passes_and_reports_the_programs_own_call_counts(self):
        calls = {'provider': 0, 'paid': 0, 'sec': 0}
        summary, raised, _ = self.run_with({'calls': calls}, save=True)
        self.assertIsNone(raised)
        self.assertEqual(summary['status'], 'PASS')
        self.assertEqual(summary['calls'], calls)
        self.assertEqual(summary['values'], {'B01': '7', 'B04': '7'})
        invocation = self.invocation()
        self.assertEqual(invocation['isolated'], 1)
        self.assertEqual((invocation['args']['command'], invocation['args']['company'], invocation['args']['metric']),
                         ('run', 'acme_hotels', ['B01', 'B04']))
        self.assertTrue(invocation['args']['source_root'].endswith('/sec_metrics_package/source'))
        self.assertTrue((Path(summary['saved_to']) / 'metrics_matrix.csv').is_file())

    def test_call_counts_are_reported_as_measured_not_assumed_zero(self):
        summary, _, _ = self.run_with({'calls': {'provider': 1, 'paid': 1, 'sec': 2}})
        self.assertEqual(summary['calls'], {'provider': 1, 'paid': 1, 'sec': 2})

    def test_limited_flow_is_not_pass_and_names_the_metric(self):
        summary, _, _ = self.run_with({'calls': {'provider': 0, 'paid': 0, 'sec': 0},
                                       'status': 'FLOW_COMPLETED_WITH_LIMITATIONS',
                                       'statuses': {'B04': 'SOURCE_BLOCKED'}})
        self.assertEqual(summary['status'], 'FLOW_COMPLETED_WITH_LIMITATIONS')
        self.assertEqual(summary['metric_failures'], {'B04': 'stub'})

    def test_program_without_a_summary_stops_the_notebook(self):
        summary, raised, text = self.run_with({'crash': True})
        self.assertIsNone(summary)
        self.assertIn('退出码 3', str(raised))
        self.assertIn('boom', text)

    def test_package_file_that_differs_from_its_listing_stops_before_running(self):
        summary, raised, _ = self.run_with({'calls': {}}, tamper=True)
        self.assertIsNone(summary)
        self.assertIn('differ from PACKAGE.json', str(raised))
        self.assertFalse((self.temp / 'work' / 'state-acme_hotels').exists())


if __name__ == '__main__':
    unittest.main()
