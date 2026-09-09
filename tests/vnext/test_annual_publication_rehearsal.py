"""Exercise a prepared real-candidate bundle; no validator or approval is mocked.

Run with ANNUAL_PUBLICATION_TEST_ROOT and ANNUAL_PUBLICATION_TEST_ID. The
publication root must be the new isolated rehearsal workspace, never actual R3.
Only native fault checkpoints are injected; all graph/source/publication gates
remain real. Missing supplied real material is an explicit SKIP, not acceptance.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

from vnext import annual_publication as annual, annual_adoption as adoption
from vnext import publication as pub, invocation_control as controller
from vnext.canonical import canonical_json_bytes, content_hash
from vnext.run_store import RunStoreError
from vnext.batch_workflow import BatchWorkflowError


class HardCrash(BaseException):
    pass


def proof(path):
    data = path.read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}


def save(path, value):
    path.write_bytes(canonical_json_bytes(value=value) + b'\n')


class AnnualPublicationRehearsalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        supplied = os.environ.get('ANNUAL_PUBLICATION_TEST_ROOT')
        cls.identity = os.environ.get('ANNUAL_PUBLICATION_TEST_ID')
        if not supplied or not cls.identity:
            raise unittest.SkipTest('Requires an actually prepared real-candidate isolated publication')
        cls.root = Path(supplied).resolve()
        annual._marker(cls.root)
        cls.directory = cls.root / 'outputs/publications' / cls.identity
        cls.manifest = pub.verify_publication_bundle(bundle_dir=cls.directory)
        cls.pin = annual._Verified(annual._FACTORY, cls.manifest)
        cls.before = {name: proof(annual.ROOT / name) for name in json.loads(
            (annual.ROOT / 'docs/evidence/annual_runtime/repair/post-live-protection.json').read_text())['files']}
        cls.original_candidate = Path(adoption.read(cls.directory, annual.SNAPSHOT + '/context.json')['origin']['candidate_directory'])
        cls.original_files = adoption._tree_files(root=cls.original_candidate)
        cls.log = []

    @classmethod
    def tearDownClass(cls):
        assert {name: proof(annual.ROOT / name) for name in cls.before} == cls.before
        assert adoption._tree_files(root=cls.original_candidate) == cls.original_files
        output = os.environ.get('ANNUAL_PUBLICATION_TEST_REPORT')
        if output:
            save(Path(output), {'status': 'COMPLETED_CHECK_LOG', 'publication_id': cls.identity,
                'checks': cls.log, 'actual_r3_and_original_candidate_unchanged': True,
                'new_provider_paid_sec_calls': [0, 0, 0]})

    def setUp(self):
        patch = mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        patch.start(); self.addCleanup(patch.stop)
        real = subprocess.check_output
        def local_only(argv, *args, **kwargs):
            if argv[0] == 'gh':
                raise AssertionError('Repeated prepare must not query approval or request again')
            return real(argv, *args, **kwargs)
        patch = mock.patch.object(subprocess, 'check_output', side_effect=local_only)
        patch.start(); self.addCleanup(patch.stop)

    def test_complete_flow_faults_and_cold_source_reads(self):
        with annual._verified(self.pin):
            annual.switch(publication_root=self.root, publication_id=self.identity, operation='rollback')
            old = annual.read_version(publication_root=self.root)
            self.assertEqual(self.manifest['previous_publication_id'], old['publication_id'])
            def fail_before_pointer(*, fault_point):
                if fault_point == 'MID_MIRROR_WRITE':
                    raise OSError('INJECTED_MIRROR_WRITE_FAILURE')
            with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=fail_before_pointer):
                with self.assertRaises(pub.PublicationError):
                    annual.switch(publication_root=self.root, publication_id=self.identity, operation='publish')
            self.assertEqual(old, annual.read_version(publication_root=self.root))
            self.log.append({'check': 'SOFT_SWITCH_FAILURE_OLD_COMPLETE_VIEW', 'status': 'PASS'})
            # Direct low-level calls lack the annual edge capability; formal
            # commit also refuses the recorded-credit artifact.
            with self.assertRaises((ValueError, pub.PublicationError)):
                pub._commit_recorded_sandbox_publication(publication_root=self.root, publication_id=self.identity,
                    expected_active_publication_id=old['publication_id'], committed_at_utc=annual.utc())
            with self.assertRaises(pub.PublicationError):
                pub._commit_publication(publication_root=self.root, publication_id=self.identity,
                    expected_active_publication_id=old['publication_id'], committed_at_utc=annual.utc())
            self.log.append({'check': 'LOW_LEVEL_AND_FORMAL_AUTHORITY_REFUSED', 'status': 'PASS'})
            for point, expected_after_recovery in [
                ('MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT', old['publication_id']),
                ('POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT', self.identity),
            ]:
                def crash(*, fault_point):
                    if fault_point == point:
                        raise HardCrash(point)
                with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=crash):
                    with self.assertRaises(HardCrash):
                        annual.switch(publication_root=self.root, publication_id=self.identity, operation='publish')
                with self.assertRaises(pub.PublicationError):
                    pub.PublicationView.open(publication_root=self.root)
                recovered = annual.switch(publication_root=self.root, publication_id=self.identity, operation='recover')
                self.assertEqual(expected_after_recovery, recovered['publication_id'])
                self.log.append({'check': point, 'status': 'PASS', 'recovered_publication_id': recovered['publication_id']})
            new = annual.read_version(publication_root=self.root)
            self.assertEqual(327, new['public_row_count'])
            self.assertEqual({'B01', 'B10'}, {r['metric_id'] for r in new['selected_rows']})
            self.assertEqual(2, len(new['verified_source_locations']))
            view = pub.PublicationView.open(publication_root=self.root)
            for source in new['verified_source_locations']:
                self.assertEqual(source['sha256'], hashlib.sha256(view.read_bytes(relative_path=source['bundle_relative_path'])).hexdigest())
            batch = json.loads(view.read_bytes(relative_path=annual.BATCH))
            self.assertEqual((240, 2, 238), (len(batch['cumulative_result_bindings']), batch['selected_result_count'], batch['inherited_result_count']))
            pointer = (self.root / 'outputs/active_publication.json').read_bytes()
            repeated = annual.switch(publication_root=self.root, publication_id=self.identity, operation='publish')
            self.assertEqual('ALREADY_ACTIVE_NO_SWITCH', repeated['status'])
            self.assertEqual(pointer, (self.root / 'outputs/active_publication.json').read_bytes())
            previous = annual.switch(publication_root=self.root, publication_id=self.identity, operation='rollback')
            self.assertEqual(old['publication_id'], previous['publication_id'])
            restored = annual.switch(publication_root=self.root, publication_id=self.identity, operation='restore')
            self.assertEqual(new, restored)
            self.log.append({'check': 'COMPLETE_240_327_SOURCE_READ_ROLLBACK_RESTORE_AND_DEDUP', 'status': 'PASS'})
        # Independent generic validation/cold replay outside the verification pin.
        files = adoption._tree_files(root=self.directory)
        directories = {p.relative_to(self.directory).as_posix() for p in self.directory.rglob('*') if p.is_dir()}
        self.assertEqual(self.identity, pub.PublicationView.open(publication_root=self.root).publication_id)
        self.assertEqual(files, adoption._tree_files(root=self.directory))
        self.assertEqual(directories, {p.relative_to(self.directory).as_posix() for p in self.directory.rglob('*') if p.is_dir()})
        history = controller.prepare_historical_annual_invocation_view(repo_root=self.directory / annual.SNAPSHOT / 'data', requirement_id='issue_28_v6')
        invocation = json.loads(next((self.directory / annual.SNAPSHOT / 'candidate/invocation_control/plans').glob('*.json')).read_text())
        with self.assertRaises(controller.InvocationControlError):
            controller.execute_successor_invocation(repo_root=self.directory / annual.SNAPSHOT / 'data', authority=history, plan=invocation)
        self.log.append({'check': 'COLD_REPLAY_NO_WRITES_HISTORICAL_VIEW_CANNOT_EXECUTE', 'status': 'PASS'})

    def test_rebound_bundle_counterexamples(self):
        # Every negative uses a copy, recomputes outer file/manifest identities,
        # and must still fail native reconstruction before it can be activated.
        cases = ['wrong_source', 'foreign_b01_run', 'missing_b10_result', 'runtime_code',
                 'implementation_tree', 'formal_credit', 'disguised_type', 'missing_evidence']
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                directory = Path(temporary) / '.rebound'
                shutil.copytree(self.directory, directory)
                snapshot = directory / annual.SNAPSHOT
                context = adoption.read(snapshot, 'context.json')
                meta = adoption.read(directory, annual.META)
                manifest = copy.deepcopy(self.manifest)
                if case == 'wrong_source':
                    source = context['origin']['plan']['prepared_input']['companyfacts_input']['source_repo_relative_path']
                    path = snapshot / 'data' / source
                    value = json.loads(path.read_text()); value['cik'] = 1
                    path.write_text(json.dumps(value) + '\n')
                    context['data_files'][source] = proof(path); save(snapshot / 'context.json', context)
                elif case in {'foreign_b01_run', 'missing_b10_result'}:
                    if case == 'foreign_b01_run':
                        path = snapshot / 'candidate/b01/manifest.json'; value = json.loads(path.read_text())
                        value['run_id'] += ':foreign'; save(path, value)
                    else:
                        path = snapshot / 'candidate/b10/records.jsonl'
                        values = [json.loads(line) for line in path.read_text().splitlines()]
                        path.write_bytes(b''.join(canonical_json_bytes(value=v) for v in values if v['record_type'] != 'METRIC_RESULT'))
                    relative = path.relative_to(snapshot / 'candidate').as_posix()
                    context['candidate_files'][relative] = proof(path); save(snapshot / 'context.json', context)
                elif case == 'runtime_code':
                    path = directory / 'internal/annual_runtime/tools/check_vnext_semantics.py'
                    canary = Path(temporary) / 'BUNDLE_CODE_EXECUTED'
                    path.write_text('from pathlib import Path\nPath(' + repr(str(canary)) + ').write_text("bad")\n')
                    meta['runtime_files']['tools/check_vnext_semantics.py'] = proof(path)
                    meta['scans']['semantic']['source_hashes']['tools/check_vnext_semantics.py'] = proof(path)['sha256']
                    save(directory / annual.META, meta)
                elif case == 'implementation_tree':
                    meta['implementation_tree'] = 'sha256:' + '0' * 64; save(directory / annual.META, meta)
                elif case == 'formal_credit':
                    manifest['publication_credit'] = 'LIVE'
                elif case == 'disguised_type':
                    manifest['record_type'] = 'SUCCESSOR_PUBLICATION_MANIFEST'
                    del manifest['publication_credit'], manifest['annual_adoption_receipt_id']
                else:
                    path = snapshot / 'candidate/b10/review_decisions.jsonl'; path.write_bytes(b'')
                    context['candidate_files']['b10/review_decisions.jsonl'] = proof(path); save(snapshot / 'context.json', context)
                for entry in manifest['files']:
                    entry.update(proof(directory / entry['path']))
                body = {k: v for k, v in manifest.items() if k not in {'record_type', 'publication_id'}}
                manifest['publication_id'] = 'publication_' + content_hash(value=body)[7:]
                save(directory / 'publication_manifest.json', manifest)
                with self.assertRaises((ValueError, pub.PublicationError, KeyError, RunStoreError, BatchWorkflowError)) as caught:
                    pub.verify_publication_bundle(bundle_dir=directory)
                expected = {
                    'wrong_source': 'Request-ledger locator evidence is invalid',
                    'foreign_b01_run': 'ANNUAL_STRUCTURED_RUN_OR_SOURCE_CHANGED',
                    'missing_b10_result': 'Reviewed Result exact set differs',
                    'missing_evidence': 'Review unit has no effective decision',
                    'runtime_code': 'ANNUAL_RELEASE_RUNTIME_CHANGED',
                    'implementation_tree': 'ANNUAL_RELEASE_RUNTIME_CHANGED',
                    'formal_credit': 'Publication manifest record is invalid',
                    'disguised_type': 'Publication bundle file exact set differs',
                }
                self.assertIn(expected[case], str(caught.exception))
                self.assertNotIn('JSONL contains an empty record', str(caught.exception))
                self.assertFalse((Path(temporary) / 'BUNDLE_CODE_EXECUTED').exists())
                self.log.append({'check': 'REBOUND_' + case.upper(), 'status': 'PASS', 'rejection': str(caught.exception)})
        with annual._verified(self.pin):
            self.assertEqual(self.identity, annual.read_version(publication_root=self.root)['publication_id'])

    def test_repeated_prepare_does_not_publish_or_query_approval(self):
        before_pointer = (self.root / 'outputs/active_publication.json').read_bytes()
        before_ids = {p.name for p in (self.root / 'outputs/publications').iterdir()}
        prepared = annual.prepare(candidate_dir=self.original_candidate, publication_root=self.root)
        self.assertEqual('REUSED_PREPARED_PUBLICATION', prepared['status'])
        self.assertEqual(self.identity, prepared['publication_id'])
        self.assertEqual(before_pointer, (self.root / 'outputs/active_publication.json').read_bytes())
        self.assertEqual(before_ids, {p.name for p in (self.root / 'outputs/publications').iterdir()})
        self.log.append({'check': 'REPEAT_PREPARE_NO_NEW_APPROVAL_CALL_OR_PUBLICATION', 'status': 'PASS'})


if __name__ == '__main__':
    unittest.main()
