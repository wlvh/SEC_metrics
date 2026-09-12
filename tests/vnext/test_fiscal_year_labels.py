"""Real noncalendar disclosures and independently varied label conflicts."""
import copy
import hashlib
import html
import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.fiscal_year_labels import FiscalYearLabelError, inspect_fiscal_year_labels, inspect_saved_fiscal_year_label


class FiscalYearLabelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases={}
        with original_sources_only():
            for company in ('salesforce','macys'):
                report=inspect_saved_fiscal_year_label(repo_root=ROOT,company_id=company)
                prepared=report['prepared_input']
                cls.cases[company]={'report':report,
                    'primary':(ROOT/prepared['table_input']['source_repo_relative_path']).read_bytes(),
                    'facts':(ROOT/prepared['companyfacts_input']['source_repo_relative_path']).read_bytes(),
                    'filing':prepared['filing'],'cik':prepared['entity']}

    def inspect(self,raw=None,facts=None,company='salesforce'):
        case=self.cases[company]
        primary=raw if raw is not None else case['primary']
        cf=facts if facts is not None else case['facts']
        with original_sources_only():
            return inspect_fiscal_year_labels(primary_bytes=primary,companyfacts_bytes=cf,
                expected_primary_sha256=hashlib.sha256(primary).hexdigest(),expected_companyfacts_sha256=hashlib.sha256(cf).hexdigest(),
                expected_cik=case['cik'],filing=case['filing'])

    def test_salesforce_actual_two_definitions_conflict_with_dei_and_same_filing_cf(self):
        x=self.cases['salesforce']['report']['inspection']
        self.assertEqual('SOURCE_LABEL_CONFLICT',x['status'])
        self.assertEqual({'period_start':'2025-02-01','period_end':'2026-01-31'},x['actual_period'])
        self.assertEqual(2025,x['dei_fiscal_year'])
        self.assertEqual([2025],x['companyfacts_fiscal_year_values'])
        self.assertEqual(604,x['companyfacts_same_accession_row_count'])
        self.assertEqual([2026],x['current_definition_labels'])
        self.assertEqual(2026,x['source_defined_fiscal_year'])
        self.assertEqual(2,len(x['source_definitions']))
        self.assertIsNone(x['analysis_group_year'])
        self.assertFalse(x['existing_input_or_Run_changed'])
        self.assertEqual(2025,self.cases['salesforce']['report']['prepared_input']['table_input']['target_period']['fiscal_year'])
        # The same filing's fy labels are not 604 independent statements of
        # each monetary fact's measurement year: comparative periods remain.
        self.assertTrue(any(r['period_end']=='2024-01-31' for r in x['companyfacts_rows']))

    def test_macys_real_52_53_week_definition_keeps_start_year_label(self):
        x=self.cases['macys']['report']['inspection']
        self.assertEqual('SOURCE_LABELS_CONSISTENT',x['status'])
        self.assertEqual([2025],x['current_definition_labels'])
        self.assertEqual(638,x['companyfacts_same_accession_row_count'])
        self.assertEqual({'period_start':'2025-02-02','period_end':'2026-01-31'},x['actual_period'])
        self.assertEqual(2,len(x['source_definitions']))
        self.assertTrue(any({'fiscal_year':2023,'period_end':'2024-02-03'} in d['mapping'] for d in x['source_definitions']))
        self.assertTrue(any('53 weeks' in d['text'] for d in x['source_definitions']))
        self.assertEqual(2025,x['new_rule_label_proposal'])

    def test_every_definition_dei_and_context_returns_to_original_bytes(self):
        for company,case in self.cases.items():
            x=case['report']['inspection']
            raw=case['primary']
            for definition in x['source_definitions']:
                span=raw[definition['raw_start_byte']:definition['raw_end_byte']]
                self.assertEqual(hashlib.sha256(span).hexdigest(),definition['raw_span_sha256'])
                text=' '.join(html.unescape(re.sub('<[^>]+>','',span.decode())).split())
                self.assertEqual(definition['text'],text)
            for fact in x['dei_facts']:
                span=raw[fact['raw_start_byte']:fact['raw_end_byte']]
                self.assertEqual(hashlib.sha256(span).hexdigest(),fact['raw_span_sha256'])
                lexical=' '.join(html.unescape(re.sub('<[^>]+>','',span.decode())).split())
                self.assertEqual(fact['value_raw'],lexical)
                locator=fact['context_locator']
                context=raw[locator['raw_start_byte']:locator['raw_end_byte']]
                self.assertEqual(hashlib.sha256(context).hexdigest(),locator['raw_span_sha256'])
                self.assertIn(fact['context']['context_ref'].encode(),context)
            cf=json.loads(case['facts'])
            for row in x['companyfacts_rows']:
                at=row['locator']
                actual=cf['facts'][at['taxonomy']][at['concept']]['units'][at['unit']][at['index']]
                self.assertEqual(x['accession'],actual['accn'])
                self.assertEqual(row['fiscal_year_raw'],actual['fy'])

    def test_competing_same_period_definitions_never_choose_by_majority_or_metadata(self):
        raw=self.cases['salesforce']['primary']
        changed=raw.replace(b'References to fiscal 2026, for example,',b'References to fiscal 2025, for example,',1)
        x=self.inspect(changed)
        self.assertEqual('EXPLICIT_DEFINITION_UNRESOLVED',x['status'])
        self.assertEqual([2025,2026],x['current_definition_labels'])
        self.assertIsNone(x['new_rule_label_proposal'])
        self.assertEqual(2,len(x['source_definitions']))

    def test_other_period_examples_and_unsupported_subject_do_not_create_a_label(self):
        raw=self.cases['salesforce']['primary']
        old=raw.replace(b'References to fiscal 2026, for example, refer to the fiscal year ending January 31, 2026.',
                        b'References to fiscal 2024, for example, refer to the fiscal year ending January 31, 2024.')
        x=self.inspect(old)
        self.assertEqual([],x['current_definition_labels'])
        self.assertIsNone(x['new_rule_label_proposal'])
        metadata=json.loads(self.cases['salesforce']['facts'])
        for concepts in metadata['facts'].values():
            for concept in concepts.values():
                for values in concept['units'].values():
                    for fact in values:
                        if fact.get('accn')==self.cases['salesforce']['filing']['accessionNumber']:fact['fy']=2026
        x=self.inspect(old,facts=json.dumps(metadata).encode())
        self.assertEqual('SOURCE_LABEL_CONFLICT',x['status'])
        self.assertIsNone(x['new_rule_label_proposal'])
        other=raw.replace(b'Our fiscal year ends',b'Example Supplier fiscal year ends')
        x=self.inspect(other)
        self.assertEqual('EXPLICIT_DEFINITION_UNRESOLVED',x['status'])
        self.assertIsNone(x['new_rule_label_proposal'])

    def test_utf8_prefix_does_not_turn_character_offsets_into_byte_offsets(self):
        raw=self.cases['salesforce']['primary']
        changed=raw.replace(b'<body', '<!-- 审阅字节 -->'.encode()+b'<body',1)
        x=self.inspect(changed)
        self.assertEqual('SOURCE_LABEL_CONFLICT',x['status'])
        for d in x['source_definitions']:
            self.assertEqual(d['raw_span_sha256'],hashlib.sha256(changed[d['raw_start_byte']:d['raw_end_byte']]).hexdigest())

    def test_companyfacts_subject_accession_and_source_digest_cannot_be_borrowed(self):
        case=self.cases['salesforce']
        cf=json.loads(case['facts']);cf['cik']=12345
        with self.assertRaisesRegex(FiscalYearLabelError,'COMPANYFACTS_ENTITY_CONFLICT'):
            self.inspect(facts=json.dumps(cf).encode())
        cf=json.loads(case['facts'])
        for concepts in cf['facts'].values():
            for concept in concepts.values():
                for values in concept['units'].values():
                    for fact in values:
                        if fact.get('accn')==case['filing']['accessionNumber']:fact['accn']='0000000000-26-000001'
        with self.assertRaisesRegex(FiscalYearLabelError,'SAME_ACCESSION_COMPANYFACTS_MISSING'):
            self.inspect(facts=json.dumps(cf).encode())
        with self.assertRaisesRegex(FiscalYearLabelError,'SOURCE_BYTES_CHANGED'):
            inspect_fiscal_year_labels(primary_bytes=case['primary']+b' ',companyfacts_bytes=case['facts'],
                expected_primary_sha256=hashlib.sha256(case['primary']).hexdigest(),expected_companyfacts_sha256=hashlib.sha256(case['facts']).hexdigest(),
                expected_cik=case['cik'],filing=case['filing'])


if __name__=='__main__':
    unittest.main()
