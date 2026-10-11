"""Current opt-in and source-proof controls; constructed rows carry no business credit."""
import inspect
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from vnext.normal_zero_ai_results import _revenue_admission, resolve_ordinary_zero_ai_metric
from vnext.normal_run_inputs import prepare_ordinary_zero_ai_run_input
from vnext.selected_revenue_scope_v1 import selected_revenue_scope
from vnext.canonical import sha256_bytes
from tests.vnext.test_selected_revenue_scope_v1 import originals, facts, APPROVED


class CurrentReportedRevenueTest(unittest.TestCase):
    def test_explicit_total_uses_v2_admission_and_matching_observation_check(self):
        source, _, annual = originals()
        scope, admit, verify = _revenue_admission(primary=source, annual=annual,
            approved_concepts=APPROVED, contract='reported-total-v2')
        self.assertEqual(scope['method'], 'SELECTED_REPORTED_CONSOLIDATED_REVENUE_V2')
        self.assertEqual([f['value'] for f in admit(facts=facts(annual), scope=scope)], ['58496000000'])
        selected = scope['reported_totals'][0]['total']
        good = {'semantic_role':'revenue','value':selected['value'],'unit':selected['unit'],
                'period_start':selected['period_start'],'period_end':selected['period_end'],
                'source_binding':{'concept':selected['concept'],'entity':annual['entity'],
                                  'accession':annual['filing']['accessionNumber']}}
        verify(observations=[good], scope=scope)
        with self.assertRaises(ValueError):
            verify(observations=[{**good, 'value':'50914000000'}], scope=scope)

    def test_absent_direct_total_reuses_existing_component_path_without_new_credit(self):
        source, _, annual = originals()
        source['raw_bytes'] = source['raw_bytes'].replace(b'Total revenues', b'Revenues')
        source['source_reference']['raw_asset_id'] = 'sha256:'+sha256_bytes(content=source['raw_bytes'])
        expected = selected_revenue_scope(primary=source, annual=annual, approved_concepts=APPROVED)
        scope, _, _ = _revenue_admission(primary=source, annual=annual,
            approved_concepts=APPROVED, contract='reported-total-v2')
        self.assertEqual(scope, expected)

    def test_v2_period_error_cannot_fall_back_to_a_component(self):
        source, _, annual = originals()
        source['raw_bytes'] = source['raw_bytes'].replace(b'Year Ended December 31,', b'Year Ended December 30,')
        source['source_reference']['raw_asset_id'] = 'sha256:'+sha256_bytes(content=source['raw_bytes'])
        with patch('vnext.selected_revenue_scope_v1.selected_revenue_scope',
                   side_effect=AssertionError('No fallback after a source error')):
            with self.assertRaisesRegex(ValueError, 'VISIBLE_END_DAY_CONFLICT'):
                _revenue_admission(primary=source, annual=annual, approved_concepts=APPROVED,
                                   contract='reported-total-v2')

    def test_shared_default_still_returns_exact_v1_proof(self):
        source, _, annual = originals()
        expected = selected_revenue_scope(primary=source, annual=annual, approved_concepts=APPROVED)
        actual, _, _ = _revenue_admission(primary=source, annual=annual, approved_concepts=APPROVED)
        self.assertEqual(actual, expected)
        for entry in (resolve_ordinary_zero_ai_metric, prepare_ordinary_zero_ai_run_input):
            self.assertEqual(inspect.signature(entry).parameters['revenue_scope_contract'].default, 'components-v1')

    def test_public_preparer_forwards_only_explicit_opt_in(self):
        from vnext import normal_run_inputs as inputs
        for metric in ('B01', 'B03'):
            for options in ({}, {'validate_revenue_scope':True, 'revenue_scope_contract':'reported-total-v2'}):
                with self.subTest(metric=metric, options=options), patch.object(inputs,
                     'resolve_ordinary_zero_ai_metric', side_effect=ValueError('stop before output')) as resolver:
                    with self.assertRaisesRegex(ValueError, 'stop before output'):
                        inputs.prepare_ordinary_zero_ai_run_input(repo_root=Path(__file__).resolve().parents[2],
                            company_id='pfizer', metric_id=metric, **options)
                    self.assertEqual(resolver.call_args.kwargs.get('revenue_scope_contract'),
                                     options.get('revenue_scope_contract'))

    def test_current_company_opts_in_b01_b02_b03_but_shared_defaults_do_not(self):
        from vnext import ordinary_saved_result as saved
        from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
        for entry in (resolve_ordinary_zero_ai_metric, prepare_ordinary_zero_ai_run_input,
                      resolve_ordinary_companyfacts_metrics):
            self.assertFalse(inspect.signature(entry).parameters['allow_single_revenue_line'].default)
        for metric in ('B01','B02','B03','B04'):
            with self.subTest(metric=metric), patch.object(saved,'prepare_ordinary_zero_ai_run_input',
                 side_effect=ValueError('stopped at actual preparation boundary')) as prepare:
                with self.assertRaisesRegex(ValueError,'actual preparation boundary'):
                    saved._ordinary_case(Path('/source'), 'lumen_technologies', metric)
                self.assertEqual(prepare.call_args.kwargs.get('allow_single_revenue_line',False),
                                 metric in {'B01','B02','B03'})

    def test_b02_public_preparation_passes_scope_option_only_when_enabled(self):
        from vnext import normal_run_inputs as inputs
        root=Path(__file__).resolve().parents[2]
        for options in ({}, {'validate_revenue_scope':True,'revenue_scope_contract':'reported-total-v2',
                             'allow_single_revenue_line':True}):
            with self.subTest(options=options), patch.object(inputs,'resolve_ordinary_companyfacts_metrics',
                 side_effect=ValueError('stop at source resolver')) as resolver:
                with self.assertRaisesRegex(ValueError,'stop at source resolver'):
                    inputs.prepare_ordinary_zero_ai_run_input(repo_root=root,company_id='pfizer',metric_id='B02',**options)
                self.assertEqual(resolver.call_args.kwargs.get('validate_revenue_scope'),options.get('validate_revenue_scope'))
                self.assertEqual(resolver.call_args.kwargs.get('allow_single_revenue_line'),options.get('allow_single_revenue_line'))

    def test_original_claim_admission_retains_ids_and_excludes_subtotal(self):
        from vnext.normal_companyfacts_results import _original_revenue_claims
        source,_,annual=originals()
        class Reader:
            def primary(self,filing,**kwargs):return source
            def read(self,*args,**kwargs):return {'raw_bytes':b'{}'}
        original=facts(annual)
        claims=[{'claim_kind':'COMPANYFACTS_NUMERIC_FACT','locator':{'concept':f['concept'].split(':')[1],
                 'period_start':f['period_start'],'period_end':f['period_end']},
                 'attributes':{k:f[k] for k in ('entity','accession','period_start','period_end')},
                 'value':f['value'],'unit':f['unit'],'verified_claim_id':'claim-'+str(i)}
                for i,f in enumerate(original)]
        # Label inspection has its own real-source tests; this small control
        # isolates claim filtering, not source authenticity or company credit.
        inspected={'status':'METADATA_LABEL_ONLY','source_defined_fiscal_year':None,
                   'invalid_companyfacts_fy_rows':[],'dei_fiscal_year':2023}
        real_scope,admit,_=_revenue_admission(primary=source,annual=annual,
            approved_concepts=APPROVED,contract='reported-total-v2')
        with patch('vnext.fiscal_year_labels.inspect_fiscal_year_labels',return_value=inspected), \
             patch('vnext.normal_zero_ai_results._revenue_admission',return_value=(real_scope,admit,None)):
            kept,scope=_original_revenue_claims(reader=Reader(),prepared=annual,filing=annual['filing'],
                period=annual['table_input']['target_period'],claims=claims,concepts=APPROVED,
                allow_single_revenue_line=True)
        self.assertEqual(kept,[claims[1]])
        self.assertIs(kept[0],claims[1])
        self.assertEqual(scope,real_scope)

    def test_single_line_cannot_be_enabled_without_explicit_scope_contract(self):
        from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
        root=Path(__file__).resolve().parents[2]
        for entry,kwargs in ((resolve_ordinary_zero_ai_metric,{'metric_id':'B01'}),
                             (prepare_ordinary_zero_ai_run_input,{'metric_id':'B02'}),
                             (resolve_ordinary_companyfacts_metrics,{})):
            with self.subTest(entry=entry.__name__), self.assertRaisesRegex(ValueError,'REVENUE_OPTION_INVALID'):
                entry(repo_root=root,company_id='pfizer',allow_single_revenue_line=True,**kwargs)

    def test_paired_original_period_mismatch_cannot_reach_revenue_admission(self):
        from vnext.normal_companyfacts_results import _original_revenue_claims
        source,_,annual=originals()
        class Reader:
            def primary(self,filing):return source
            def read(self,*args,**kwargs):return {'raw_bytes':b'{}'}
        with patch('vnext.normal_zero_ai_results._revenue_admission',side_effect=AssertionError('No admission')):
            with self.assertRaisesRegex(ValueError,'REVENUE_ORIGINAL_FACTS_MISSING'):
                _original_revenue_claims(reader=Reader(),prepared=annual,filing=annual['filing'],
                    period={**annual['table_input']['target_period'],'period_start':'2022-01-01'},
                    claims=[],concepts=APPROVED,allow_single_revenue_line=True)

    def test_noncompeting_original_amounts_do_not_require_extra_prior_html(self):
        from vnext.normal_companyfacts_results import _original_revenue_claims
        class Reader:
            def primary(self,*args,**kwargs):raise AssertionError('No extra required source')
        period={'period_start':'2024-01-01','period_end':'2024-12-31'}
        claims=[{'locator':{'concept':c,**period},'attributes':{'accession':'prior'},
                 'unit':'USD','value':v} for c,v in (('Revenues','12.00'),('SalesRevenueNet','12'))]
        kept,scope=_original_revenue_claims(reader=Reader(),prepared={},filing={'accessionNumber':'prior'},
            period=period,claims=claims,concepts=['Revenues','SalesRevenueNet'],allow_single_revenue_line=True)
        self.assertIs(kept,claims)
        self.assertFalse(scope['complete_scope_proven'])
        self.assertEqual(scope['status'],'NO_COMPETING_REVENUE_AMOUNTS')

    def comparative_inputs(self, *, wrong_row=False, wrong_header=False, original_value='49000000000',
                           wrong_scale=False, wrong_current_fact=False):
        import re,copy
        source,_,annual=originals()
        raw=source['raw_bytes']
        context=re.search(rb'<xbrli:context id="annual">.*?</xbrli:context>',raw,re.S)[0]
        prior=context.replace(b'id="annual"',b'id="prior"').replace(b'2025-',b'2024-')
        raw=raw.replace(b'<xbrli:unit id="usd">',prior+b'<xbrli:unit id="usd">')
        raw=raw.replace(b'<td>2025</td>',b'<td>2025</td><td>'+ (b'2023' if wrong_header else b'2024')+b'</td>')
        comparative=b'<td><ix:nonFraction name="us-gaap:Revenues" contextRef="prior" unitRef="usd" scale="6" decimals="-6">50000</ix:nonFraction></td>'
        if wrong_scale:comparative=comparative.replace(b'scale="6"',b'scale="3"')
        needle=b'>58496</ix:nonFraction></td></tr>'
        if wrong_row:
            raw=raw.replace(b'>1000</ix:nonFraction></td></tr>',b'>1000</ix:nonFraction></td>'+comparative+b'</tr>')
        else:raw=raw.replace(needle,b'>58496</ix:nonFraction></td>'+comparative+b'</tr>')
        source={**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
        scope,_,_=_revenue_admission(primary=source,annual=annual,approved_concepts=APPROVED,contract='reported-total-v2')
        from tests.vnext.test_selected_income_source_v1 import fixture
        xml,prior_annual=fixture();xml=copy.deepcopy(xml);xml['raw_bytes']=xml['raw_bytes'].replace(b'2025',b'2024').replace(b'>12000000<',('>'+original_value+'<').encode())
        filing={'accessionNumber':'0000000123-25-000001','form':'10-K','reportDate':'2024-12-31'}
        xml['source_reference']={**xml['source_reference'],'accession':filing['accessionNumber'],'raw_asset_id':'sha256:'+sha256_bytes(content=xml['raw_bytes'])}
        xml['raw_blob']={'media_type':'application/xml'}
        class Reader:
            def primary(self,*args,**kwargs):return source
            def auditor_filing(self,*args):return [xml]
        period={'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}
        claims=[{'verified_claim_id':'original-'+c,'locator':{'concept':c,'period_start':period['period_start'],'period_end':period['period_end']},
                 'attributes':{'accession':filing['accessionNumber']},'unit':'USD','value':v} for c,v in [('Revenues','49000000000'),('RevenueFromContractWithCustomerExcludingAssessedTax','45000000000')]]
        return {'reader':Reader(),'prepared':annual,'filing':filing,'period':period,'claims':claims,
                'concepts':[c.split(':')[-1] for c in APPROVED],'current_scope':scope,'current_filing':annual['filing'],
                'current_claims':[{'locator':{'concept':'Revenues','period_start':period['period_start'],'period_end':period['period_end']},
                    'attributes':{'accession':annual['filing']['accessionNumber']},'unit':'USD',
                    'value':'51000000000' if wrong_current_fact else '50000000000'}]}

    def test_current_comparative_proves_concept_without_replacing_original_value(self):
        from vnext.normal_companyfacts_results import _prior_revenue_from_comparative
        args=self.comparative_inputs();kept,scope=_prior_revenue_from_comparative(**args)
        self.assertEqual([c['value'] for c in kept],['49000000000'])
        self.assertEqual(scope['comparative_reports'][0]['value'],'50000000000')
        self.assertTrue(scope['original_value_retained'])
        self.assertFalse(scope['original_prior_statement_scope_proven'])
        from vnext.paired_measure_v1 import paired_measure_problem
        current={'locator':{'concept':'Revenues','period_start':'2025-01-01','period_end':'2025-12-31'},
                 'attributes':{'accession':args['current_filing']['accessionNumber']},'value':'58496000000','unit':'USD'}
        comparison={**kept[0],'attributes':{'accession':args['current_filing']['accessionNumber']},'value':'50000000000'}
        route={'branches':[{'components':[{'approved_concepts':args['concepts'],'accession_role':role} for role in ('current','prior')]}]}
        problem,_=paired_measure_problem(route=route,claims=[current,*kept],current_claims=[current,comparison],
            accessions={'current':args['current_filing']['accessionNumber'],'prior':args['filing']['accessionNumber']})
        self.assertIsNotNone(problem)

    def test_comparative_wrong_row_year_and_original_xml_amount_are_rejected(self):
        from vnext.normal_companyfacts_results import _prior_revenue_from_comparative
        for options in ({'wrong_row':True},{'wrong_header':True},{'original_value':'48000000000'},
                        {'wrong_scale':True},{'wrong_current_fact':True}):
            with self.subTest(options=options),self.assertRaises(ValueError):
                _prior_revenue_from_comparative(**self.comparative_inputs(**options))

    def test_unknown_contract_or_disabled_validation_cannot_opt_in(self):
        for entry in (resolve_ordinary_zero_ai_metric, prepare_ordinary_zero_ai_run_input):
            for contract in ('unknown', 'reported-total-v2'):
                with self.subTest(entry=entry.__name__, contract=contract):
                    with self.assertRaisesRegex(ValueError, 'REVENUE_SCOPE_CONTRACT_INVALID'):
                        entry(repo_root=Path(__file__).resolve().parents[2], company_id='pfizer',
                              metric_id='B01', revenue_scope_contract=contract)

    def test_new_proof_dependencies_invalidate_only_consuming_metrics(self):
        from vnext import ordinary_current_update as update
        root = Path(__file__).resolve().parents[2]
        original_hash = update.sha256_file
        for relative in ('scripts/vnext/selected_reported_revenue_v2.py', 'scripts/vnext/historical_fiscal_labels.py'):
            for metric in ('B01', 'B02', 'B03', 'C01'):
                with self.subTest(path=relative, metric=metric):
                    before = update._configuration(root, 'pfizer', metric)
                    with patch.object(update, 'sha256_file', side_effect=lambda *, path:
                            'changed-selected-total-proof' if path==root/relative else original_hash(path=path)):
                        after = update._configuration(root, 'pfizer', metric)
                    self.assertEqual(before!=after, metric in {'B01','B02','B03'})

    def test_standard_preceding_navigation_is_preserved_without_admitting_scope_prose(self):
        source, _, annual = originals()
        def with_intro(text):
            raw = source['raw_bytes'].replace(b'<div>Consolidated Statements of Income</div>',
                text.encode()+b'<div>Consolidated Statements of Income</div>')
            return {**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],
                    'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
        scope, _, _ = _revenue_admission(primary=with_intro(
            '<div>See accompanying Notes.</div><div>57</div><div>Table of Contents</div>'),
            annual=annual, approved_concepts=APPROVED, contract='reported-total-v2')
        navigation=scope['reported_totals'][0]['statement_scope']['preceding_navigation_sources']
        self.assertEqual([b['visible_text'] for b in navigation],
                         ['See accompanying Notes.','57','Table of Contents'])
        with self.assertRaisesRegex(ValueError, 'STATEMENT_HEADING_SCOPE_UNRESOLVED'):
            _revenue_admission(primary=with_intro('<div>Only Subsidiary Beta is included.</div>'),
                annual=annual,approved_concepts=APPROVED,contract='reported-total-v2')
        after=source['raw_bytes'].replace(b'</div><table>',b'</div><div>See accompanying Notes.</div><table>')
        changed={**source,'raw_bytes':after,'source_reference':{**source['source_reference'],
            'raw_asset_id':'sha256:'+sha256_bytes(content=after)}}
        with self.assertRaisesRegex(ValueError, 'STATEMENT_HEADING_SCOPE_UNRESOLVED'):
            _revenue_admission(primary=changed,annual=annual,approved_concepts=APPROVED,
                               contract='reported-total-v2')

    def test_fiscal_header_and_standard_cost_groups_do_not_relax_scope_annotations(self):
        source, _, annual=originals()
        raw=source['raw_bytes'].replace(b'Year Ended December 31,',b'Fiscal Year Ended December 31,')
        raw=raw.replace(b'<tr><td>Cost of sales</td>',
            b'<tr><td>Cost of revenues (1)(2):</td><td></td></tr><tr><td>Operating expenses (1)(2):</td><td></td></tr><tr><td>Cost of sales</td>')
        changed={**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],
            'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
        scope,_,_=_revenue_admission(primary=changed,annual=annual,approved_concepts=APPROVED,
                                     contract='reported-total-v2')
        self.assertEqual(scope['status'],'REPORTED_CONSOLIDATED_TOTAL')
        bad=raw.replace(b'Operating expenses (1)(2):',b'Operating expenses of Subsidiary Beta only:')
        changed={**changed,'raw_bytes':bad,'source_reference':{**changed['source_reference'],
            'raw_asset_id':'sha256:'+sha256_bytes(content=bad)}}
        with self.assertRaisesRegex(ValueError,'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
            _revenue_admission(primary=changed,annual=annual,approved_concepts=APPROVED,
                               contract='reported-total-v2')

    def test_late_fiscal_header_before_amounts_is_checked_against_native_interval(self):
        source, _, annual=originals()
        for day in (30,31):
            raw=source['raw_bytes'].replace(b'<tr><td>Product revenues</td>',
                ('<tr><td>Fiscal Year Ended December '+str(day)+',</td><td>57</td></tr><tr><td>Product revenues</td>').encode())
            changed={**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],
                'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
            with self.subTest(day=day):
                if day==30:
                    with self.assertRaisesRegex(ValueError,'VISIBLE_END_DAY_CONFLICT'):
                        _revenue_admission(primary=changed,annual=annual,approved_concepts=APPROVED,
                                           contract='reported-total-v2')
                else:
                    scope,_,_=_revenue_admission(primary=changed,annual=annual,approved_concepts=APPROVED,
                                               contract='reported-total-v2')
                    self.assertTrue(any('Fiscal Year' in h['text'] for h in scope['reported_totals'][0]['end_headers']))

    def test_cost_group_non_numeric_parenthesis_is_not_an_invented_footnote(self):
        source, _, annual=originals()
        for label in ('Operating expenses (Europe):','Cost of revenues (Subsidiary):'):
            raw=source['raw_bytes'].replace(b'<tr><td>Cost of sales</td>',
                ('<tr><td>'+label+'</td><td></td></tr><tr><td>Cost of sales</td>').encode())
            changed={**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],
                'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
            with self.subTest(label=label),self.assertRaisesRegex(ValueError,'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
                _revenue_admission(primary=changed,annual=annual,approved_concepts=APPROVED,
                                   contract='reported-total-v2')


class PublicRowRevenueScopeContextTest(unittest.TestCase):
    def test_public_row_context_names_revenue_scope_by_identity_not_source_rows(self):
        from vnext.ordinary_projection import _display_selection
        scope = {'scope_id': 'sha256:abc', 'method': 'SELECTED_REPORTED_CONSOLIDATED_REVENUE_V2',
                 'status': 'REPORTED_CONSOLIDATED_TOTAL', 'complete_scope_proven': True,
                 'selected_fiscal_column_year': 2025,
                 'annual_input': {'table_input': {'x' * 1000: 1}}, 'original_reports': [{'row': i} for i in range(500)],
                 'reported_totals': [{'statement_scope': {'intervening_sources': ['y' * 5000]}}]}
        selection = {'status': 'PASS', 'income_period': {'period_end': '2026-01-31'}, 'revenue_scope': scope}
        shown = _display_selection(selection)
        self.assertEqual(shown['revenue_scope'], {
            'scope_id': 'sha256:abc', 'method': 'SELECTED_REPORTED_CONSOLIDATED_REVENUE_V2',
            'status': 'REPORTED_CONSOLIDATED_TOTAL', 'complete_scope_proven': True,
            'selected_fiscal_column_year': 2025})
        self.assertEqual({k: v for k, v in shown.items() if k != 'revenue_scope'},
                         {'status': 'PASS', 'income_period': {'period_end': '2026-01-31'}})
        self.assertLess(len(json.dumps(shown)), 400)
        # The case selection itself keeps the full scope for evidence rendering.
        self.assertIn('original_reports', selection['revenue_scope'])
        self.assertIsNone(_display_selection(None))
        untouched = {'status': 'N_A_STRUCTURAL', 'depreciation_scope': {'complete_business_scope_proven': False}}
        self.assertEqual(_display_selection(untouched), untouched)
