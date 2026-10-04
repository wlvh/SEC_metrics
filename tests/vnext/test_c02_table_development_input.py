"""Input relationships, coverage and refusal; no model/semantic acceptance."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from vnext.c02_table_context_417ccfb7 import assert_matches, expanded_view, model_view
from vnext.c02_table_development_input import (
    development_request, prepare_ordinary_table_development_input)
from vnext.table_grid import build_table_grid


class C02TableDevelopmentInputTest(unittest.TestCase):
    def setUp(self):
        raw = (b'<html><body><table><caption>Current committee members</caption>'
               b'<tr><th rowspan="2">Member</th><th colspan="2">Committee</th></tr>'
               b'<tr><th>Audit</th><th>Risk</th></tr>'
               b'<tr><td>Alex</td><td>Chair</td><td>Member</td></tr></table>'
               b'<table><tr><td>Unrelated remuneration</td></tr></table></body></html>')
        self.raw_id = 'sha256:' + hashlib.sha256(raw).hexdigest()
        self.grid = build_table_grid(html_bytes=raw, parent_raw_asset_ids=[self.raw_id],
                                     storage_uri='development/test-grid.json')
        self.doc = {'raw_asset_id': self.raw_id, 'source_state': 'COMPLETE_LOCAL_DOCUMENT',
                    'registrant_names': ['Example Corp'],
                    'source_filing': {'form': 'DEF 14A', 'filingDate': '2026-03-10',
                                     'accessionNumber': '0000000001-26-000001'},
                    'blocks': [{'block_index': i, 'text': text} for i, text in enumerate(
                        ['Current committee members', 'Alex', 'Chair', 'Member', 'Member'])]}
        self.target = {'period_start': '2025-02-01', 'period_end': '2026-01-31'}

    def test_complete_rows_columns_spans_and_duplicate_block_ids(self):
        view = model_view(self.doc, self.grid)
        blocks, tables = expanded_view(json.loads(json.dumps(view)))
        self.assertEqual(blocks, ['Current committee members', 'Alex', 'Chair', 'Member', 'Member'])
        self.assertEqual(tables[0]['cells'], [
            [('Member', True), ('Committee', True), ('Committee', True)],
            [('Member', True), ('Audit', True), ('Risk', True)],
            [('Alex', False), ('Chair', False), ('Member', False)]])
        self.assertEqual(tables[1]['cells'], [[('Unrelated remuneration', False)]])

    def test_swapping_committee_columns_is_not_equivalent(self):
        view = model_view(self.doc, self.grid)
        x = view['tables'][0]['x']
        chair = next(c for c in x if c[:2] == [2, 1])
        member = next(c for c in x if c[:2] == [2, 2])
        chair[2], member[2] = member[2], chair[2]
        with self.assertRaisesRegex(ValueError, 'EXPANDED_GRID_CHANGED'):
            assert_matches(view, self.doc, self.grid)

    def test_block_text_or_omitted_table_is_rejected(self):
        view = model_view(self.doc, self.grid)
        changed = copy.deepcopy(view)
        changed['strings'][4] = 'Invented member'
        with self.assertRaisesRegex(ValueError, 'BLOCK_TEXT_OR_ORDER_CHANGED'):
            assert_matches(changed, self.doc, self.grid)
        view['tables'].pop()
        with self.assertRaisesRegex(ValueError, 'EXPANDED_GRID_CHANGED'):
            assert_matches(view, self.doc, self.grid)

    def test_wrong_raw_parent_is_rejected(self):
        doc = {**self.doc, 'raw_asset_id': 'sha256:' + '0' * 64}
        with self.assertRaisesRegex(ValueError, 'RAW_PARENT_CHANGED'):
            model_view(doc, self.grid)

    def test_overlapping_spans_are_rejected(self):
        view = model_view(self.doc, self.grid)
        view['tables'][0]['x'].append(view['tables'][0]['x'][0])
        with self.assertRaisesRegex(ValueError, 'OVERLAPPING_SPANS'):
            expanded_view(view)

    def test_request_has_complete_view_and_actual_reporting_interval(self):
        result = development_request(document=self.doc, derived=self.grid,
                                     target=self.target, task_text='Extract composition facts.')
        body = json.loads(result['request_body'])
        self.assertEqual(json.loads(body['messages'][1]['content']), result['view'])
        self.assertIn('2025-02-01 through 2026-01-31', body['messages'][0]['content'])
        self.assertIn('not a board measurement', body['messages'][0]['content'])
        self.assertEqual(body['max_tokens'], 4096)
        self.assertTrue(result['measurement']['fits'])

    def test_over_limit_is_retained_not_trimmed_or_accepted(self):
        with patch('vnext.c02_table_development_input.measure_request',
                   return_value={'fits': False, 'context_tokens': 200001}):
            result = development_request(document=self.doc, derived=self.grid,
                                         target=self.target, task_text='Extract composition facts.')
        self.assertFalse(result['measurement']['fits'])
        self.assertEqual(result['view']['block_count'], 5)
        self.assertEqual(len(result['view']['tables']), 2)

    def test_incomplete_document_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_SOURCE'):
            development_request(document={**self.doc, 'source_state': 'INCOMPLETE'},
                                derived=self.grid, target=self.target, task_text='Extract.')

    def test_blocked_ordinary_source_is_not_substituted(self):
        with patch('vnext.c02_table_development_input.prepare_normal_business_text_input',
                   return_value={'text_arguments': None}):
            with self.assertRaisesRegex(ValueError, 'SOURCE_PREPARATION_BLOCKED'):
                prepare_ordinary_table_development_input(data_root='.', company_id='example',
                                                         task_text='Extract.')

    def test_ambiguous_governance_source_is_not_silently_selected(self):
        args = {'source_references': [{'source_reference_id': 'one'}, {'source_reference_id': 'two'}],
                'source_filings': {'one': {'form': 'DEF 14A'}, 'two': {'form': '10-K/A'}}}
        with patch('vnext.c02_table_development_input.prepare_normal_business_text_input',
                   return_value={'text_arguments': args}):
            with self.assertRaisesRegex(ValueError, 'GOVERNANCE_SOURCE_NOT_UNIQUE'):
                prepare_ordinary_table_development_input(data_root='.', company_id='example',
                                                         task_text='Extract.')
