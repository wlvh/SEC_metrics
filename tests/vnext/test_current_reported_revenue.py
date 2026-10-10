"""Current opt-in and source-proof controls; constructed rows carry no business credit."""
import inspect
from pathlib import Path
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
            for metric in ('B01', 'B03', 'C01'):
                with self.subTest(path=relative, metric=metric):
                    before = update._configuration(root, 'pfizer', metric)
                    with patch.object(update, 'sha256_file', side_effect=lambda *, path:
                            'changed-selected-total-proof' if path==root/relative else original_hash(path=path)):
                        after = update._configuration(root, 'pfizer', metric)
                    self.assertEqual(before!=after, metric in {'B01','B03'})

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
