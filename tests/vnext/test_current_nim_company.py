"""Current NIM adapter controls and one real data-only source integration."""
import hashlib
import csv
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import financial_results as financial
from vnext import ordinary_current_update as update
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.ordinary_saved_result import create_saved_result,read_saved_result


class CurrentNIMContractTest(unittest.TestCase):
    def test_invalid_current_record_option_rejects_before_selection(self):
        with patch.object(financial,'_installed_rule',side_effect=AssertionError('No source selection')):
            for mode in (None,1,'yes'):
                with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'RECORD_MODE_INVALID'):
                    financial.resolve_ordinary_financial_metric(repo_root=REPO_ROOT,
                        company_id='jpmorgan_chase',metric_id='A04',ordinary_records=mode)

    def test_registry_subject_roles_and_industry_cannot_mix_with_installed_traits(self):
        with (REPO_ROOT/'config/company_registry.csv').open(newline='') as stream:
            reader=csv.DictReader(stream);fields=reader.fieldnames;original=list(reader)
        for changed in ({'primary_cik':'19617','roles':'primary:19617'},
                {'industry_profile':'financial'},{'related_ciks':'19617'},
                {'entity_continuity_status':'successor_predecessor'}):
            with self.subTest(change=changed),tempfile.TemporaryDirectory() as folder:
                source=Path(folder);path=source/'config/company_registry.csv';path.parent.mkdir()
                rows=[dict(r) for r in original];next(r for r in rows if r['company_id']=='macys').update(changed)
                with path.open('w',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
                with patch.object(financial,'_ordinary_sources',side_effect=AssertionError('No wrong-company source or N_A')):
                    with self.assertRaisesRegex(ValueError,'COMPANY_REGISTRATION_DIFFERS'):
                        financial.resolve_ordinary_financial_metric(repo_root=source,
                            company_id='macys',metric_id='A04',ordinary_records=True)

    def test_cosmetic_registration_name_does_not_require_identical_file_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder);path=source/'config/company_registry.csv';path.parent.mkdir()
            with (REPO_ROOT/'config/company_registry.csv').open(newline='') as stream:
                reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
            next(r for r in rows if r['company_id']=='macys')['display_name']='Macy’s display spelling'
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            financial._current_company_registration(data_root=source,company_id='macys')

    def test_current_source_and_interpretation_dependencies_are_tracked(self):
        before=update._configuration(REPO_ROOT,'jpmorgan_chase','A04');original=update.sha256_file
        for path in ('scripts/vnext/financial_results.py','scripts/vnext/financial_relationships.py',
                'scripts/vnext/normal_annual_input_v2.py','scripts/vnext/fiscal_year_labels.py',
                'config/normal_fiscal_year_labels_v1.json','catalog/r6/text_results_v2_policy.json',
                'catalog/r4_v2/A13_geographic_exposure.md'):
            with self.subTest(path=path),patch.object(update,'sha256_file',side_effect=lambda *,path,relative=path:
                    'changed-used-nim-rule' if path==REPO_ROOT/relative else original(path=path)):
                changed=update._configuration(REPO_ROOT,'jpmorgan_chase','A04')
                self.assertNotEqual(before,changed)


class CurrentNIMSourceIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.source=cls.root/'source';cls.source.mkdir()
        original=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id='jpmorgan_chase')
        paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for proof in original['source_proofs']:
            paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
        for relative in paths:
            target=cls.source/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(REPO_ROOT/relative,target)
        cls.result=create_saved_result(source_root=cls.source,output_root=cls.root/'result',
            company_id='jpmorgan_chase',metric_id='A04')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_source_only_input_and_full_native_result_are_saved(self):
        self.assertFalse((self.source/'catalog').exists());self.assertFalse((self.source/'scripts').exists())
        self.assertEqual({p.name for p in (self.source/'config').iterdir()},{'company_registry.csv'})
        self.assertEqual(self.result['result']['value'],'0.025')
        self.assertEqual(self.result['result']['unit'],'ratio')
        self.assertEqual((self.result['result']['period_start'],self.result['result']['period_end']),
            ('2025-01-01','2025-12-31'))
        self.assertEqual(self.result['manifest']['rules_root'],str(REPO_ROOT))

    def test_independent_record_read_never_recalculates(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.root/'result').iterdir() if p.is_file()}
        with patch.object(financial,'resolve_ordinary_financial_metric',side_effect=AssertionError('Read cannot calculate')):
            read=read_saved_result(output_root=self.root/'result')
        self.assertEqual(read['result'],self.result['result'])
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (self.root/'result').iterdir() if p.is_file()})

    def test_old_default_resolution_preserves_amount_unit_and_actual_period(self):
        old=financial.resolve_ordinary_financial_metric(repo_root=REPO_ROOT,
            company_id='jpmorgan_chase',metric_id='A04')
        self.assertNotIn('fiscal_year_label_resolution',old['prepared_input'])
        for field in ('value','unit','period_start','period_end','scope_key','publication'):
            self.assertEqual(old['result'][field],self.result['result'][field])

    def test_changed_body_cannot_use_unchanged_log_to_revive_success(self):
        state=self.root/'tamper-state'
        first=update.run_once(state_root=state,source_root=self.source,
            company_id='jpmorgan_chase',metric_id='A04')
        self.assertEqual(first['status'],'CANDIDATE_READY')
        pointer=state/'current-result.json';before=pointer.read_bytes()
        proof=self.result['manifest']['source_proofs'][1]
        primary=self.source/proof['request_repo_relative_path'];raw=primary.read_bytes()
        try:
            primary.write_bytes(raw+b'<!-- changed source body without a request record -->')
            with patch.object(financial,'resolve_ordinary_financial_metric',side_effect=AssertionError('Do not calculate invalid source')):
                failed=update.run_once(state_root=state,source_root=self.source,
                    company_id='jpmorgan_chase',metric_id='A04')
            self.assertEqual(failed['status'],'INPUT_OR_EXECUTION_FAILED')
            self.assertEqual(pointer.read_bytes(),before)
            self.assertEqual(read_saved_result(output_root=Path(first['result_root']))['result'],self.result['result'])
        finally:
            primary.write_bytes(raw)

class CurrentNIMNonfinancialIntegrationTest(unittest.TestCase):
    def test_real_nonfinancial_company_is_structural_not_fake_zero(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        source=root/'retail-source';source.mkdir()
        selected=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id='macys')
        paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for proof in selected['source_proofs']:
            paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
        for relative in paths:
            target=source/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(REPO_ROOT/relative,target)
        with patch.object(financial,'_fact',side_effect=AssertionError('No bank fact interpretation for retail')):
            saved=create_saved_result(source_root=source,output_root=root/'retail-result',
                company_id='macys',metric_id='A04')
        self.assertEqual(saved['result']['applicability'],'N_A_STRUCTURAL')
        self.assertIsNone(saved['result']['value'])
        self.assertNotEqual(saved['result'].get('reason_code'),'IMPLEMENTATION_GAP')


if __name__=='__main__':unittest.main()
