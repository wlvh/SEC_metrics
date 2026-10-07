"""Coverage, shared fixtures and real failures in the current CI entry."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import run_foundation_ci as ci


class FoundationCiPartitionTest(unittest.TestCase):
    def test_all_inherited_selectors_are_active_or_explicitly_retired_once(self):
        result=ci.partition()
        self.assertEqual(set(ci.inherited.FAST_TESTS),
                         set(result['fast']) | set(result['source-material']) | set(result['retired']))
        self.assertFalse(set(result['fast']) & set(result['source-material']))
        self.assertEqual(len(ci.inherited.FAST_TESTS),
                         len(result['fast'])+len(result['source-material'])+len(result['retired']))
        self.assertEqual(result['retired'],('tests.vnext.test_normal_candidate_authority',))
        self.assertIn('tests.vnext.test_financial_duration',result['source-material'])
        # v2 already recognizes this whole-table original as needing a
        # different execution shape. Preserve it whole under material limits.
        self.assertIn(ci.v2.REPLACED,result['source-material'])
        self.assertNotIn(ci.v2.REPLACED,result['fast'])
        self.assertTrue(all(not s.startswith(ci.MATERIAL_PREFIXES)
                            for s in result['fast']))

    def test_duplicate_inherited_selector_is_rejected(self):
        original=ci.inherited.FAST_TESTS
        with patch.object(ci.inherited,'FAST_TESTS',(*original,original[0])):
            with self.assertRaisesRegex(ValueError,'SELECTOR_COVERAGE_CHANGED'):
                ci.partition()

    def test_cli_preserves_fast_or_material_failure(self):
        for suite in ('fast','source-material'):
            with self.subTest(suite=suite):
                out=io.StringIO()
                with patch.object(sys,'argv',['ci','--suite',suite,'--jobs','1']), \
                     patch.object(ci,'partition',return_value={'fast':('example',),
                         'source-material':('example',)}), \
                     patch.object(ci,'run_fast_suite',return_value={
                         'test':'example','return_code':124}) as fast, \
                     patch.object(ci.v2,'_run_source_case',return_value={
                         'test':'example','return_code':124}) as source, \
                     redirect_stdout(out):
                    self.assertEqual(1,ci.main())
                self.assertEqual('FAILED',json.loads(out.getvalue())['status'])
                self.assertEqual(124,json.loads(out.getvalue())['tests'][0]['return_code'])
                if suite=='fast':
                    fast.assert_called_once_with(('example',))
                    source.assert_not_called()
                else:
                    source.assert_called_once_with('example')
                    fast.assert_not_called()

    def test_shared_class_preparation_runs_once_and_every_test_executes(self):
        events = []
        class SmallBusiness(unittest.TestCase):
            @classmethod
            def setUpClass(cls): events.append('prepare')
            def test_unit(self):
                events.append('unit'); print('test diagnostic remains inside report')
                self.assertEqual('USD', 'USD')
            def test_period(self): events.append('period'); self.assertLess('2025-01-01', '2025-12-31')
        module = types.ModuleType('_ci_small_example'); module.SmallBusiness = SmallBusiness
        with patch.dict(sys.modules, {'_ci_small_example': module}):
            outside = io.StringIO()
            with redirect_stdout(outside):
                result = ci.run_fast_suite(('_ci_small_example.SmallBusiness.test_unit',
                                           '_ci_small_example.SmallBusiness.test_period'))
        self.assertEqual(events, ['prepare','unit','period'])
        self.assertEqual((result['return_code'], result['test_count']), (0,2))
        self.assertEqual(outside.getvalue(), '')
        self.assertIn('test diagnostic remains inside report', result['diagnostics'])

    def test_assertion_error_missing_selector_and_skip_remain_explicit(self):
        class Broken(unittest.TestCase):
            def test_wrong_unit(self): self.assertEqual('shares', 'USD')
            def test_exception(self): raise ValueError('unresolved source')
            @unittest.skip('explicit pending environment')
            def test_skip(self): pass
        module = types.ModuleType('_ci_broken_example'); module.Broken = Broken
        with patch.dict(sys.modules, {'_ci_broken_example':module}):
            result = ci.run_fast_suite(('_ci_broken_example.Broken', '_ci_broken_example.missing'))
        self.assertEqual(result['return_code'],1)
        self.assertEqual((len(result['failures']), len(result['errors']), len(result['skips'])),(1,2,1))
        self.assertIn('unresolved source', str(result['errors']))


if __name__ == '__main__':
    unittest.main()
