"""A05's explained update is explicit and cannot take over old journals."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext import normal_run_v3 as normal
from vnext import ordinary_a05_formula_update as successor


class A05FormulaSuccessorTest(unittest.TestCase):
    def test_wrong_metric_and_non_boolean_scope_stop_before_source_read(self):
        with self.assertRaisesRegex(ValueError,
                                    'ORDINARY_A05_FORMULA_SCOPE_WRONG_METRIC'):
            normal.prepare_case(data_root=normal.ROOT,
                company_id='jpmorgan_chase',metric_id='B01',a05_formula=True)
        with self.assertRaisesRegex(ValueError,
                                    'ORDINARY_A05_FORMULA_SCOPE_WRONG_METRIC'):
            normal.prepare_case(data_root=normal.ROOT,
                company_id='jpmorgan_chase',metric_id='A05',a05_formula='yes')

    def test_current_operator_uses_a_new_a05_journal_and_keeps_other_metric_route(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'private-state'
            canonical_root = root.resolve()
            def other(**kwargs):
                self.assertEqual(['B01'],kwargs['metric_ids'])
                self.assertEqual(canonical_root,kwargs['state_root'])
                return {'metrics':[{'metric_id':'B01',
                                    'status':'NO_SOURCE_CONTENT_CHANGE'}]}
            def a05(**kwargs):
                self.assertEqual(canonical_root/'metrics/A05-formula-v1',kwargs['state_root'])
                self.assertEqual(['A05'],kwargs['metric_ids'])
                self.assertTrue(kwargs['a05_formula'])
                self.assertFalse((root/'metrics/A05').exists())
                return {'status':'CANDIDATE_READY'}
            with (patch.object(successor,'run_other_metrics',side_effect=other),
                  patch.object(successor.current,'run_once',side_effect=a05)):
                report = successor.run_company(state_root=root,
                    source_root=normal.ROOT,company_id='jpmorgan_chase',
                    metric_ids=['A05','B01'])
            self.assertEqual('UPDATES_READY',report['status'])
            self.assertEqual(['A05','B01'],[m['metric_id'] for m in report['metrics']])
            self.assertEqual({'provider':0,'paid':0,'sec':0},report['calls'])


if __name__ == '__main__':
    unittest.main()
