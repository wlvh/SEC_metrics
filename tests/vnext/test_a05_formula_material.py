"""A nonfinancial A05 keeps its legitimate structural N/A through a full Run."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext import normal_run_v3 as normal
from vnext import ordinary_projection as projection


class A05FormulaMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.temp.name)/'data'
        cls.run_dir = Path(cls.temp.name)/'run'
        normal.install_normal_inputs(data_root=cls.data,
            company_id='marriott_international', metric_id='A05',
            a05_formula=True)
        cls.created = normal.create_normal_run(data_root=cls.data,
            run_dir=cls.run_dir, company_id='marriott_international',
            metric_id='A05', a05_formula=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_structural_na_completes_with_no_invented_formula_or_observation(self):
        result = self.created['result']
        self.assertEqual('PUBLISHED', result['publication'])
        self.assertEqual('N_A_STRUCTURAL', result['applicability'])
        self.assertEqual('TRAIT_NOT_APPLICABLE', result['reason_code'])
        self.assertIsNone(result['value'])
        rendered = projection.render_ordinary_run(data_root=self.data,
            run_dir=self.run_dir, _return_replay_context=True)
        self.assertEqual('', rendered['row']['formula'])
        self.assertEqual([], [r for r in rendered['replay_context']['records']
                              if r.get('record_type') == 'VERIFIED_OBSERVATION'
                              and r.get('metric_id') == 'A05'])
        self.assertEqual(result['result_id'],
            next(r for r in rendered['replay_context']['records']
                 if r.get('record_type') == 'METRIC_RESULT'
                 and r.get('metric_id') == 'A05')['result_id'])

    def test_structural_na_with_a_fake_numeric_observation_is_rejected(self):
        with patch.object(projection.projector, '_ordered_observations',
                          return_value=([{'source_binding':
                                          {'selected_branch_id':'average_assets'}}], None)):
            with self.assertRaisesRegex(ValueError,
                                        'ORDINARY_A05_STRUCTURAL_RESULT_CHANGED'):
                projection.render_ordinary_run(data_root=self.data,
                                               run_dir=self.run_dir)


if __name__ == '__main__':
    unittest.main()
