"""The CI partition keeps the inherited selector contract and worker limits."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import run_foundation_ci as ci


class FoundationCiPartitionTest(unittest.TestCase):
    def test_all_inherited_selectors_are_kept_exactly_once(self):
        result=ci.partition()
        self.assertEqual(set(ci.inherited.FAST_TESTS),
                         set(result['fast']) | set(result['source-material']))
        self.assertFalse(set(result['fast']) & set(result['source-material']))
        self.assertEqual(len(ci.inherited.FAST_TESTS),
                         len(result['fast'])+len(result['source-material']))
        self.assertIn('tests.vnext.test_financial_duration',result['source-material'])
        # v2 already recognizes this whole-table original as needing a
        # different execution shape. Preserve it whole under material limits.
        self.assertIn(ci.v2.REPLACED,result['source-material'])
        self.assertNotIn(ci.v2.REPLACED,result['fast'])

    def test_duplicate_inherited_selector_is_rejected(self):
        original=ci.inherited.FAST_TESTS
        with patch.object(ci.inherited,'FAST_TESTS',(*original,original[0])):
            with self.assertRaisesRegex(ValueError,'SELECTOR_COVERAGE_CHANGED'):
                ci.partition()

    def test_cli_uses_original_keyword_worker_and_preserves_failure(self):
        for suite in ('fast','source-material'):
            with self.subTest(suite=suite):
                out=io.StringIO()
                with patch.object(sys,'argv',['ci','--suite',suite,'--jobs','1']), \
                     patch.object(ci,'partition',return_value={'fast':('example',),
                         'source-material':('example',)}), \
                     patch.object(ci.inherited,'_run_case',return_value={
                         'test':'example','return_code':124}) as fast, \
                     patch.object(ci.v2,'_run_source_case',return_value={
                         'test':'example','return_code':124}) as source, \
                     redirect_stdout(out):
                    self.assertEqual(1,ci.main())
                self.assertEqual('FAILED',json.loads(out.getvalue())['status'])
                self.assertEqual(124,json.loads(out.getvalue())['tests'][0]['return_code'])
                if suite=='fast':
                    fast.assert_called_once_with(test_name='example')
                    source.assert_not_called()
                else:
                    source.assert_called_once_with('example')
                    fast.assert_not_called()


if __name__ == '__main__':
    unittest.main()
