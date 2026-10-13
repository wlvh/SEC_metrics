"""Feature declarations preserve test coverage without editing one append point."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))


class SelectorRegistryTest(unittest.TestCase):
    def load(self,path,**kwargs):
        from feature_test_selectors import load_feature_selectors
        return load_feature_selectors(directory=path,**kwargs)

    def test_two_independent_feature_files_are_both_consumed_in_stable_order(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'two.json').write_text(json.dumps({'fast':['tests.two']}))
            (directory/'one.json').write_text(json.dumps({'fast':['tests.one'],'source-material':['tests.original']}))
            self.assertEqual(self.load(directory),{'fast':('tests.one','tests.two'),
                'source-material':('tests.original',)})

    def test_missing_or_malformed_declaration_cannot_look_like_no_tests(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            with self.assertRaises(ValueError):self.load(directory/'missing')
            for contents in ('{','{"fast":["tests.one"],"fast":["tests.two"]}',json.dumps({'other':['tests.one']}),
                             json.dumps({'fast':'tests.one'}),json.dumps({'fast':['']}),
                             json.dumps({'fast':['tests.one','tests.one']})):
                with self.subTest(contents=contents):
                    (directory/'bad.json').write_text(contents)
                    with self.assertRaises(ValueError):self.load(directory)

    def test_duplicates_across_feature_files_or_suites_are_rejected(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'one.json').write_text(json.dumps({'fast':['tests.one']}))
            (directory/'two.json').write_text(json.dumps({'source-material':['tests.one']}))
            with self.assertRaises(ValueError):self.load(directory)

    def test_duplicate_of_existing_selector_is_rejected(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'one.json').write_text(json.dumps({'fast':['tests.one']}))
            with self.assertRaises(ValueError):self.load(directory,existing_fast=('tests.one',))

    def test_actual_runner_keeps_all_prior_selectors_order_and_material_shards(self):
        import run_fast_tests_v2 as runner
        old=json.loads((ROOT/'docs/evidence/issue28_feature_test_registration_20261013/before-selectors.json').read_text())
        self.assertEqual(tuple(s for s in runner.FAST_TESTS if s in old['fast']),tuple(old['fast']))
        self.assertEqual(tuple(s for s in runner.SOURCE_TESTS if s in old['source-material']),tuple(old['source-material']))
        for index in (0,1):
            self.assertEqual(tuple(s for s in runner._selected_tests('source-material',index,2)
                if s in old['source-material']),tuple(old['source_shards'][index]))
        self.assertEqual(len(set((*runner.FAST_TESTS,*runner.SOURCE_TESTS))),
                         len(runner.FAST_TESTS)+len(runner.SOURCE_TESTS))
