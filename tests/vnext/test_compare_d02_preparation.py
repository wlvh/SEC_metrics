"""Receiver D02 comparison tool: sample accounting, visible failures and change classes."""
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools' / 'compare_d02_preparation.py'

STUB = '''
import os, socket, time
def prepare_historical_legal_sources(*, repo_root, company_id, fiscal_year):
    if company_id == 'refused' and REFUSE:
        raise ValueError('EXAMPLE_REFUSAL')
    if company_id == 'network':
        socket.create_connection(('example.invalid', 80))
    if company_id == 'crash':
        os._exit(3)
    if company_id == 'hang':
        time.sleep(60)
    if company_id == 'litter':
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated.cfg'), 'w') as handle:
            handle.write('left behind by the producer')
    text = open(os.path.join(repo_root, company_id + '.txt'), encoding='utf-8').read()
    request = {'request_id': 'sha256:' + str(len(text)), 'source_id': 's1',
               'blocks': [{'block_id': 'b1', 'text': text}], 'must_decide': ['b1'],
               'record_type': 'R', 'contract': 'C', 'metric_id': 'D02', 'definition': {},
               'system_prompt': 'P', 'response_protocol': {}}
    proposal = {'coverage_status': 'LOCAL_REQUESTED_RANGES_SCANNED', 'coverage_reasons': [],
                'note_references': [], 'D03': {}, 'policy_hash': 'p', 'proposal_id': 'x',
                'checked_ranges': [{'section_id': 'ITEM_8', 'start_block': 0, 'end_block_exclusive': 2}],
                'D02': {'finding_status': 'SOURCE_EXCERPTS_FOUND', 'candidates': [
                    {'section_id': 'ITEM_8', 'block_index': 1, 'labels': ['L'], 'text': text}]},
                'document_id': 'd', 'source_reference_id': 's1'}
    target = {'accession': 'a', 'entity': '1', 'period_start': '%d-01-01' % fiscal_year,
              'period_end': '%d-12-31' % fiscal_year}
    return {'source_arguments': {'target': target, 'raw_blobs': {'sha256:r': {}}},
            'prepared': {'capability_status': 'READY', 'capability_gaps': [], 'proposals': {'s1': proposal}},
            'requests': [request], 'admission': {'record_type': 'VERIFIED', 'request_attempt_ids': ['r1']}}
'''


def load_tool():
    spec = importlib.util.spec_from_file_location('compare_d02_preparation_under_test', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def write_code_root(root, *, refuse=True, companies=('alpha', 'refused')):
    package = Path(root) / 'scripts' / 'vnext'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    (package / 'd02_reviewed_source.py').write_text(f'REFUSE = {refuse}\n' + STUB)
    config = Path(root) / 'config'
    config.mkdir()
    (config / 'company_registry.csv').write_text('company_id,display_name\n'
                                                 + ''.join(f'{c},{c}\n' for c in companies))


def write_sources(root, names):
    Path(root).mkdir(parents=True, exist_ok=True)
    for name in names:
        (Path(root) / f'{name}.txt').write_text(f'Legal proceedings text for {name}.')


class WorkerAccountingTest(unittest.TestCase):
    def test_refusal_network_and_crash_stay_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, sources, work = Path(tmp, 'code'), Path(tmp, 'sources'), Path(tmp, 'work')
            write_code_root(code)
            write_sources(sources, ['alpha', 'beta'])
            work.mkdir()
            samples = [['alpha', 2024], ['crash', 2024], ['refused', 2024], ['beta', 2024], ['network', 2024]]
            tasks = tool.run_version(label='baseline', code_root=code, source_root=sources,
                                     samples=samples, work_dir=work)
            workers = tool.run_workers(tasks, 2, 60)
            results, problems = tool.load_results(tasks)
        self.assertEqual(problems, [])
        self.assertEqual({w['samples'][0]: w['returncode'] for w in workers},
                         {'alpha:2024': 0, 'crash:2024': 3, 'refused:2024': 0, 'beta:2024': 0, 'network:2024': 0})
        self.assertEqual(results['alpha:2024']['outcome'], 'OK')
        self.assertEqual(results['refused:2024']['error']['reason'], 'EXAMPLE_REFUSAL')
        self.assertEqual(results['network:2024']['error']['reason'], tool.NETWORK_REFUSAL)
        # Each sample has its own process: the crash loses only its own result.
        self.assertNotIn('crash:2024', results)
        self.assertEqual(results['beta:2024']['outcome'], 'OK')
        keys = [f'{c}:{y}' for c, y in samples]
        report = tool.compare(keys, results, results)
        categories = {e['sample']: e['category'] for e in report['entries']}
        self.assertEqual(categories, {'alpha:2024': 'SAME_OK', 'crash:2024': 'NOT_COMPARED',
                                      'refused:2024': 'SAME_FAIL', 'beta:2024': 'SAME_OK',
                                      'network:2024': 'SAME_FAIL'})
        self.assertFalse(report['all_samples_compared'])

    def test_time_limit_applies_to_each_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, sources, work = Path(tmp, 'code'), Path(tmp, 'sources'), Path(tmp, 'work')
            write_code_root(code)
            write_sources(sources, ['alpha'])
            work.mkdir()
            tasks = tool.run_version(label='candidate', code_root=code, source_root=sources,
                                     samples=[['hang', 2024], ['alpha', 2024]], work_dir=work)
            workers = tool.run_workers(tasks, 2, 3)
            results, _ = tool.load_results(tasks)
        timed_out = {w['samples'][0]: w['timeout'] for w in workers}
        self.assertEqual(timed_out, {'hang:2024': True, 'alpha:2024': False})
        self.assertEqual(set(results), {'alpha:2024'})
        report = tool.compare(['hang:2024', 'alpha:2024'], results, results)
        self.assertEqual(report['counts']['NOT_COMPARED'], 1)

    def test_unimportable_entry_is_a_harness_error_for_every_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, work = Path(tmp, 'code'), Path(tmp, 'work')
            (code / 'scripts' / 'vnext').mkdir(parents=True)
            (code / 'scripts' / 'vnext' / '__init__.py').write_text('')
            work.mkdir()
            tasks = tool.run_version(label='candidate', code_root=code, source_root=tmp,
                                     samples=[['alpha', 2024], ['beta', 2025]], work_dir=work)
            tool.run_workers(tasks, 1, 60)
            results, _ = tool.load_results(tasks)
        self.assertEqual({r['outcome'] for r in results.values()}, {'HARNESS_ERROR'})
        report = tool.compare(['alpha:2024', 'beta:2025'], results, results)
        self.assertEqual(report['counts']['NOT_COMPARED'], 2)


class ClassificationTest(unittest.TestCase):
    def setUp(self):
        self.ok = {'outcome': 'OK', 'fingerprint': {
            'selection': {'accession': 'a'}, 'admission': {}, 'capability': ['READY', 'g'],
            'source_references_digest': 'r', 'sources': {},
            'requests': [{'request_id': 'r1', 'source_id': 's1', 'pool': ['b1', 'b2'], 'must_decide': ['b1'],
                          'texts_digest': 't', 'fields_digest': 'i'}], 'result_parts': {}}}

    def error(self, reason):
        return {'outcome': 'ERROR', 'error': {'type': 'ValueError', 'module': 'm', 'reason': reason, 'category': None}}

    def test_status_transitions_and_missing_results(self):
        self.assertEqual(tool.classify(self.ok, self.ok)[0], 'SAME_OK')
        self.assertEqual(tool.classify(self.error('A'), self.ok)[0], 'FAIL_TO_OK')
        self.assertEqual(tool.classify(self.ok, self.error('A'))[0], 'OK_TO_FAIL')
        self.assertEqual(tool.classify(self.error('A'), self.error('A'))[0], 'SAME_FAIL')
        self.assertEqual(tool.classify(self.error('A'), self.error('B'))[0], 'CHANGED_FAIL')
        self.assertEqual(tool.classify(None, self.ok)[0], 'NOT_COMPARED')
        self.assertEqual(tool.classify(self.ok, {'outcome': 'HARNESS_ERROR'})[0], 'NOT_COMPARED')

    def test_request_identity_and_pool_changes_are_named(self):
        changed = {'outcome': 'OK', 'fingerprint': {**self.ok['fingerprint'], 'requests': [
            {**self.ok['fingerprint']['requests'][0], 'request_id': 'r2', 'pool': ['b1', 'b3']}]}}
        category, changes = tool.classify(self.ok, changed)
        self.assertEqual(category, 'CHANGED_OK')
        fields = {c['field']: c for c in changes}
        self.assertIn('no longer apply', fields['request_id']['note'])
        self.assertEqual((fields['pool']['added'], fields['pool']['removed']), (1, 1))

    def test_document_level_changes_are_reported(self):
        source = {'coverage': ['LOCAL_REQUESTED_RANGES_SCANNED', []], 'coverage_record_digest': 'c1',
                  'note_references': [], 'checked_ranges': [['ITEM_8', 0, 9]], 'd02_candidates': [],
                  'd02_records_digest': 'x', 'proposal_ids': ['x', 'd'], 'd02_finding_status': 'F',
                  'furniture_removed': [3],
                  'd03_digest': 'd', 'other_fields': [], 'other_digest': 'o', 'policy_hash': 'p'}
        base = {'outcome': 'OK', 'fingerprint': {**self.ok['fingerprint'], 'sources': {'s1': source}}}
        cand = {'outcome': 'OK', 'fingerprint': {**base['fingerprint'], 'sources': {'s1': {
            **source, 'coverage_record_digest': 'c2', 'furniture_removed': [3, 4]}}}}
        category, changes = tool.classify(base, cand)
        self.assertEqual(category, 'CHANGED_OK')
        self.assertEqual({c['field'] for c in changes}, {'coverage_record_digest', 'furniture_removed'})

    def test_unrequested_result_makes_the_comparison_incomplete(self):
        report = tool.compare(['alpha:2024'], {'alpha:2024': self.ok, 'extra:2024': self.ok},
                              {'alpha:2024': self.ok})
        self.assertEqual(report['counts']['SAME_OK'], 1)
        self.assertEqual(report['unexpected_results'], ['extra:2024'])
        self.assertFalse(report['all_samples_compared'])


def sample_result():
    candidate = {'source_reference_id': 's1', 'raw_asset_id': 'sha256:r', 'document_id': 'd', 'section_id': 'ITEM_3',
                 'labels': ['L'], 'block_index': 4, 'raw_start_byte': 100, 'raw_end_byte': 160,
                 'raw_span_sha256': 'h', 'text': 'Legal proceedings.'}
    proposal = {'coverage_status': 'LOCAL_REQUESTED_RANGES_SCANNED', 'coverage_reasons': [], 'note_references': [],
                'checked_ranges': [], 'D02': {'finding_status': 'SOURCE_EXCERPTS_FOUND', 'candidates': [candidate]},
                'D03': {}, 'policy_hash': 'p', 'proposal_id': 'x', 'document_id': 'd', 'source_reference_id': 's1'}
    target = {'company_id': 'alpha', 'entity': '1', 'accession': 'a', 'period_start': '2024-01-01',
              'period_end': '2024-12-31', 'scope': {'entity_scope': 'registrant'}, 'scope_key': 'k1'}
    return {'source_arguments': {'target': target, 'raw_blobs': {'sha256:r': {}},
                                 'raw_bytes_by_id': {'sha256:r': b'<html>'}},
            'prepared': {'capability_status': 'READY', 'capability_gaps': [], 'proposals': {'s1': proposal}},
            'requests': [], 'admission': {'record_type': 'VERIFIED'}, 'period_selection': {'policy_id': 'p1'}}


class FingerprintTest(unittest.TestCase):
    def classify(self, mutate):
        base, cand = sample_result(), sample_result()
        mutate(cand)
        category, changes = tool.classify({'outcome': 'OK', 'fingerprint': tool.fingerprint(base)},
                                          {'outcome': 'OK', 'fingerprint': tool.fingerprint(cand)})
        return category, {c['field']: c for c in changes}

    def test_scope_locators_identities_and_unnamed_parts_are_compared(self):
        def candidate(result):
            return result['prepared']['proposals']['s1']['D02']['candidates'][0]
        self.assertEqual(self.classify(lambda result: None), ('SAME_OK', {}))
        # (mutation, named field that must report it, result part that must report it)
        cases = {
            'D02 scope': (lambda r: r['source_arguments']['target']['scope'].update(entity_scope='consolidated'),
                          'selection', 'source_arguments.target'),
            'candidate byte span': (lambda r: candidate(r).update(raw_start_byte=101),
                                    'd02_records_digest', 'prepared.proposals'),
            'proposal id': (lambda r: r['prepared']['proposals']['s1'].update(proposal_id='y'),
                            'proposal_ids', 'prepared.proposals'),
            'raw bytes': (lambda r: r['source_arguments']['raw_bytes_by_id'].update({'sha256:r': b'<html> '}),
                          None, 'source_arguments.raw_bytes_by_id'),
            'unnamed field': (lambda r: r['period_selection'].update(policy_id='p2'),
                              None, 'period_selection.policy_id'),
        }
        for name, (mutate, field, part) in cases.items():
            with self.subTest(name):
                category, fields = self.classify(mutate)
                self.assertEqual(category, 'CHANGED_OK')
                self.assertEqual(fields['result_parts']['parts'], [part])
                self.assertTrue(tool._describe(fields['result_parts']).startswith('result parts changed: '))
                if field:
                    self.assertIn(field, fields)


class SourceDigestTest(unittest.TestCase):
    def test_changed_or_added_source_file_changes_the_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_sources(tmp, ['alpha'])
            first = tool.tree_digest(tmp)
            Path(tmp, 'alpha.txt').write_text('changed')
            second = tool.tree_digest(tmp)
            Path(tmp, 'new.txt').write_text('added')
            third = tool.tree_digest(tmp)
            Path(tmp, 'empty').mkdir()
            fourth = tool.tree_digest(tmp)
        self.assertEqual(len({first['digest'], second['digest'], third['digest']}), 3)
        self.assertEqual((first['files'], third['files']), (1, 2))
        # An empty directory changes the result but not the file digest other runs cite.
        self.assertNotEqual(third, fourth)
        self.assertEqual(third['digest'], fourth['digest'])
        self.assertEqual((third['directories'], fourth['directories']), (0, 1))


class PinnedCommitRunTest(unittest.TestCase):
    def git(self, repo, *args):
        return subprocess.run(['git', '-C', str(repo), '-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                               *args], check=True, capture_output=True, text=True).stdout.strip()

    def test_two_commits_are_compared_and_worktrees_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, sources = Path(tmp, 'repo'), Path(tmp, 'sources')
            repo.mkdir()
            self.git(repo, 'init', '-q')
            write_code_root(repo, refuse=True)
            self.git(repo, 'add', '-A')
            self.git(repo, 'commit', '-q', '-m', 'baseline')
            baseline = self.git(repo, 'rev-parse', 'HEAD')
            (repo / 'scripts' / 'vnext' / 'd02_reviewed_source.py').write_text('REFUSE = False\n' + STUB)
            # Only the candidate registers the company whose producer leaves a file behind.
            (repo / 'config' / 'company_registry.csv').write_text('company_id,display_name\n'
                                                                  'alpha,alpha\nrefused,refused\nlitter,litter\n')
            self.git(repo, 'commit', '-q', '-am', 'candidate')
            candidate = self.git(repo, 'rev-parse', 'HEAD')
            write_sources(sources, ['alpha', 'refused'])
            common = ['--repo', str(repo), '--baseline', baseline, '--candidate', candidate,
                      '--source-root', str(sources), '--fiscal-years', '2024', '--jobs', '2']
            with contextlib.redirect_stdout(io.StringIO()):
                code = tool.main(common + ['--output-dir', str(Path(tmp, 'out1')), '--fail-on', 'OK_TO_FAIL'])
                flagged = tool.main(common + ['--output-dir', str(Path(tmp, 'out2')), '--fail-on', 'FAIL_TO_OK'])
                littered = tool.main(common + ['--output-dir', str(Path(tmp, 'out3')), '--companies', 'litter'])
                for invalid in ('nosuch', ',', 'alpha,alpha'):
                    with self.subTest(companies=invalid), self.assertRaises(SystemExit):
                        tool.main(common + ['--output-dir', str(Path(tmp, 'bad', invalid)), '--companies', invalid])
            summary = Path(tmp, 'out1', 'summary.md').read_text()
            manifest = json.loads(Path(tmp, 'out1', 'manifest.json').read_text())
            littered_summary = Path(tmp, 'out3', 'summary.md').read_text()
            worktrees = self.git(repo, 'worktree', 'list')
        self.assertEqual((code, flagged, littered), (tool.EXIT_COMPLETE, tool.EXIT_FAIL_ON, tool.EXIT_INCOMPLETE))
        self.assertIn('result: COMPLETE', summary)
        self.assertIn('`refused:2024`', summary)
        self.assertIn(candidate, summary)
        self.assertEqual(manifest['versions']['candidate']['parents'], [baseline])
        # A file the producer leaves in its code worktree, even untracked, makes the run incomplete.
        self.assertIn('result: INCOMPLETE', littered_summary)
        self.assertIn('generated.cfg', littered_summary)
        # 'litter' is registered only by the candidate, so the scope is not a baseline subset.
        self.assertIn("outside the baseline registry: ['litter']", littered_summary)
        self.assertNotIn('SUBSET of the baseline registry', littered_summary)
        self.assertEqual(len(worktrees.splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
