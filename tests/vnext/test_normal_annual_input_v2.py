"""Issuer-defined fiscal years do not rewrite the original machine labels."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tests.vnext.test_normal_companyfacts_results import copy_sources
from vnext.normal_annual_input import prepare_saved_annual_input as original_input, NormalAnnualInputError
from vnext.normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value, _choose_fiscal_year
from vnext.normal_accession_results import resolve_ordinary_accession_metrics
from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
from vnext.normal_zero_ai_results import resolve_ordinary_zero_ai_metric


class OrdinaryFiscalLabelTest(unittest.TestCase):
    def test_source_defined_year_preserves_raw_metadata_actual_dates_and_original_input(self):
        with original_sources_only():
            for company,year in [('salesforce',2026),('macys',2025),('marriott_international',2025)]:
                old=original_input(repo_root=ROOT,company_id=company)
                new=prepare_saved_annual_input(repo_root=ROOT,company_id=company)
                self.assertEqual(old,new['original_input'])
                period=new['table_input']['target_period']
                self.assertEqual(year,period['fiscal_year'])
                self.assertEqual({k:old['table_input']['target_period'][k] for k in ('period_start','period_end')},
                                 {k:period[k] for k in ('period_start','period_end')})
                self.assertEqual(old['source_proofs'],new['source_proofs'])
                self.assertFalse(new['production_authorized'])
                resolution=new['fiscal_year_label_resolution']
                self.assertEqual(2025,resolution['original_dei_fiscal_year'])
                self.assertEqual(company=='salesforce',resolution['metadata_conflict_retained'])

    def test_revenue_events_companyfacts_and_accession_use_the_same_new_label_without_changing_amounts(self):
        with original_sources_only():
            revenue=resolve_ordinary_zero_ai_metric(repo_root=ROOT,company_id='salesforce',metric_id='B01')
            events=resolve_ordinary_zero_ai_metric(repo_root=ROOT,company_id='salesforce',metric_id='C01')
            catalog=resolve_ordinary_companyfacts_metrics(repo_root=ROOT,company_id='salesforce')
            native=resolve_ordinary_accession_metrics(repo_root=ROOT,company_id='salesforce')
        self.assertEqual('41525000000',revenue['result']['value'])
        self.assertEqual('2025-02-01',revenue['result']['period_start'])
        self.assertEqual('WITHHELD',events['result']['publication'])
        self.assertEqual('SOURCE_ACCESS_FAILED',events['selection']['category'])
        self.assertEqual('72400000000',native['metrics']['B12']['result']['value'])
        for row in (revenue,events,catalog,native):
            self.assertEqual(2026,row['prepared_input']['table_input']['target_period']['fiscal_year'])
            self.assertEqual(2025,row['prepared_input']['fiscal_year_label_resolution']['original_dei_fiscal_year'])
        self.assertEqual(2026,native['metrics']['B12']['target']['scope']['fiscal_year'])
        self.assertEqual(2026,catalog['metrics']['B02']['target']['scope']['fiscal_year'])

    def test_imported_policy_is_not_a_caller_choice_of_year(self):
        with original_sources_only():
            row=resolve_ordinary_accession_metrics(repo_root=ROOT,company_id='salesforce')
        with tempfile.TemporaryDirectory(prefix='fiscal-source-input-') as tmp:
            root=Path(tmp);copy_sources(row,root)
            with original_sources_only():
                self.assertEqual(row['prepared_input'],prepare_saved_annual_input(repo_root=root,company_id='salesforce'))
            policy=root/'config/normal_fiscal_year_labels_v1.json'
            data=json.loads(policy.read_text());data['conflict_rule']='USE_CALLER_YEAR';policy.write_text(json.dumps(data))
            with original_sources_only(),self.assertRaisesRegex(NormalAnnualInputError,'INSTALLED_POLICY_CHANGED'):
                prepare_saved_annual_input(repo_root=root,company_id='salesforce')

    def test_unresolved_source_definition_cannot_be_forced_into_a_year(self):
        # This isolates the branch after source inspection; original-byte
        # quotation and foreign-subject negatives live in test_fiscal_year_labels.
        from vnext.fiscal_year_labels import inspect_saved_fiscal_year_label
        with original_sources_only():
            report=inspect_saved_fiscal_year_label(repo_root=ROOT,company_id='salesforce')
        report['inspection']['status']='EXPLICIT_DEFINITION_UNRESOLVED'
        report['inspection']['source_defined_fiscal_year']=None
        with self.assertRaisesRegex(NormalAnnualInputError,'FISCAL_LABEL_UNRESOLVED'):
            _choose_fiscal_year(report['inspection'])
        with self.assertRaises(TypeError):
            prepare_saved_annual_input(repo_root=ROOT,company_id='salesforce',fiscal_year=2025)

    def test_exact_json_shape_retains_source_characters(self):
        source={'text':'Original ; é','tuple':(';',)}
        result=exact_json_value(source)
        self.assertEqual(source['text'],result['text'])
        self.assertEqual([';'],result['tuple'])

    def test_process_local_interpretation_never_reuses_changed_sources_or_mutable_return_values(self):
        from vnext import normal_annual_input_v2 as entry
        from vnext import fiscal_year_labels as inspector
        from vnext.batch_workflow import BatchWorkflowError
        entry._INSPECTIONS.clear()
        with original_sources_only(),patch.object(inspector,'_inspect_prepared_input',wraps=inspector._inspect_prepared_input) as calls:
            first=prepare_saved_annual_input(repo_root=ROOT,company_id='salesforce')
            first['fiscal_year_label_resolution']['source_inspection']['source_defined_fiscal_year']=9999
            second=prepare_saved_annual_input(repo_root=ROOT,company_id='salesforce')
            self.assertEqual(1,calls.call_count)
            self.assertEqual(2026,second['fiscal_year_label_resolution']['source_inspection']['source_defined_fiscal_year'])
            row=resolve_ordinary_accession_metrics(repo_root=ROOT,company_id='salesforce')
            with tempfile.TemporaryDirectory(prefix='fiscal-cache-source-') as tmp:
                root=Path(tmp);copy_sources(row,root)
                self.assertEqual(second,prepare_saved_annual_input(repo_root=root,company_id='salesforce'))
                self.assertEqual(1,calls.call_count)
                path=root/row['prepared_input']['table_input']['source_repo_relative_path']
                path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaisesRegex(BatchWorkflowError,'Request-ledger locator evidence is invalid'):
                    prepare_saved_annual_input(repo_root=root,company_id='salesforce')
                self.assertEqual(1,calls.call_count)


if __name__=='__main__':unittest.main()
