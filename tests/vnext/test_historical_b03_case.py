"""Small constructed source-selection controls, without EBITDA acceptance."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from vnext import historical_b03_case as cases


class HistoricalB03SourcesTest(TestCase):
    def test_actual_precision_and_table_helpers_are_declared(self):
        from tests.vnext.test_ordinary_depreciation_sources import DepreciationSourcesTest
        from tests.vnext.test_b03_current_input_scope import ContractAggregateTest
        from tests.vnext.processing_dependency_checks import processing_calls
        from vnext.ordinary_depreciation_sources import inspect_depreciation_sources
        root=Path(__file__).resolve().parents[2]
        with processing_calls(root) as observed:
            result=inspect_depreciation_sources(**DepreciationSourcesTest().packet())
            contract=ContractAggregateTest()
            self.assertIsNotNone(contract.check(contract.material()))
        self.assertFalse(result['definition_complete'])
        self.assertFalse(result['metric_result_created'])
        for name in ('r5_b06_scope','b06_disclosure','r5_b06_structured'):
            path='scripts/vnext/'+name+'.py'
            self.assertIn(path,observed)
            self.assertIn(path,cases.PROCESSING_FILES)

    def setUp(self):
        self.annual = {'company_id': 'constructed', 'entity': '12345',
            'filing': {'accessionNumber': 'old-selected', 'form': '10-K'},
            'table_input': {'target_period': {'fiscal_year': 2024,
                'period_start': '2024-01-01', 'period_end': '2024-12-31'}},
            'subject_policy': {'mode': 'CONTINUOUS_PRIMARY'}, 'amendments': [],
            'source_proofs': [{'constructed_annual_proof': True}]}
        self.primary = {'raw_blob': {'media_type': 'text/html'}, 'source': 'constructed-primary'}
        self.xml = {'raw_blob': {'media_type': 'application/xml'}, 'source': 'constructed-xml'}
        self.originals = [self.primary, self.xml]
        self.filings = []
        self.reads = []
        self.target_inventory = None
        self.inventory_lookups = []

        def read(url, **kwargs):
            self.reads.append((url, kwargs))
            return {'constructed_url': url}

        def auditor(filing):
            self.filings.append(filing)
            return self.originals

        self.reader = SimpleNamespace(read=read, auditor_filing=auditor,
            proofs={'source': {'proof': {'constructed_original_proof': True}}},
            records={}, file_sets=[{'constructed_complete_original_set': True}])

    def lookup_inventory(self, **kwargs):
        self.inventory_lookups.append(kwargs)
        if self.target_inventory is not None:
            self.reader.proofs['history'] = {'proof': {'constructed_history_proof': True}}
            self.reader.records['history'] = {'record_type': 'SOURCE_REFERENCE', 'constructed_history': True}
            return self.target_inventory
        return kwargs['inventory']

    def prepare(self):
        with patch.object(cases, 'resolve_period_selection', return_value={'selected': 'constructed'}) as select, \
             patch.object(cases, 'prepare_historical_annual_input', return_value=self.annual) as annual, \
             patch.object(cases, '_Sources', return_value=self.reader), \
             patch.object(cases, 'filing_inventory', side_effect=self.lookup_inventory), \
             patch.object(cases, 'verify_ordinary_source_proofs', return_value={'checked': True}) as admit:
            value = cases.prepare_selected_income_sources(repo_root=Path('/saved'),
                company_id='constructed', fiscal_year=2024)
        return value, select, annual, admit

    def test_requested_year_reaches_same_source_readers_and_complete_proofs(self):
        result, select, annual, admit = self.prepare()
        select.assert_called_once_with(repo_root=Path('/saved').resolve(), company_id='constructed',
            fiscal_year=2024, rules_root=cases.ROOT)
        self.assertEqual([self.annual['filing']], self.filings)
        self.assertIs(result['preparation']['primary'], self.primary)
        self.assertIs(result['preparation']['xml'], self.xml)
        self.assertIs(result['preparation']['input_binding']['source_sets'], self.reader.file_sets)
        self.assertEqual(2, len(result['source_proofs']))
        admit.assert_called_once_with(data_root=Path('/saved').resolve(), proofs=result['source_proofs'])
        self.assertNotIn('results', result)
        self.assertNotIn('filing_inventory_source', result['preparation'])

    def test_older_filing_uses_loaded_history_inventory_and_keeps_main_identity(self):
        self.target_inventory = {'source': 'constructed-history-block'}
        result, *_ = self.prepare()
        self.assertIs(self.target_inventory, result['preparation']['filing_inventory_source'])
        self.assertEqual('https://data.sec.gov/submissions/CIK0000012345.json',
                         result['preparation']['inventory']['constructed_url'])
        lookup = self.inventory_lookups[0]
        self.assertEqual('old-selected', lookup['accession'])
        self.assertEqual('12345', lookup['cik'])
        self.assertEqual({'selected': 'constructed'}, lookup['period_selection'])
        self.assertIs(self.reader, lookup['reader'])
        self.assertIn({'constructed_history_proof': True}, result['source_proofs'])
        self.assertIn({'record_type': 'SOURCE_REFERENCE', 'constructed_history': True},
                      result['preparation']['records'])

    def test_literal_and_resolved_labels_are_distinct_but_dates_must_match(self):
        self.annual['original_input'] = deepcopy(self.annual)
        self.annual['original_input']['table_input']['target_period']['fiscal_year'] = 2023
        result, *_ = self.prepare()
        self.assertEqual(2023, result['original_annual']['table_input']['target_period']['fiscal_year'])
        self.assertEqual(2024, result['annual']['table_input']['target_period']['fiscal_year'])
        self.annual['original_input']['table_input']['target_period']['period_start'] = '2024-02-01'
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_PERIOD_CHANGED'):
            self.prepare()

    def test_wrong_requested_label_refuses_before_original_reads(self):
        self.annual['table_input']['target_period']['fiscal_year'] = 2025
        with self.assertRaisesRegex(ValueError, 'REQUESTED_YEAR_CHANGED'):
            self.prepare()
        self.assertEqual([], self.filings)

    def test_unreceived_successor_remains_an_implementation_gap(self):
        self.annual['subject_policy']['mode'] = 'SUCCESSOR_REGISTRANT_ONLY'
        with self.assertRaises(cases.HistoricalIncomeSourceError) as caught:
            self.prepare()
        self.assertEqual('IMPLEMENTATION_GAP',caught.exception.category)
        self.assertEqual([],self.filings)

    def test_link_amendment_uses_the_received_statement_check_and_carries_its_record(self):
        self.annual['amendments'] = [{'form':'10-K/A'}]
        checked={'classification':'EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15',
                 'scope_id':'constructed-proved-link-only'}
        with patch.object(cases,'_statement_amendment_checks',return_value=[checked]) as inspect:
            result,*_=self.prepare()
        inspect.assert_called_once_with(self.reader,self.annual,
            metric_id='B03',income_properties=[])
        self.assertEqual([checked],result['statement_amendment_checks'])
        self.assertEqual([checked],result['preparation']['input_binding']['statement_amendment_checks'])
        self.assertNotIn('statement_income_amendment_properties',result)
        self.assertNotIn('statement_income_amendment_properties',result['preparation']['input_binding'])

    def test_income_property_is_carried_separately_from_the_original_source_scope(self):
        self.annual['amendments'] = [{'form':'10-K/A'}]
        original={'classification':'PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',
                  'scope_id':'constructed-part3-source'}
        property_check={'source_scope_id':original['scope_id'],'metric_id':'B03',
            'income_property':{'input_class':'CURRENT_ORIGINAL_INCOME_STATEMENT_VALUES'}}
        def checked(reader,annual,*,metric_id,income_properties):
            self.assertEqual('B03',metric_id)
            income_properties.append(property_check)
            return [original]
        with patch.object(cases,'_statement_amendment_checks',side_effect=checked):
            result,*_=self.prepare()
        self.assertEqual([original],result['statement_amendment_checks'])
        self.assertEqual([property_check],result['statement_income_amendment_properties'])
        self.assertEqual([property_check],result['preparation']['input_binding']['statement_income_amendment_properties'])

    def test_uncleared_amendment_refuses_before_companyfacts_calculation(self):
        from vnext.historical_statement_cases import StatementCaseError
        self.annual['amendments']=[{'form':'10-K/A'}]
        with patch.object(cases,'_statement_amendment_checks',
                side_effect=StatementCaseError('HISTORICAL_STATEMENT_AMENDMENT_ORIGINAL_VALUES_NOT_PROVEN',
                    'AMENDMENT_INPUT_NOT_CLEARED')):
            with self.assertRaises(StatementCaseError) as caught:
                self.prepare()
        self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED',caught.exception.category)
        self.assertEqual([],self.filings)

    def test_missing_or_duplicate_media_cannot_become_a_selected_original(self):
        for originals in ([self.primary], [self.primary, self.primary, self.xml]):
            self.originals = originals
            with self.subTest(originals=len(originals)), self.assertRaisesRegex(ValueError, 'MEDIA_SET_AMBIGUOUS'):
                self.prepare()


class HistoricalB03ConsumerGuardTest(TestCase):
    def test_wrong_metric_refuses_before_any_source_read(self):
        with patch.object(cases,'prepare_selected_income_sources') as prepare:
            with self.assertRaisesRegex(ValueError,'FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_income_year_case(repo_root='/saved',
                    company_id='constructed',metric_id='B01',fiscal_year=2024)
        prepare.assert_not_called()

    def test_processing_closure_contains_shared_business_and_request_identity(self):
        self.assertEqual(len(cases.PROCESSING_FILES),len(set(cases.PROCESSING_FILES)))
        for path in ('scripts/vnext/selected_income_calculation.py',
                     'scripts/vnext/ordinary_b03_input_scope.py',
                     'scripts/vnext/b03_contract_amortization_scope.py',
                     'scripts/vnext/ordinary_income_input.py',
                     'scripts/vnext/historical_filing_inventory.py',
                     'scripts/sec_http.py'):
            self.assertIn(path,cases.PROCESSING_FILES)
