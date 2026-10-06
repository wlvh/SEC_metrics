"""Company pending-review boundaries; real source/CLI proof is separate."""
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.vnext import company_c02_development as c02
from scripts.vnext import company_result_export as export
from scripts.vnext import company_result_view as view
from scripts.vnext.canonical import content_hash


class CompanyC02DevelopmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.packet = self.base/'packet'; self.packet.mkdir()
        self.trust = self.base/'trust'; self.trust.mkdir()
        for name in c02.MEMBERS:
            p = self.packet/name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('original '+name)
        self.meta = {'record_type': 'COMPANY_C02_DEVELOPMENT_INPUT_V1',
            'company_id': 'sample', 'metric_id': 'C02', 'origin': 'RECORDED_PROGRAM_TEST',
            'files': {n: c02.binding(self.packet/n) for n in sorted(c02.MEMBERS)},
            'new_call_authority': False, 'semantic_acceptance': False, 'production_authorized': False}
        self.seal()
        env = patch.dict(os.environ, {c02.TRUST_VARIABLE: str(self.trust)})
        env.start(); self.addCleanup(env.stop)

    def seal(self):
        self.meta.pop('processing_id', None)
        self.meta['processing_id'] = content_hash(value=self.meta)
        (self.packet/c02.PACKET_FILE).write_text(json.dumps(self.meta))
        (self.trust/(self.meta['processing_id'][7:]+'.json')).write_text(json.dumps(self.meta))

    def auth(self, company='sample'):
        return c02.authenticate_review_input(packet_root=self.packet, company_id=company)

    def test_enrolled_exact_packet_has_no_call_or_acceptance_authority(self):
        self.assertEqual(self.auth(), self.meta)
        self.assertFalse(self.auth()['semantic_acceptance'])

    def test_changed_response_and_native_review_are_rejected(self):
        for name in ('response.bin', 'review.md', 'records.jsonl'):
            with self.subTest(name=name):
                p = self.packet/name; old = p.read_bytes(); p.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'BYTES_CHANGED'): self.auth()
                p.write_bytes(old)

    def test_packet_self_reseal_cannot_enroll_an_answer(self):
        self.meta['origin'] = 'DEVELOPMENT_MODEL'
        self.meta.pop('processing_id')
        self.meta['processing_id'] = content_hash(value=self.meta)
        (self.packet/c02.PACKET_FILE).write_text(json.dumps(self.meta))
        with self.assertRaises((ValueError, FileNotFoundError)): self.auth()

    def test_missing_independent_trust_and_wrong_company_refused(self):
        with self.assertRaisesRegex(ValueError, 'SCOPE_OR_AUTHORITY'): self.auth('other')
        with patch.dict(os.environ, {c02.TRUST_VARIABLE: ''}):
            with self.assertRaisesRegex(ValueError, 'TRUST_REQUIRED'): self.auth()

    def test_extra_answer_or_symlink_is_refused(self):
        p = self.packet/'hidden-answer.json'; p.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'MEMBER_SET'): self.auth()
        p.unlink(); p.symlink_to(self.packet/'response.bin')
        with self.assertRaisesRegex(ValueError, 'ALIAS'): self.auth()

    def test_trust_symlink_and_overlap_refused(self):
        path = self.trust/(self.meta['processing_id'][7:]+'.json')
        raw = path.read_bytes(); path.unlink()
        target = self.base/'trust-copy.json'; target.write_bytes(raw); path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'NOT_TRUSTED'): self.auth()
        with patch.dict(os.environ, {c02.TRUST_VARIABLE: str(self.packet)}):
            with self.assertRaisesRegex(ValueError, 'TRUST_OVERLAP'): self.auth()

    def test_enrolled_authority_or_real_origin_still_refused(self):
        for key, value in [('semantic_acceptance', True), ('new_call_authority', True),
                           ('production_authorized', True), ('origin', 'REAL')]:
            with self.subTest(key=key):
                old = self.meta[key]; self.meta[key] = value; self.seal()
                with self.assertRaisesRegex(ValueError, 'SCOPE_OR_AUTHORITY'): self.auth()
                self.meta[key] = old; self.seal()

    def test_baseline_program_cannot_import_development_review(self):
        from scripts.vnext import normal_run_v3
        with patch.object(normal_run_v3, 'REQUIREMENT_ID', 'issue_28_v13'):
            with self.assertRaisesRegex(ValueError, 'INSTALLED_ORDINARY_RUNTIME_REQUIRED'): c02._runtime()

    def test_no_receipt_means_interrupted_pending_objects_do_not_appear(self):
        root = self.base/'state'; (root/'development/C02/unfinished/pending').mkdir(parents=True)
        current = {'checkpoint_id': 'source', 'company_id': 'sample'}
        result = view.build_company_view(root=root, company_id='sample', current=current)
        self.assertEqual(result['metrics'], [])
        self.assertNotIn('development_reviews', result)

    def test_explicit_pending_row_does_not_duplicate_generic_request_status(self):
        root = self.base/'state'; work = root/'development/C02/example'; work.mkdir(parents=True)
        receipt = {'company_id': 'sample', 'metric_id': 'C02', 'runtime_root': str(self.base/'program'),
            'source_checkpoint_id': 'source', 'requirement_id': 'issue_54_v1',
            'requirement_closure_hash': 'closure', 'candidate_hash': 'candidate',
            'review_unit_hash': 'unit', 'original_candidate_hash': 'old',
            'target': {'period_end': '2025-12-31'}}
        receipt['review_id'] = content_hash(value=receipt)
        (work/'receipt.json').write_text(json.dumps(receipt))
        view.save_execution(root=root, report={'company_id': 'sample', 'source_checkpoint_id': 'source',
            'metrics': [{'metric_id': 'C02', 'status': 'REVIEW_REQUIRED',
                         'development_review_id': receipt['review_id']}], 'period_request': {}})
        result = view.build_company_view(root=root, company_id='sample', current={'checkpoint_id': 'source'})
        self.assertEqual(result['metrics'], [])
        self.assertEqual(len(result['development_reviews']), 1)
        (work/'receipt.json').unlink()
        missing = view.build_company_view(root=root, company_id='sample', current={'checkpoint_id': 'source'})
        self.assertEqual(len(missing['metrics']), 1)
        self.assertEqual(missing['metrics'][0]['result_validity'], 'NO_RESULT')

    def test_pending_export_has_empty_value_and_unresolved_evidence(self):
        root = self.base/'state'; root.mkdir()
        work = root/'development/C02/example'; work.mkdir(parents=True)
        (work/'input/processing/c02').mkdir(parents=True)
        (work/'input/processing/c02/image-metadata.json').write_text('{"policy":"TEST"}')
        (work/'pending').mkdir()
        (work/'pending/review-context.json').write_text(json.dumps({'source_linked_review': {'citations': [
            {'block_index': 1, 'text': 'Board consists of seven directors.'},
            {'block_index': 2, 'text': 'Appointment date not stated.'}]}}))
        entry = {'company_id': 'sample', 'metric_id': 'C02', 'work_root': str(work),
            'development_review_id': 'sha256:'+'a'*64, 'candidate_hash': 'candidate',
            'review_unit_hash': 'unit', 'original_candidate_hash': 'old',
            'period': {'period_start': '2025-01-01', 'period_end': '2025-12-31'},
            'business_metric_completed': False, 'result_validity': 'DEVELOPMENT_PENDING_NOT_REPLAYED'}
        current = {'checkpoint_id': 'source', 'company_id': 'sample'}
        company_view = {'metrics': [], 'development_reviews': [entry]}
        from contextlib import contextmanager
        @contextmanager
        def locked(_): yield root
        out = self.base/'output'
        replayed = {'source_sha256': 'raw', 'facts_and_unresolved': {
            'facts': [{'statement': 'Seven directors', 'source_blocks': [1]}],
            'unresolved': [{'reason': 'Date unclear', 'source_blocks': [2]}]}}
        replayed['files'] = {p.relative_to(work).as_posix(): c02.binding(p) for p in work.rglob('*') if p.is_file()}
        with patch.object(export, 'locked_company', locked), \
             patch.object(export, 'recover_for_read', return_value=current), \
             patch.object(export, 'build_company_view', return_value=company_view), \
             patch.object(c02, 'replay_in_creator', return_value=replayed):
            result = export.export_results(state_root=root, output_root=out, company_id='sample')
        self.assertEqual(result['status'], 'EXPORTED')
        rows = list(csv.DictReader(io.StringIO((out/'metrics_matrix.csv').read_text())))
        self.assertEqual(rows[0]['value'], '')
        self.assertEqual(rows[0]['run_id'], '')
        self.assertEqual(rows[0]['result_validity'], 'DEVELOPMENT_PENDING_NO_RESULT')
        evidence = list(csv.DictReader(io.StringIO((out/'metric_evidence.csv').read_text())))
        self.assertEqual(len(evidence), 2)
        self.assertTrue(any(e['value_raw'] == 'Date unclear' and e['evidence_quote'] == 'Appointment date not stated.' for e in evidence))
        self.assertTrue((out/entry['native_path']/'input/processing/c02/image-metadata.json').is_file())

    def test_missing_fixed_creator_is_not_replayed_with_current_code(self):
        with self.assertRaisesRegex(ValueError, 'FIXED_RUNTIME_REQUIRED'):
            c02.replay_in_creator(root=self.base, entry={'runtime_root': str(self.base/'old')}, runtime_roots=[])

    def test_explicit_current_fixed_program_is_a_valid_creator_not_input_overlap(self):
        from scripts.vnext.company_handoff import ROOT
        work = self.base/'state/development/C02/test'; work.mkdir(parents=True)
        entry = {'runtime_root': str(ROOT), 'work_root': str(work), 'company_id': 'sample',
            'source_checkpoint_id': 'sha256:'+'b'*64, 'development_review_id': 'review'}
        with patch.object(c02.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='{"review_id":"review"}', stderr='')):
            result = c02.replay_in_creator(root=self.base/'state', entry=entry, runtime_roots=[ROOT])
        self.assertEqual(result, {'review_id': 'review', 'files': {}})


if __name__ == '__main__': unittest.main()
