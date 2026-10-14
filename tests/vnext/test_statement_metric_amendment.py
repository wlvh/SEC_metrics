"""Metric-specific source properties; constructed originals have no business credit."""
from copy import deepcopy
import unittest

from tests.vnext import test_income_amendment_paragraph_dispatch as paragraph_fixture
from vnext.ordinary_income_input import inspect_income_amendment
from vnext.statement_metric_amendment import inspect_statement_metric_amendment


class StatementMetricAmendmentTest(unittest.TestCase):
    scope=paragraph_fixture.IncomeParagraphDispatchTest.scope

    def test_b05_original_cash_flow_roles_have_their_own_property(self):
        scope,raw=self.scope();original=deepcopy(scope)
        result=inspect_statement_metric_amendment(scope,raw,metric_id='B05')
        self.assertEqual(['capital_expenditures','operating_cash_flow'],result['covered_component_roles'])
        self.assertEqual('ORIGINAL_REPORTED_FREE_CASH_FLOW_COMPONENT_VALUES',result['input_class'])
        self.assertEqual(scope['scope_id'],result['original_scope_id'])
        self.assertEqual(scope,original)
        self.assertFalse(result['metric_result_created'])
        self.assertFalse(result['annual_continuity_proven'])

    def test_b05_changed_or_new_cash_flow_components_cannot_be_cleared(self):
        for text in ('Net cash provided by operating activities has been corrected.',
                     'Capital expenditures have been restated.',
                     'Operating cash flow was $42 million.',
                     '<table><tr><td>Net cash provided by operating activities</td><td>42</td></tr></table>',
                     '<table><tr><td>Payments to acquire property, plant and equipment</td><td>42</td></tr></table>'):
            scope,raw=self.scope('<div>'+text+'</div>')
            with self.subTest(text=text),self.assertRaises(ValueError):
                inspect_statement_metric_amendment(scope,raw,metric_id='B05')

    def cash_flow_scope(self, disclosure='We generated net operating cash flow of $42 million.',
                        introduction=None, original_transform=lambda raw:raw):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from tests.vnext.test_instant_amendment_paragraph_api import filing_html
        from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
        from vnext.sources import raw_blob_record, source_reference_record
        introduction=introduction or ("The Committee evaluated the Company's 2024 qualitative performance goals, "
                                      "which included the following highlights:")
        fact=('<ix:nonFraction name="us-gaap:NetCashProvidedByUsedInOperatingActivities" '
              'contextRef="C" unitRef="usd" scale="6" decimals="-6">42</ix:nonFraction>')
        original=filing_html(False).replace(b'<html ',
            b'<html xmlns:us-gaap="http://fasb.org/us-gaap/2024" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" ')
        original=original.replace(b'</ix:resources>', b'<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources>')
        statement=('<p>EXAMPLE CORP AND SUBSIDIARIES</p><p>CONSOLIDATED STATEMENTS OF CASH FLOWS</p>'
                   '<p>(In millions)</p><table><tr><th></th><th>Year Ended December 31,</th></tr>'
                   '<tr><th></th><th>2024</th></tr><tr><td>Net cash flow provided by operating activities</td>'
                   '<td>'+fact+'</td></tr></table>')
        original=original_transform(original.replace(b'</body>',statement.encode()+b'</body>'))
        amendment=filing_html(True, '<p>'+introduction+'</p><table><tr><td><p>•</p></td><td><p>'+disclosure+'</p></td></tr></table>')
        with TemporaryDirectory() as folder:
            root=Path(folder);items=[]
            for amended,raw in ((False,original),(True,amendment)):
                name='amended.htm' if amended else 'original.htm';(root/name).write_bytes(raw)
                blob=raw_blob_record(repo_root=root,repo_relative_path=name,media_type='text/html')
                accession='0000000001-25-00000'+('2' if amended else '1')
                ref=source_reference_record(raw_blob=blob,company_id='constructed',
                    source_url='https://www.sec.gov/Archives/edgar/data/1/'+accession.replace('-','')+'/'+name,
                    accession=accession,document_name=name,source_role='target_primary',request_attempt_id='constructed-no-credit')
                filing={'form':'10-K/A' if amended else '10-K','reportDate':'2024-12-31',
                        'filingDate':'2025-04-25' if amended else '2025-02-26',
                        'accessionNumber':accession,'primaryDocument':name}
                items.append({'raw':raw,'blob':blob,'reference':ref,'filing':filing})
            scope=inspect_annual_amendment_scope(original=items[0],amendment=items[1],
                company_id='constructed',cik='1',note_layout='inline-paragraphs-v2')
        return scope,amendment,original

    def test_b05_duplicate_disclosure_is_bound_to_original_total_period_subject_and_units(self):
        scope,raw,original_raw=self.cash_flow_scope();saved=deepcopy(scope)
        value=inspect_statement_metric_amendment(scope,raw,metric_id='B05',original_raw=original_raw)
        relation=value['duplicate_component_disclosures'][0]
        self.assertEqual(relation['role'],'operating_cash_flow')
        self.assertEqual(relation['reported_value'],'42000000')
        self.assertEqual(relation['original_fact']['period'],scope['original']['period'])
        self.assertEqual(value['additional_component_disclosures'],[])
        self.assertEqual(scope,saved)
        self.assertFalse(value['metric_result_created'])

    def test_b05_same_amount_alone_does_not_prove_duplicate_disclosure(self):
        cases=[{'disclosure':'We generated net operating cash flow of $43 million.'},
               {'disclosure':'We generated net operating cash flow of €42 million.'},
               {'disclosure':'We generated adjusted net operating cash flow of $42 million.'},
               {'disclosure':'They generated net operating cash flow of $42 million.'},
               {'disclosure':'We generated net operating cash flow of $42 million in 2023.'},
               {'disclosure':'We generated net operating cash flow of $42 million — for 2023.'},
               {'disclosure':'We generated net operating cash flow of $42 million — for a subsidiary.'},
               {'disclosure':'We generated net operating cash flow of $42 million — an improvement from 2023 — and the amount excludes a segment.'},
               {'disclosure':'We generated net operating cash flow of $42 million for a subsidiary.'},
               {'disclosure':'We learned that Other Corp reported net operating cash flow of $42 million.'},
               {'disclosure':'<q>We generated net operating cash flow of $42 million.</q>'},
               {'introduction':"The Committee evaluated the Company's 2023 qualitative performance goals, which included the following highlights:"},
               {'disclosure':'We generated net operating cash flow of $42 million from continuing operations.'},
               {'original_transform':lambda raw:raw.replace(b'operating activities</td>',b'operating activities from continuing operations</td>')},
               {'original_transform':lambda raw:raw.replace(b'contextRef="C" unitRef="usd"',b'contextRef="C" unitRef="usd" sign="-"')},
               {'original_transform':lambda raw:raw.replace(b'iso4217:USD</xbrli:measure>',b'iso4217:EUR</xbrli:measure>')}]
        for case in cases:
            scope,raw,original_raw=self.cash_flow_scope(**case)
            with self.subTest(case=case),self.assertRaises(ValueError):
                inspect_statement_metric_amendment(scope,raw,metric_id='B05',original_raw=original_raw)
        scope,raw,original_raw=self.cash_flow_scope()
        with self.assertRaisesRegex(ValueError,'ORIGINAL_RAW_BINDING_CHANGED'):
            inspect_statement_metric_amendment(scope,raw,metric_id='B05',original_raw=original_raw+b' ')
        with self.assertRaisesRegex(ValueError,'RELATION_UNRESOLVED'):
            inspect_statement_metric_amendment(scope,raw,metric_id='B05')

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
                             ('B07','Operating income (loss)'),
                             ('B04','Net income attributable to common shareholders'),
                             ('B07','Interest expense, net of interest income')]:
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
        for metric in ('B01','B03','B06','B08','D04'):
            with self.subTest(metric=metric),self.assertRaisesRegex(ValueError,'METRIC_NOT_SUPPORTED'):
                inspect_statement_metric_amendment(scope,raw,metric_id=metric)
        with self.assertRaisesRegex(ValueError,'RAW_BINDING_CHANGED'):
            inspect_statement_metric_amendment(scope,raw+b' ',metric_id='B04')
