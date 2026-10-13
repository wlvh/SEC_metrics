"""Coverage, shared fixtures and real failures in the current CI entry."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import types
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import run_foundation_ci as ci


class FoundationCiPartitionTest(unittest.TestCase):
    def test_material_worker_rejects_skipped_or_empty_required_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'tests').mkdir()
            (root/'tests/required_unittests.py').write_bytes((ROOT/'tests/required_unittests.py').read_bytes())
            (root/'fixture_material.py').write_text('import unittest\n'
                'class Passed(unittest.TestCase):\n'
                ' def test_unit(self):self.assertEqual("USD","USD")\n'
                'class Skipped(unittest.TestCase):\n'
                ' @unittest.skip("constructed missing source")\n'
                ' def test_required(self):pass\n'
                'class Mixed(Passed,Skipped):pass\n'
                'class Empty(unittest.TestCase):pass\n'
                'class Failed(unittest.TestCase):\n'
                ' def test_unit(self):self.assertEqual("shares","USD")\n')
            with patch.object(ci.v2.inherited,'REPO_ROOT',root):
                passed=ci.v2._run_source_case('fixture_material.Passed')
                skipped=ci.v2._run_source_case('fixture_material.Skipped')
                empty=ci.v2._run_source_case('fixture_material.Empty')
                mixed=ci.v2._run_source_case('fixture_material.Mixed')
                failed=ci.v2._run_source_case('fixture_material.Failed')
            self.assertEqual(0,passed['return_code'])
            self.assertNotEqual(0,skipped['return_code'])
            self.assertNotEqual(0,empty['return_code'])
            self.assertNotEqual(0,mixed['return_code'])
            self.assertNotEqual(0,failed['return_code'])
            self.assertIn('constructed missing source',skipped['stdout_tail']+skipped['stderr_tail'])
            self.assertEqual(ci.v2.SOURCE_TIMEOUT_SECONDS,skipped['timeout_seconds'])
            out=io.StringIO()
            with patch.object(ci.v2.inherited,'REPO_ROOT',root), \
                 patch.object(ci,'partition',return_value={'fast':(),
                     'source-material':('fixture_material.Mixed',),'retired':()}), \
                 patch.object(sys,'argv',['ci','--suite','source-material','--jobs','1']), \
                 redirect_stdout(out):
                self.assertEqual(1,ci.main())
            report=json.loads(out.getvalue())
            self.assertEqual('FAILED',report['status'])
            self.assertEqual(1,report['tests'][0]['return_code'])

    def test_material_timeout_still_retains_124_and_original_limit(self):
        import subprocess
        failure=subprocess.TimeoutExpired(['required-unittest'],ci.v2.SOURCE_TIMEOUT_SECONDS,
            output=b'partial source output',stderr=b'partial diagnostic')
        with patch.object(ci.v2.subprocess,'run',side_effect=failure):
            result=ci.v2._run_source_case('constructed.source')
        self.assertEqual(124,result['return_code'])
        self.assertEqual(ci.v2.SOURCE_TIMEOUT_SECONDS,result['timeout_seconds'])
        self.assertIn('partial source output',result['stdout_tail'])
        self.assertIn('SOURCE_MATERIAL_TIMEOUT_SECONDS=',result['stderr_tail'])

    def test_material_and_old_object_readers_fetch_only_needed_versions(self):
        body=(ROOT/'.github/workflows/vnext-fast.yml').read_text()
        material=body.split('  inherited-source-material:',1)[1].split('  main-foundation:',1)[0]
        reader=body.split('  main-foundation:',1)[1].split('  # #54',1)[0]
        self.assertIn('fetch-depth: 1',material)
        self.assertIn('fetch-depth: 1',reader)
        self.assertIn('git fetch --no-tags --depth=1 origin',reader)
        self.assertIn('requirements/issue_28_v1/baseline_manifest.json',reader)
        self.assertIn('git show',reader)
        self.assertNotIn('fetch-depth: 0',reader)

    def test_all_inherited_selectors_are_active_or_explicitly_retired_once(self):
        result=ci.partition()
        declared=(*ci.inherited.FAST_TESTS,*ci.v2._FEATURE_SELECTORS['fast'],
                  *ci.v2._FEATURE_SELECTORS['source-material'])
        self.assertEqual(set(declared),
                         set(result['fast']) | set(result['source-material']) | set(result['retired']))
        self.assertFalse(set(result['fast']) & set(result['source-material']))
        self.assertEqual(len(declared),
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

    def test_additive_feature_selectors_reach_their_declared_ci_tiers(self):
        features={'fast':('tests.feature.fast',),'source-material':('tests.feature.original',)}
        with patch.object(ci.v2,'_FEATURE_SELECTORS',features):
            result=ci.partition()
        self.assertIn('tests.feature.fast',result['fast'])
        self.assertNotIn('tests.feature.fast',result['source-material'])
        self.assertIn('tests.feature.original',result['source-material'])
        self.assertNotIn('tests.feature.original',result['fast'])

    def test_duplicate_feature_or_inherited_overlap_is_rejected(self):
        for features in ({'fast':(ci.inherited.FAST_TESTS[0],),'source-material':()},
                         {'fast':('tests.feature.same',),'source-material':('tests.feature.same',)}):
            with self.subTest(features=features),patch.object(ci.v2,'_FEATURE_SELECTORS',features):
                with self.assertRaisesRegex(ValueError,'SELECTOR_COVERAGE_CHANGED'):
                    ci.partition()

    def test_feature_declared_test_really_executes_through_the_workflow_cli(self):
        events=[]
        class Base(unittest.TestCase):
            def test_unit(self):events.append('baseline')
        class Feature(unittest.TestCase):
            def test_period(self):events.append('feature');self.assertLess('2025-01-01','2025-12-31')
        module=types.ModuleType('_ci_declared_feature');module.Base=Base;module.Feature=Feature
        out=io.StringIO()
        with patch.dict(sys.modules,{'_ci_declared_feature':module}), \
             patch.object(ci.inherited,'FAST_TESTS',('_ci_declared_feature.Base',)), \
             patch.object(ci.v2,'_FEATURE_SELECTORS',{'fast':('_ci_declared_feature.Feature',),'source-material':()}), \
             patch.object(sys,'argv',['ci','--suite','fast']),redirect_stdout(out):
            self.assertEqual(ci.main(),0)
        report=json.loads(out.getvalue())
        self.assertEqual(events,['baseline','feature'])
        self.assertEqual(report['tests'][0]['test_count'],2)
        self.assertEqual(report['total_feature_selectors'],1)

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

    def test_a_required_suite_that_only_skips_is_not_a_pass(self):
        class Pending(unittest.TestCase):
            @unittest.skip('constructed unavailable required input')
            def test_required(self): pass
        module=types.ModuleType('_ci_pending_example');module.Pending=Pending
        with patch.dict(sys.modules,{'_ci_pending_example':module}):
            result=ci.run_fast_suite(('_ci_pending_example.Pending',))
        self.assertEqual(result['test_count'],1)
        self.assertEqual(len(result['skips']),1)
        self.assertEqual(result['return_code'],1)


if __name__ == '__main__':
    unittest.main()
