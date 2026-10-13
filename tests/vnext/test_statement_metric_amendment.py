"""Metric-specific source properties; constructed originals have no business credit."""
from copy import deepcopy
import unittest

from tests.vnext import test_income_amendment_paragraph_dispatch as paragraph_fixture
from vnext.ordinary_income_input import inspect_income_amendment
from vnext.statement_metric_amendment import inspect_statement_metric_amendment


class StatementMetricAmendmentTest(unittest.TestCase):
    scope=paragraph_fixture.IncomeParagraphDispatchTest.scope

    def test_clean_property_is_explicit_and_preserves_old_scope_and_defaults(self):
        scope,raw=self.scope();original=deepcopy(scope)
        old=inspect_income_amendment(scope,raw,paragraph_fixture.RULES)
        for metric,roles in [('B04',['net_income']),('B07',[
            'aggregate_nonoperating','interest_expense','operating_income','pretax_income'])]:
            result=inspect_statement_metric_amendment(scope,raw,metric_id=metric)
            self.assertEqual(result['metric_id'],metric)
            self.assertEqual(result['original_scope_id'],scope['scope_id'])
            self.assertEqual(result['covered_component_roles'],roles)
            self.assertNotEqual(result['input_class'],old['input_class'])
            self.assertFalse(result['metric_result_created'])
            self.assertFalse(result['annual_continuity_proven'])
            self.assertFalse(result['debt_completeness_proven'])
        self.assertEqual(scope,original)
        self.assertEqual(old,inspect_income_amendment(scope,raw,paragraph_fixture.RULES))

    def test_current_component_corrections_plain_and_inline_are_not_cleared(self):
        for metric,text in (
            ('B04','Our net income has been corrected.'),
            ('B04','Our net <span>income</span> has been cor<div style="display:inline">rected</div>.'),
            ('B04','Our net earnings have been restated.'),
            ('B04','Our income tax expense has been corrected.'),
            ('B07','Our interest expense has been revised.'),
            ('B07','Our pretax income has been corrected.'),
            ('B07','Our non-operating expense has been restated.'),
            ('B07','Our interest ex<div style="display:inline">pense</div> has been rev<div style="display:inline">ised</div>.')):
            scope,raw=self.scope('<div>'+text+'</div>')
            with self.subTest(metric=metric,text=text),self.assertRaisesRegex(ValueError,'CORRECTION.*UNRESOLVED'):
                inspect_statement_metric_amendment(scope,raw,metric_id=metric)

    def test_adjusted_compensation_target_is_not_a_reported_operating_income_row(self):
        scope,raw=self.scope('<table><tr><th>Performance metric</th><th>Goal</th></tr>'
            '<tr><td>Adjusted Operating Income Before Depreciation and Amortization</td><td>42</td></tr></table>')
        self.assertEqual(inspect_statement_metric_amendment(scope,raw,metric_id='B07')['metric_id'],'B07')

    def test_changed_component_definition_cannot_keep_old_property(self):
        from unittest.mock import patch
        from vnext import statement_metric_amendment as module
        original=module.strict_json_file
        def changed(*,path):
            value=original(path=path)
            if str(path).endswith(module.CATALOG_PATH):
                value=deepcopy(value)
                value['metrics']['B04']['branches'][0]['components'][0]['unit']='EUR'
            return value
        scope,raw=self.scope()
        with patch.object(module,'strict_json_file',side_effect=changed),self.assertRaisesRegex(
                ValueError,'COMPONENT_DEFINITION_CHANGED'):
            inspect_statement_metric_amendment(scope,raw,metric_id='B04')

    def test_new_unmarked_component_amount_needs_a_relation_proof(self):
        for metric,text in [('B04','Net income was $42 million.'),
            ('B04','Net income was €42.'),
            ('B07','Interest expense was USD 42 million.'),
            ('B07','Pretax income was 42 million.'),
            ('B07','Non-operating expense was $42 million.')]:
            scope,raw=self.scope('<div>'+text+'</div>')
            with self.subTest(metric=metric,text=text),self.assertRaisesRegex(
                    ValueError,'COMPONENT_DISCLOSURE_RELATION_UNRESOLVED'):
                inspect_statement_metric_amendment(scope,raw,metric_id=metric)

    def test_unmarked_table_components_keep_their_row_relationship(self):
        for metric,label in [('B04','Net income'),('B07','Interest expense'),
                             ('B07','Operating income (loss)')]:
            extra='<table><tr><th>USD millions</th><th>2024</th></tr><tr><td>'+label+'</td><td>42</td></tr></table>'
            scope,raw=self.scope(extra)
            with self.subTest(metric=metric,label=label),self.assertRaisesRegex(
                    ValueError,'COMPONENT_DISCLOSURE_RELATION_UNRESOLVED'):
                inspect_statement_metric_amendment(scope,raw,metric_id=metric)
        scope,raw=self.scope('<table><tr><th>USD millions</th><th>2024</th></tr>'
            '<tr><td>Net income</td><td>—</td></tr></table>')
        with self.assertRaisesRegex(ValueError,'COMPONENT_DISCLOSURE_RELATION_UNRESOLVED'):
            inspect_statement_metric_amendment(scope,raw,metric_id='B04')

    def test_flag_quote_period_and_unknown_layout_remain_refused(self):
        for transform in (lambda raw:raw.replace('☐'.encode(),'☒'.encode()),
            lambda raw:raw.replace(b'Example Corp (the',b'<q>Example Corp (the').replace(
                b'otherwise requires.</p>',b'otherwise requires.</q></p>')):
            scope,raw=self.scope(transform=transform)
            with self.assertRaises(ValueError):inspect_statement_metric_amendment(scope,raw,metric_id='B04')
        scope,raw=self.scope();scope['fiscal_window_unchanged']=False
        with self.assertRaises(ValueError):inspect_statement_metric_amendment(scope,raw,metric_id='B04')
        scope,raw=self.scope();scope['note_layout']='unknown'
        with self.assertRaises(ValueError):inspect_statement_metric_amendment(scope,raw,metric_id='B07')

    def test_other_metrics_and_mismatched_raw_bytes_gain_no_property(self):
        scope,raw=self.scope()
        for metric in ('B01','B03','B05','B06','B08','D04'):
            with self.subTest(metric=metric),self.assertRaisesRegex(ValueError,'METRIC_NOT_SUPPORTED'):
                inspect_statement_metric_amendment(scope,raw,metric_id=metric)
        with self.assertRaisesRegex(ValueError,'RAW_BINDING_CHANGED'):
            inspect_statement_metric_amendment(scope,raw+b' ',metric_id='B04')
