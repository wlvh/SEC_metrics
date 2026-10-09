"""Reported scope controls. Constructed inputs are not business results."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from vnext.canonical import sha256_bytes
from vnext.selected_revenue_scope_v1 import selected_revenue_scope, admit_revenue_facts, verify_revenue_observations
from tests.vnext.test_selected_income_source_v1 import fixture

APPROVED = ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', 'us-gaap:Revenues']


def originals(*, total='58496', product='50914', alliance='7582', year='2025', full=True):
    source, annual = fixture()
    def row(label, concept, value):
        return f'<tr><td>{label}</td><td><ix:nonFraction name="us-gaap:{concept}" contextRef="annual" unitRef="usd" scale="6" decimals="-6">{value}</ix:nonFraction></td></tr>'
    table = '<table><tr><td>Year Ended December 31,</td><td></td></tr><tr><td>(MILLIONS, EXCEPT PER SHARE DATA)</td><td>'+year+'</td></tr>'
    table += row('Product revenues', APPROVED[0].split(':')[1],product)
    table += row('Alliance revenues','RevenueFromCollaborativeArrangementExcludingRevenueFromContractWithCustomer',alliance)
    table += row('Total revenues', 'Revenues',total)
    if full:
        table += row('Cost of sales', 'CostOfGoodsAndServicesSold','10000')
        table += row('Net income', 'NetIncomeLoss','1000')
    table += '</table>'
    raw = source['raw_bytes'].replace(b'</xbrli:xbrl>',table.encode()+b'</xbrli:xbrl>')
    source = {**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
    return source,copy.deepcopy(source),annual


def facts(annual):
    result=[]
    for concept,value in zip(APPROVED, ['50914000000','58496000000']):
        result.append({'entity':annual['entity'], 'accession':annual['filing']['accessionNumber'],
            'concept':concept, 'value':value,'unit':'USD','period_start':'2025-01-01','period_end':'2025-12-31',
            'duration_days':365, 'filed':'2026-02-01','fiscal_period':'FY','form':'10-K',
            'fact_id':'fact:sha256:'+('1' if concept==APPROVED[0] else '2')*64,
            'source_binding':{'entity':annual['entity'],'accession':annual['filing']['accessionNumber'],
                'raw_asset_id':'sha256:'+'a'*64, 'source_reference_id':'sha256:'+'b'*64,
                'source_role':'companyfacts','document_name':'facts.json'}})
    return result


class SelectedRevenueScopeTest(unittest.TestCase):
    def scope(self, **kwargs):
        primary,xml,annual=originals(**kwargs)
        return selected_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_approved_legacy_calculator_selects_total_after_component_admission(self):
        from vnext.calculator import calculate_metric
        from vnext.specs import compile_spec_file
        from vnext.observations import scope_key
        _,_,annual=originals(); source_facts=facts(annual)
        spec=compile_spec_file(path=Path(__file__).resolve().parents[2]/'catalog/metrics/B01_revenue.md',dependency_specs={})
        scope={'entity_scope':'registrant','period_basis':'source_annual_duration'}
        target={'company_id':annual['company_id'],'entity':annual['entity'],'accession':annual['filing']['accessionNumber'],
                'period_start':'2025-01-01','period_end':'2025-12-31','scope':scope,'scope_key':scope_key(scope=scope)}
        traits=['non_financial']
        old=calculate_metric(compiled_spec=spec,target=target,company_traits=traits,structured_facts=source_facts,verified_observations=[])
        self.assertEqual(old[0]['value'],'50914000000')
        admitted=admit_revenue_facts(facts=source_facts,scope=self.scope())
        self.assertEqual(admitted,[source_facts[1]])
        new=calculate_metric(compiled_spec=spec,target=target,company_traits=traits,structured_facts=admitted,verified_observations=[])
        self.assertEqual(new[0]['value'],'58496000000')
        self.assertNotEqual(old[0]['result_id'],new[0]['result_id'])
        verify_revenue_observations(observations=new[2],scope=self.scope())
        with self.assertRaisesRegex(ValueError,'SELECTED_COMPONENT_NOT_TOTAL'):
            verify_revenue_observations(observations=old[2],scope=self.scope())
        self.assertEqual(source_facts,facts(annual))

    def test_source_bound_cells_year_and_primary_xml_retained(self):
        scope=self.scope();self.assertEqual(scope['status'],'REPORTED_COMPONENTS_AND_TOTAL')
        split=scope['splits'][0]
        self.assertEqual(split['total']['value'],'58496000000')
        self.assertEqual([r['value'] for r in split['parts']],['50914000000','7582000000'])
        self.assertEqual(split['xml_check'],'MATCH');self.assertEqual(len(split['xml_matches']),3)
        self.assertEqual(split['year_headers'][0]['text'],'2025')
        self.assertTrue(split['part_cells'][0]['raw_text'])

    def test_revenue_note_total_without_full_statement_not_treated_as_company_total(self):
        scope=self.scope(full=False);self.assertFalse(scope['complete_scope_proven'])
        _,_,annual=originals();self.assertEqual(admit_revenue_facts(facts=facts(annual),scope=scope),facts(annual))

    def test_missing_revenue_component_is_not_an_empty_success(self):
        primary,xml,annual=originals()
        import re
        for source in (primary,xml):
            source['raw_bytes']=re.sub(rb'<tr><td>Alliance revenues</td>.*?</tr>',b'',source['raw_bytes'])
            source['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=source['raw_bytes'])
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_REVENUE_BLOCK'):
            selected_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_scope_cannot_borrow_later_filing_total_when_original_is_missing(self):
        _,_,annual=originals(); f=facts(annual);f[1]['accession']='later'
        with self.assertRaisesRegex(ValueError,'TOTAL_NOT_IN_COMPANYFACTS'):
            admit_revenue_facts(facts=f,scope=self.scope())

    def test_quarter_caption_does_not_accept_annual_native_context(self):
        primary,xml,annual=originals()
        primary['raw_bytes']=primary['raw_bytes'].replace(b'Year Ended December 31,',b'Three Months Ended December 31,')
        primary['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=primary['raw_bytes'])
        with self.assertRaisesRegex(ValueError,'VISIBLE_DURATION_UNRESOLVED'):
            selected_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_visible_scale_cannot_be_overruled_by_native_amounts(self):
        primary,xml,annual=originals()
        primary['raw_bytes']=primary['raw_bytes'].replace(b'MILLIONS, EXCEPT PER SHARE DATA',b'THOUSANDS, EXCEPT PER SHARE DATA')
        primary['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=primary['raw_bytes'])
        with self.assertRaisesRegex(ValueError,'VISIBLE_NATIVE_SCALE_CONFLICT'):
            selected_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_visible_column_year_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError,'VISIBLE_YEAR_UNRESOLVED'):self.scope(year='2024')

    def test_conflicting_part_total_not_fixed_by_larger_value(self):
        with self.assertRaisesRegex(ValueError,'COMPONENT_TOTAL_CONFLICT'):self.scope(total='60000')

    def test_same_total_value_must_exist_in_selected_companyfacts(self):
        _,_,annual=originals(); source_facts=facts(annual);source_facts[1]['value']='60000000000'
        with self.assertRaisesRegex(ValueError,'TOTAL_NOT_IN_COMPANYFACTS'):
            admit_revenue_facts(facts=source_facts,scope=self.scope())

    def test_primary_xml_conflict_rejected(self):
        primary,xml,annual=originals();xml['raw_bytes']=xml['raw_bytes'].replace(b'>58496<',b'>60000<')
        xml['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=xml['raw_bytes'])
        with self.assertRaisesRegex(ValueError,'PRIMARY_XML_COMPONENT_OR_TOTAL_DIFFERS'):
            selected_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_single_full_revenue_keeps_contract_label_and_no_false_complete_credit(self):
        source,annual=fixture();rows=facts(annual)[:1]
        scope=selected_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
        self.assertFalse(scope['complete_scope_proven']);self.assertEqual(admit_revenue_facts(facts=rows,scope=scope),rows)

    def test_primary_only_statement_check_is_explicit_not_faked_xml_check(self):
        primary,_,annual=originals()
        scope=selected_revenue_scope(primary=primary,annual=annual,approved_concepts=APPROVED)
        self.assertEqual(scope['splits'][0]['xml_check'],'NOT_SUPPLIED')

    def test_other_filing_facts_and_prior_periods_not_rewritten_or_substituted(self):
        _,_,annual=originals(); original=facts(annual);other=copy.deepcopy(original[0]);other['accession']='later'
        changed=copy.deepcopy(original[0]);changed.update(period_start='2024-01-01',period_end='2024-12-31')
        admitted=admit_revenue_facts(facts=[*original,other,changed],scope=self.scope())
        self.assertEqual(admitted,[original[1],changed])
        self.assertEqual(other['accession'],'later')

    def test_old_visible_header_parser_default_is_retained(self):
        from vnext.financial_structured import _InlineTableIndex,_fact_cells
        from vnext.financial_duration import _column_period
        from vnext.deterministic_router import parse_accession_xbrl_source
        source,_,annual=originals();raw=source['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw)
        index=_InlineTableIndex(raw);index.feed(raw.decode());index.close()
        rows=self.scope()['splits'][0]['total'];table,cell=_fact_cells(index,parsed,{rows['ordinal']})[rows['ordinal']]
        self.assertEqual(_column_period(table=table,selected=cell)[2],'COLUMN_PERIOD_NOT_PROVEN')

    def test_saved_producer_opts_in_for_b01_and_b03_but_not_neighbours(self):
        from vnext import ordinary_saved_result as saved
        # Test dispatch at the actual producer seam; no mocked business result
        # is registered or exported from this deliberately stopped preparation.
        for metric in ('B01','B03','B02'):
            with self.subTest(metric=metric),patch.object(saved,'prepare_ordinary_zero_ai_run_input',side_effect=ValueError('stop')) as prepare:
                with self.assertRaisesRegex(ValueError,'stop'):saved._ordinary_case(Path('/source'), 'test_company', metric)
                self.assertEqual(prepare.call_args.kwargs.get('validate_revenue_scope',False),metric in {'B01','B03'})

    def test_update_configuration_names_actual_scope_and_header_dependencies(self):
        from vnext.ordinary_current_update import _configuration
        root=Path(__file__).resolve().parents[2]
        for metric in ('B01','B03'):
            cfg=_configuration(root,'pfizer',metric)['processing_files']
            for name in ('selected_revenue_scope_v1','selected_income_source_v1','financial_duration'):
                self.assertIn('scripts/vnext/'+name+'.py',cfg)
