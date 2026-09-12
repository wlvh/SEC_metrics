"""Ordinary Run preparation fixes Spec and dependency sets before dispatch."""
import unittest
from pathlib import Path
import tempfile
import shutil

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_run_specs import installed_ordinary_spec_documents,validate_ordinary_spec_files
from vnext.normal_run_inputs import prepare_ordinary_zero_ai_run_input


class OrdinaryRunInputTest(unittest.TestCase):
    def test_all_catalog_specs_roundtrip_without_changing_semantic_closure(self):
        rows=validate_ordinary_spec_files(repo_root=ROOT)
        self.assertEqual(22,len(rows))
        self.assertEqual(['B01'],rows['B03']['compiled_spec']['compiled']['dependencies'])
        self.assertEqual('ratio',rows['A01']['compiled_spec']['compiled']['canonical_unit'])
        with tempfile.TemporaryDirectory(prefix='normal-spec-import-') as tmp:
            root=Path(tmp)
            for row in rows.values():
                p=root/row['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(row['text'])
            self.assertEqual(rows,validate_ordinary_spec_files(repo_root=root))
            path=root/rows['A01']['path'];path.write_text(path.read_text().replace('ratio','USD'))
            with self.assertRaisesRegex(ValueError,'INSTALLED_SPEC_BYTES_CHANGED:A01'):
                validate_ordinary_spec_files(repo_root=root)

    def test_source_graph_includes_b03_dependency_but_not_unrequested_events(self):
        with original_sources_only():
            b03=prepare_ordinary_zero_ai_run_input(repo_root=ROOT,company_id='marriott_international',metric_id='B03')
            event=prepare_ordinary_zero_ai_run_input(repo_root=ROOT,company_id='marriott_international',metric_id='E03')
        self.assertEqual(['B01','B03'],b03['required_metric_ids'])
        self.assertEqual(['B03'],b03['requested_metric_ids'])
        self.assertEqual({'B01','B03'},set(b03['results']))
        self.assertEqual('26186000000',b03['results']['B01']['value'])
        self.assertEqual('B03',b03['primary_result']['metric_id'])
        self.assertEqual(['E03'],event['required_metric_ids'])
        self.assertEqual({'E03'},set(event['results']))
        self.assertEqual('NOT_CREATED',event['native_run_status'])

    def test_numeric_catalog_and_instant_run_target_retain_the_source_year(self):
        with original_sources_only():
            annual=prepare_ordinary_zero_ai_run_input(repo_root=ROOT,company_id='salesforce',metric_id='B02')
            instant=prepare_ordinary_zero_ai_run_input(repo_root=ROOT,company_id='salesforce',metric_id='B12')
        self.assertEqual(2026,annual['target_period']['fiscal_year'])
        self.assertEqual('2025-02-01',annual['target_period']['period_start'])
        self.assertEqual({'fiscal_year':2026,'period_start':'2026-01-31','period_end':'2026-01-31'},instant['target_period'])
        self.assertEqual('72400000000',instant['primary_result']['value'])
        self.assertEqual({'B12'},set(instant['compiled_specs']))

    def test_blocked_b03_has_real_withheld_dependency_instead_of_an_incomplete_graph(self):
        with original_sources_only():
            value=prepare_ordinary_zero_ai_run_input(repo_root=ROOT,company_id='paramount_skydance_paramount_global',metric_id='B03')
        self.assertEqual({'B01','B03'},set(value['results']))
        self.assertTrue(all(r['publication']=='WITHHELD' and r['value'] is None for r in value['results'].values()))
        self.assertEqual('NOT_CREATED',value['native_run_status'])


if __name__=='__main__':unittest.main()
