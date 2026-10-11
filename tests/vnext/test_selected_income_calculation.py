"""Small selected-source contracts; amounts are labelled constructed controls."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from vnext.selected_income_calculation import calculate_selected_income
from vnext.normal_run_specs import installed_ordinary_spec_documents


class SelectedIncomeCalculationContractTest(TestCase):
    def invoke(self, **options):
        spec = installed_ordinary_spec_documents()['B03']['compiled_spec']
        return calculate_selected_income(repo_root=Path('/constructed'),
            prepared={}, inventory={}, primary_source={}, facts_source={},
            metric_id='B03', spec=spec, dependency_specs={}, target={}, period={},
            traits={}, **options)

    def test_invalid_policy_refuses_before_reading_any_amount(self):
        with patch('vnext.selected_income_calculation.companyfacts_structured_facts') as parse:
            with self.assertRaisesRegex(ValueError,'SINGLE_REVENUE_OPTION_INVALID'):
                self.invoke(allow_single_revenue_line=True)
            with self.assertRaisesRegex(ValueError,'REVENUE_SCOPE_CONTRACT_INVALID'):
                self.invoke(revenue_scope_contract='unreviewed')
        parse.assert_not_called()

    def test_latest_filing_selection_is_not_owned_by_selected_calculation(self):
        # Explicitly selected wrappers own discovery. The common function
        # cannot silently choose latest if the caller omitted selected identity.
        with patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',
                   side_effect=AssertionError('Selected calculation must not discover')):
            with self.assertRaises(KeyError):
                self.invoke()

class SelectedIncomeCoordinateTest(TestCase):
    """Constructed identity controls; none are SEC originals or business values."""
    def setUp(self):
        from vnext.canonical import sha256_bytes
        from sec_urls import accession_document_url, companyfacts_url, submissions_url
        self.period={'fiscal_year':2024,'period_start':'2024-02-04','period_end':'2025-02-01'}
        self.annual={'company_id':'constructed','entity':'12345','filing':{
            'accessionNumber':'0000012345-25-000001','primaryDocument':'original.htm'},
            'table_input':{'target_period':dict(self.period)}}
        self.target={'company_id':'constructed','period_start':self.period['period_start'],
                     'period_end':self.period['period_end']}
        def source(kind,url):
            raw=('constructed-'+kind).encode()
            return {'raw_bytes':raw,'source_reference':{'company_id':'constructed',
                'accession':self.annual['filing']['accessionNumber'],'source_url':url,
                'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
        self.primary=source('primary',accession_document_url(cik=12345,
            accession=self.annual['filing']['accessionNumber'],document_name='original.htm'))
        self.cf=source('cf',companyfacts_url(cik=12345));self.inventory=source('inventory',submissions_url(cik=12345))
        self.xml=source('xml','constructed-xml')

    def invoke(self, **changes):
        from vnext.selected_income_calculation import selected_income_coordinate
        args=dict(prepared=self.annual,target=self.target,period=self.period,
            primary_source=self.primary,facts_source=self.cf,inventory=self.inventory,xml_source=self.xml)
        with patch('vnext.selected_income_calculation.companyfacts_structured_facts',
                   side_effect=AssertionError('Identity checks must precede amounts')):
            return selected_income_coordinate(**{**args,**changes})

    def test_actual_noncalendar_label_is_not_inferred_from_end_year(self):
        self.invoke()

    def test_wrong_target_company_dates_and_explicit_identity_refuse(self):
        for change,reason in (({'company_id':'other'},'COMPANY_CHANGED'),
                ({'period_start':'2024-02-05'},'TARGET_PERIOD_CHANGED'),
                ({'period_end':'2025-01-31'},'TARGET_PERIOD_CHANGED'),
                ({'entity':'54321'},'TARGET_IDENTITY_CHANGED'),
                ({'accession':'wrong-filing'},'TARGET_IDENTITY_CHANGED')):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError,reason):
                self.invoke(target={**self.target,**change})

    def test_other_selected_period_cannot_silently_override_the_annual(self):
        period={**self.period,'period_start':'2024-08-08'}
        with self.assertRaisesRegex(ValueError,'PERIOD_NOT_PROVEN'):
            self.invoke(period=period,target={**self.target,'period_start':period['period_start']})

    def test_existing_successor_input_can_supply_proved_short_statement_dates(self):
        from copy import deepcopy
        period={**self.period,'period_start':'2024-08-08'}
        packet={'company_id':'constructed','annual_input':deepcopy(self.annual),'statement_period':period}
        self.invoke(period=period,target={**self.target,'period_start':period['period_start']},
                    selected_income_input=packet)
        packet['annual_input']['entity']='other'
        with self.assertRaisesRegex(ValueError,'PERIOD_NOT_PROVEN'):
            self.invoke(period=period,target={**self.target,'period_start':period['period_start']},
                        selected_income_input=packet)

    def test_primary_cf_inventory_and_xml_identity_changes_refuse(self):
        from copy import deepcopy
        for key,original in (('primary_source',self.primary),('facts_source',self.cf),
                             ('inventory',self.inventory),('xml_source',self.xml)):
            for field,value in (('company_id','other'),('raw_asset_id','sha256:wrong')):
                altered=deepcopy(original);altered['source_reference'][field]=value
                with self.subTest(source=key,field=field),self.assertRaisesRegex(ValueError,'SOURCE_IDENTITY_CHANGED'):
                    self.invoke(**{key:altered})
        for key,original in (('primary_source',self.primary),('facts_source',self.cf),('xml_source',self.xml)):
            altered=deepcopy(original);altered['source_reference']['accession']='wrong'
            with self.subTest(source=key),self.assertRaisesRegex(ValueError,'SOURCE_IDENTITY_CHANGED'):
                self.invoke(**{key:altered})

    def history_inventory(self):
        from copy import deepcopy
        from sec_urls import submissions_file_url
        name = 'CIK0000012345-submissions-001.json'
        self.annual['period_selection'] = {'reporting_cik': '12345',
            'loaded_inventories': ['CIK0000012345.json', name]}
        source = deepcopy(self.inventory)
        source['source_reference']['source_url'] = submissions_file_url(file_name=name)
        return source

    def test_selected_history_inventory_checks_identity_before_reading_amounts(self):
        from copy import deepcopy
        source = self.history_inventory()
        self.invoke(filing_inventory_source=source)
        for field, value in (('company_id', 'other'), ('raw_asset_id', 'sha256:wrong'),
                             ('source_url', 'https://data.sec.gov/submissions/unselected.json')):
            altered = deepcopy(source)
            altered['source_reference'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'SOURCE_IDENTITY_CHANGED:filing_inventory'):
                self.invoke(filing_inventory_source=altered)
        self.annual['period_selection']['reporting_cik'] = '54321'
        with self.assertRaisesRegex(ValueError, 'FILING_INVENTORY_NOT_SELECTED'):
            self.invoke(filing_inventory_source=source)

    def test_exact_filing_manifest_uses_selected_history_block_or_original_default(self):
        from vnext import selected_income_calculation as common
        source = self.history_inventory()
        spec = installed_ordinary_spec_documents()['B03']['compiled_spec']
        for selected in (None, source):
            with self.subTest(history=selected is not None), \
                 patch.object(common, '_exact_filing_source_set', return_value={'constructed_manifest': True}) as manifest, \
                 patch.object(common, 'companyfacts_structured_facts', return_value=[]), \
                 patch.object(common, 'adapt_companyfacts', return_value=[]), \
                 patch.object(common, 'calculate_metric', return_value=({'publication': 'WITHHELD',
                     'value': None, 'reason_code': 'CONSTRUCTED_CONTROL'}, {}, [])):
                common.calculate_selected_income(repo_root=Path('/constructed'), prepared=self.annual,
                    inventory=self.inventory, primary_source=self.primary, facts_source=self.cf,
                    metric_id='B03', spec=spec, dependency_specs={}, target=self.target,
                    period=self.period, traits={}, filing_inventory_source=selected)
            expected = self.inventory if selected is None else source
            self.assertIs(expected['source_reference'], manifest.call_args.kwargs['inventory_reference'])
            self.assertEqual(expected['raw_bytes'], manifest.call_args.kwargs['inventory_bytes'])
