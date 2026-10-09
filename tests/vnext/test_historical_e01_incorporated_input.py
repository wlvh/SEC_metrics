"""Mechanical successor-input controls; no source or semantic credit."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from vnext import historical_e01_incorporated_input as successor
from vnext import historical_ma_confirmation as original
from tests.vnext.test_historical_ma_confirmation import request, POINTER, LOAN


class IncorporatedE01InputTest(TestCase):
    def prepare(self, text='The company announces a leadership change, not an acquisition.',
                status='VERIFIED_SAVED_SOURCE', missing_parent=False):
        legacy = request(POINTER, LOAN)
        item = legacy['items'][0]
        declaration = {'company_id': 'example', 'report_end': '2025-12-31',
            'item_id': 'missing' if missing_parent else item['item_id'],
            'accession': item['accession'],
            'parent_url': 'https://www.sec.gov/Archives/edgar/data/1/000000000125000001/a.htm'}
        dependency = {'parent_item_id': item['item_id'], 'saved_status': status,
            'source_url': declaration['parent_url'].replace('a.htm', 'ex-99.htm')}
        raw = ('<html><body><p>' + text + '</p></body></html>').encode()
        reader = SimpleNamespace(records={}, proofs={}, read=lambda *args, **kwargs: {
            'raw_bytes': raw, 'raw_blob': {'raw_asset_id': 'constructed-attachment'},
            'source_reference': {'source_reference_id': 'constructed-attachment-reference'}})
        with (patch.object(successor, 'strict_json_file', return_value={'items': [declaration]}),
              patch.object(successor, 'attachment_dependencies', return_value=[dependency]),
              patch.object(successor, '_Sources', return_value=reader),
              patch.object(successor, 'verify_ordinary_source_proofs')):
            result = successor.prepare_incorporated_e01_input(data_root=Path('/constructed'),
                predecessor_source={'company_id': 'example', 'request': legacy, 'source_proofs': []})
        return legacy, result

    def answer(self, result):
        rows = []
        for item in result['items']:
            source = item['supplied_sources'][-1]
            rows.append({'item_id': item['item_id'], 'decision': 'DOES_NOT_REPORT_A_TRANSACTION',
                'source_text_id': source['source_text_id'], 'quote': source['text'][:60]})
        return {'item_decisions': rows}

    def test_complete_pool_and_parent_texts_are_unchanged(self):
        legacy, result = self.prepare()
        self.assertEqual([i['text'] for i in legacy['items']], [i['text'] for i in result['items']])
        self.assertEqual([2, 1], [len(i['supplied_sources']) for i in result['items']])
        self.assertNotEqual(legacy['request_id'], result['request_id'])
        self.assertFalse(result['model_executed']); self.assertFalse(result['metric_result_created'])
        self.assertFalse(result['target_model_execution_authorized'])
        self.assertIn('<html>', result['items'][0]['supplied_sources'][1]['raw_html'])

    def test_changed_attachment_changes_input_without_changing_parent(self):
        _, one = self.prepare()
        _, two = self.prepare('This full attachment instead discusses a financing arrangement.')
        self.assertNotEqual(one['source_id'], two['source_id'])
        self.assertEqual(one['items'][0]['text'], two['items'][0]['text'])

    def test_quotes_can_use_the_same_items_separate_attachment(self):
        _, result = self.prepare()
        decisions = successor.validate_incorporated_answer(request=result,
            raw_output=json.dumps(self.answer(result)))
        self.assertEqual(len(result['items']), len(decisions))

    def test_other_items_source_and_invented_quotes_refuse(self):
        _, result = self.prepare(); answer = self.answer(result)
        answer['item_decisions'][1]['source_text_id'] = answer['item_decisions'][0]['source_text_id']
        with self.assertRaisesRegex(ValueError, 'SOURCE_OUTSIDE_ITEM'):
            successor.validate_incorporated_answer(request=result, raw_output=json.dumps(answer))
        answer = self.answer(result); answer['item_decisions'][0]['quote'] = 'Invented merger words which no supplied source actually says.'
        with self.assertRaisesRegex(ValueError, 'QUOTE_NOT_IN_SOURCE'):
            successor.validate_incorporated_answer(request=result, raw_output=json.dumps(answer))

    def test_each_item_and_field_type_are_checked(self):
        _, result = self.prepare(); answer = self.answer(result)
        for rows, reason in ((answer['item_decisions'][:1], 'UNANSWERED_ITEMS'),
                             ([answer['item_decisions'][0]] * 2, 'WRONG_OR_REPEATED_ITEM')):
            with self.assertRaisesRegex(ValueError, reason):
                successor.validate_incorporated_answer(request=result,
                    raw_output=json.dumps({'item_decisions': rows}))
        answer['item_decisions'][0]['source_text_id'] = []
        with self.assertRaisesRegex(ValueError, 'DECISION_FIELD_TYPE'):
            successor.validate_incorporated_answer(request=result, raw_output=json.dumps(answer))

    def test_long_real_quote_reports_length_not_missing_source(self):
        _, result = self.prepare('The company announces a leadership change. ' * 20)
        answer = self.answer(result)
        answer['item_decisions'][0]['quote'] = result['items'][0]['supplied_sources'][-1]['text'][:601]
        with self.assertRaisesRegex(ValueError, 'QUOTE_LENGTH'):
            successor.validate_incorporated_answer(request=result, raw_output=json.dumps(answer))

    def test_positive_and_unresolved_decisions_remain_distinct(self):
        _, result = self.prepare(); answer = self.answer(result)
        for decision in ('REPORTS_A_TRANSACTION', 'CANNOT_TELL_FROM_SUPPLIED_TEXT'):
            answer['item_decisions'][0]['decision'] = decision
            checked = successor.validate_incorporated_answer(request=result,
                raw_output=json.dumps(answer))
            self.assertEqual(decision, checked[result['items'][0]['item_id']]['decision'])
        answer['item_decisions'][0]['decision'] = 'ACCEPTED'
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_DECISION'):
            successor.validate_incorporated_answer(request=result, raw_output=json.dumps(answer))

    def test_absent_and_unrelated_declared_sources_do_not_silently_disappear(self):
        with self.assertRaisesRegex(ValueError, 'DECLARED_SOURCE_MISSING'):
            self.prepare(status='MISSING_SAVED_SOURCE')
        with self.assertRaisesRegex(ValueError, 'DECLARED_PARENT_OUTSIDE_POOL'):
            self.prepare(missing_parent=True)

    def test_old_validator_does_not_accept_successor_output(self):
        legacy, result = self.prepare()
        with self.assertRaisesRegex(original.ConfirmationContractError, 'DECISION_SHAPE'):
            original.validate_answer(request=legacy, raw_output=json.dumps(self.answer(result)))

    def test_one_unresolved_item_withholds_the_complete_window_count(self):
        _, result = self.prepare(); answer = self.answer(result)
        answer['item_decisions'][0]['decision'] = 'REPORTS_A_TRANSACTION'
        answer['item_decisions'][1]['decision'] = 'CANNOT_TELL_FROM_SUPPLIED_TEXT'
        summary = successor.summarize_incorporated_answer(request=result,
            raw_output=json.dumps(answer))
        self.assertIsNone(summary['proposed_count'])
        self.assertEqual('E01_SUPPLIED_SOURCES_UNCONFIRMED', summary['reason'])
        self.assertEqual([result['items'][1]['item_id']], summary['unresolved_item_ids'])
        self.assertFalse(summary['semantic_acceptance_proven'])
        self.assertFalse(summary['metric_result_created'])

    def test_complete_checked_answer_counts_once_without_semantic_credit(self):
        _, result = self.prepare(); answer = self.answer(result)
        answer['item_decisions'][0]['decision'] = 'REPORTS_A_TRANSACTION'
        summary = successor.summarize_incorporated_answer(request=result,
            raw_output=json.dumps(answer))
        self.assertEqual(1, summary['proposed_count'])
        self.assertEqual([result['items'][0]['item_id']], summary['confirmed_item_ids'])
        self.assertEqual([], summary['unresolved_item_ids'])
        self.assertIsNone(summary['reason'])
        self.assertFalse(summary['semantic_acceptance_proven'])
        answer['item_decisions'].pop()
        with self.assertRaisesRegex(ValueError, 'UNANSWERED_ITEMS'):
            successor.summarize_incorporated_answer(request=result,
                raw_output=json.dumps(answer))
