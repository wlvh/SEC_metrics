"""One real preparation, small persistence/coordinate regressions thereafter."""
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext.ordinary_saved_result import create_saved_result, read_saved_result

ROOT = Path(__file__).resolve().parents[2]


class OrdinarySavedResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.saved = Path(cls.directory.name)/'calculated'
        with patch('scripts.vnext.normal_run_v3.load_requirement_snapshot',
                   side_effect=AssertionError('No recursive requirement in this current path')):
            cls.actual = create_saved_result(source_root=ROOT, output_root=cls.saved,
                company_id='marriott_international', metric_id='B01')

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_real_source_value_period_scope_and_csv_evidence(self):
        result = self.actual['result']
        self.assertEqual((result['value'], result['unit'], result['quality']),
                         ('26186000000', 'USD', 'EXACT'))
        self.assertEqual((result['period_start'], result['period_end']), ('2025-01-01','2025-12-31'))
        row, = csv.DictReader(io.StringIO(self.actual['files']['metrics_matrix.csv'].decode()))
        self.assertEqual((row['value'], row['unit'], row['fiscal_year'], row['status']),
                         ('26186000000','USD','2025','OK'))
        self.assertEqual(row['accession'], '0001048286-26-000007')
        self.assertIn('registrant', row['context_or_dimension'])
        evidence = list(csv.DictReader(io.StringIO(self.actual['files']['metric_evidence.csv'].decode())))
        self.assertTrue(evidence)
        self.assertTrue(all(e['content_sha256'] and e['repo_relative_path'] for e in evidence))
        self.assertEqual(self.actual['receipt']['source_validation'], 'SOURCE_CALCULATOR_AND_RECORD_CHECKS')
        self.assertFalse((self.saved/'requirements').exists())
        self.assertFalse((self.saved/'evidence').exists())

    def test_read_does_not_recompute_and_repeated_output_is_not_overwritten(self):
        with patch('scripts.vnext.ordinary_saved_result.prepare_ordinary_zero_ai_run_input',
                   side_effect=AssertionError('Read must not calculate')):
            self.assertEqual(read_saved_result(output_root=self.saved)['result'], self.actual['result'])
            with self.assertRaisesRegex(ValueError, 'OUTPUT_EXISTS'):
                create_saved_result(source_root=ROOT, output_root=self.saved,
                    company_id='marriott_international', metric_id='B01')

    def test_company_period_and_unit_mismatch_rejected(self):
        for field, value, reason in [('company_id','pfizer','COORDINATE_CHANGED'),
                                    ('target_period', {'fiscal_year':2025,'period_start':'2024-01-01',
                                     'period_end':'2025-12-31'}, 'PERIOD_CHANGED'),
                                    ('unit','shares','UNIT_CHANGED')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                copied = Path(temp)/'result'; shutil.copytree(self.saved, copied)
                manifest = json.loads((copied/'manifest.json').read_text())
                if field == 'unit':
                    manifest['compiled_specs']['B01']['compiled']['canonical_unit'] = value
                else:
                    manifest[field] = value
                (copied/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, reason):
                    read_saved_result(output_root=copied)

    def test_damage_and_incomplete_write_are_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp)/'result'; shutil.copytree(self.saved, copied)
            (copied/'metrics_matrix.csv').write_text('broken')
            with self.assertRaisesRegex(ValueError, 'FILE_CHANGED'):
                read_saved_result(output_root=copied)
            (copied/'manifest.json').unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                read_saved_result(output_root=copied)

    def test_failure_is_recorded_without_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'failed'
            with patch('scripts.vnext.ordinary_saved_result.prepare_ordinary_zero_ai_run_input',
                       side_effect=ValueError('Missing required source')):
                with self.assertRaisesRegex(ValueError, 'Missing required source'):
                    create_saved_result(source_root=ROOT, output_root=out,
                        company_id='marriott_international', metric_id='B01')
            self.assertEqual(json.loads((out/'failure.json').read_text())['status'], 'FAILED')
            self.assertFalse((out/'manifest.json').exists())


if __name__ == '__main__': unittest.main()
