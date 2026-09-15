"""Actual frozen text Run to the existing public CSV schemas."""
import csv
import io
from pathlib import Path
import tempfile
import unittest

from vnext.normal_run_v2 import install_normal_inputs, create_normal_run
from vnext.normal_text_projection_v2 import render_normal_text_run
from vnext.publication import METRIC_FIELDS, EVIDENCE_FIELDS


class NormalProjectionMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='normal-projection-material-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.data = Path(cls.temporary.name) / 'data'
        cls.run_dir = Path(cls.temporary.name) / 'run'
        install_normal_inputs(data_root=cls.data, company_id='marriott_international', metric_id='D01')
        cls.native = create_normal_run(data_root=cls.data, run_dir=cls.run_dir,
            company_id='marriott_international', metric_id='D01', freeze=True)

    def test_exact_text_and_source_quotes_survive_existing_csv_roundtrip(self):
        rendered = render_normal_text_run(data_root=self.data, run_dir=self.run_dir)
        matrix = list(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
        evidence = list(csv.DictReader(io.StringIO(rendered['files']['metric_evidence.csv'].decode())))
        self.assertEqual([rendered['row']], matrix)
        self.assertEqual(rendered['evidence'], evidence)
        self.assertEqual(set(METRIC_FIELDS), set(matrix[0]))
        self.assertTrue(all(set(EVIDENCE_FIELDS) == set(r) for r in evidence))
        result = self.native['result']
        self.assertEqual(result['value'], matrix[0]['value'])
        self.assertEqual([i['text'] for i in result['text_payload']['items']],
                         [r['evidence_quote'] for r in evidence])
        self.assertEqual('TEXT_QUAL', matrix[0]['status'])
        self.assertEqual(('10-K', '2026-02-10', '2025-12-31'),
                         (matrix[0]['form'], matrix[0]['filed_date'], matrix[0]['period_end']))
        self.assertEqual('FROZEN', rendered['receipt']['run_status'])
        self.assertEqual(3, len(rendered['receipt']['input_source_reference_ids']))
        self.assertFalse(rendered['receipt']['production_authorized'])
        self.assertEqual('CANDIDATE_ONLY', rendered['receipt']['status'])

    def test_repeated_render_has_identical_rows_evidence_and_receipt(self):
        first = render_normal_text_run(data_root=self.data, run_dir=self.run_dir)
        second = render_normal_text_run(data_root=self.data, run_dir=self.run_dir)
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
