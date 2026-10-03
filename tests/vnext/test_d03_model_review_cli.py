import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext import test_d03_model_processing as fixture
from vnext import d03_model_processing as model
from vnext.native_unit_index import evidence_json_bytes

spec = importlib.util.spec_from_file_location('d03_review_cli', model.ROOT/'tools/vnext_d03_model_review.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class D03ModelReviewCliTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.D03ModelProcessingTest()
        self.fixture.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        packet = self.fixture.packet()
        (self.root/'request.bin').write_bytes(packet['request_body'])
        (self.root/'response.bin').write_bytes(packet['response_body'])
        self.manifest = {'company_id': 'fixture_company',
            'source_sha256': hashlib.sha256(evidence_json_bytes(self.fixture.source)).hexdigest(),
            'requests': [{'request_path': 'request.bin', 'response_path': 'response.bin',
                'request_sha256': packet['expected_request_sha256'],
                'response_sha256': packet['expected_response_sha256']}]}
        self.path = self.root/'input.json'
        self.path.write_text(json.dumps(self.manifest))
        self.output = self.root/'pending'
        self.reader = patch.object(model, 'prepare_regulatory_semantic_source', return_value=self.fixture.source)
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def save(self):
        return cli.save(manifest_path=self.path, data_root=self.root, output_root=self.output)[0]

    def snapshot(self):
        return {str(p.relative_to(self.output)): p.read_bytes()
                for p in self.output.rglob('*') if p.is_file()}

    def test_cli_save_read_repeat_exact_pending_identity(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, cli.main(['save', '--manifest', str(self.path), '--data-root', str(self.root),
                                         '--output-root', str(self.output)]))
        saved = json.loads(output.getvalue())
        before = self.snapshot()
        self.save()
        self.assertEqual(before, self.snapshot())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, cli.main(['read', '--data-root', str(self.root), '--output-root', str(self.output),
                '--company', 'fixture_company', '--candidate-hash', saved['candidate_hash'],
                '--review-unit-hash', saved['review_unit_hash']]))
        self.assertEqual(saved, json.loads(output.getvalue()))
        self.assertEqual('PENDING', saved['status'])
        self.assertFalse(saved['native_result_created'])
        self.assertFalse(saved['provider_attempt_created'])

    def test_interrupted_save_has_no_record_completion_and_exact_resume(self):
        original = cli.write_immutable_bytes
        calls = []
        def interrupt(**kw):
            calls.append(kw['path'])
            if len(calls) == 4:
                raise OSError('simulated process interruption')
            original(**kw)
        with patch.object(cli, 'write_immutable_bytes', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.save()
        self.assertFalse((self.output/'records.jsonl').exists())
        with self.assertRaises(FileNotFoundError):
            cli.read_development_company_assessment(directory=self.output, data_root=self.root,
                company_id='fixture_company', expected_candidate_hash='not-complete',
                expected_review_unit_hash='not-complete')
        before = self.snapshot()
        out = self.save()
        for name, raw in before.items():
            self.assertEqual(raw, (self.output/name).read_bytes())
        self.assertEqual('PENDING', out['records'][3]['status'])

    def test_changed_input_refused_without_touching_previous_package(self):
        self.save()
        before = self.snapshot()
        (self.root/'response.bin').write_bytes((self.root/'response.bin').read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'EXTERNAL_WIRE_CHANGED'):
            self.save()
        self.assertEqual(before, self.snapshot())
        self.manifest['requests'][0]['response_sha256'] = hashlib.sha256((self.root/'response.bin').read_bytes()).hexdigest()
        self.path.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(RuntimeError, 'Immutable request artifact changed'):
            self.save()
        self.assertEqual(before, self.snapshot())

    def test_output_code_live_ledger_and_alias_refused(self):
        from vnext.canonical import strict_json_file
        live = Path(strict_json_file(path=model.ROOT/'config/issue28_continuous_calls_v1.json')['budget_root'])
        for output in [model.ROOT/'forbidden-d03-review', live/'forbidden-d03-review']:
            with self.assertRaises(ValueError):
                cli.save(manifest_path=self.path, data_root=self.root, output_root=output)
        alias = self.root/'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ALIAS_OR_RELATIVE'):
            cli.save(manifest_path=self.path, data_root=self.root, output_root=alias/'pending')


if __name__ == '__main__':
    unittest.main()
