"""A real B01 source-only package uses installed program rules, never answers."""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.ordinary_saved_result import create_saved_result, read_saved_result
from vnext.normal_zero_ai_results import NormalZeroAiError
from vnext.normal_governance_input import _Sources, _filings


class SeparateRuleRootTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.source=cls.root/'source';cls.source.mkdir()
        selected=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id='marriott_international')
        paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for proof in selected['source_proofs']:
            paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
        for relative in paths:
            target=cls.source/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(REPO_ROOT/relative,target)
        cls.record=create_saved_result(source_root=cls.source,output_root=cls.root/'result',
                                      company_id='marriott_international',metric_id='B01')
        inventory=json.loads((REPO_ROOT/'evidence/submissions/CIK0001048286.json').read_text())
        prior=next(r for r in _filings(inventory,inventory_name='CIK0001048286.json')
                   if r['form']=='10-K' and r['reportDate']=='2024-12-31')
        reader=_Sources(REPO_ROOT,'marriott_international','1048286');reader.primary(prior)
        for item in reader.proofs.values():
            for key in ('request_repo_relative_path','request_headers_repo_relative_path'):
                relative=item['proof'][key];target=cls.source/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(REPO_ROOT/relative,target)
        cls.growth=create_saved_result(source_root=cls.source,output_root=cls.root/'growth',
                                      company_id='marriott_international',metric_id='B02')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_no_catalog_rules_code_or_answers_required_in_source_root(self):
        self.assertFalse((self.source/'catalog').exists())
        self.assertEqual({p.name for p in (self.source/'config').iterdir()},{'company_registry.csv'})
        self.assertFalse((self.source/'scripts').exists())
        self.assertEqual(self.record['result']['value'],'26186000000')
        self.assertEqual(self.record['manifest']['rules_root'],str(REPO_ROOT))
        self.assertEqual(self.record['manifest']['source_root'],str(self.source))

    def test_saved_result_read_retains_value_unit_period_and_source_rows(self):
        actual=read_saved_result(output_root=self.root/'result')
        self.assertEqual(actual['result']['unit'],'USD')
        self.assertEqual((actual['result']['period_start'],actual['result']['period_end']),('2025-01-01','2025-12-31'))
        import io
        rows=list(csv.DictReader(io.StringIO(actual['files']['metric_evidence.csv'].decode())))
        self.assertTrue(rows);self.assertTrue(all(r['source_url'].startswith('https://') for r in rows))

    def test_b02_uses_actual_comparative_original_without_calculation_rules_in_source(self):
        self.assertEqual(self.growth['result']['value'],'0.04326693227091633466135458167')
        self.assertEqual(self.growth['result']['unit'],'ratio')
        self.assertEqual(self.growth['manifest']['rules_root'],str(REPO_ROOT))
        self.assertFalse((self.source/'catalog').exists())
        self.assertEqual({p.name for p in (self.source/'config').iterdir()},{'company_registry.csv'})

    def test_registry_subject_change_is_not_hidden_by_program_rules(self):
        path=self.source/'config/company_registry.csv';original=path.read_bytes()
        text=original.decode();text=text.replace('1048286','19617')
        path.write_text(text)
        try:
            with self.assertRaisesRegex(NormalZeroAiError,'SOURCE_SUBJECT_REGISTRY_CHANGED'):
                create_saved_result(source_root=self.source,output_root=self.root/'wrong',
                                    company_id='marriott_international',metric_id='B01')
            self.assertFalse((self.root/'wrong/manifest.json').exists())
        finally:path.write_bytes(original)


if __name__=='__main__':unittest.main()
