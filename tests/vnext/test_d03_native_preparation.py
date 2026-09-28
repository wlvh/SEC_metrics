"""D03's future native input is complete and never revives old fact credit."""
from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import d03_native_preparation as native
from vnext.normal_source_authority import ROOT


class D03NativePreparationTest(unittest.TestCase):
    def test_saved_jpm_source_uses_anchor_successor_without_losing_groups(self):
        self.enterContext(original_sources_only())
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')):
            prepared = native.prepare_native_input(company_id='jpmorgan_chase')
        groups = prepared['groups']
        self.assertEqual('D03_NATIVE_PREPARATION_V1', prepared['record_type'])
        self.assertEqual(prepared['complete_source_unit_ids'], [
            unit_id for group in groups for unit_id in group['unit_ids']])
        self.assertEqual(len(groups), len(prepared['group_mapping']))
        self.assertTrue(all('original_request' not in group for group in groups))
        self.assertTrue(any(group['source_anchor_successor'] for group in groups))
        self.assertTrue(all(group['effective_request_id'] ==
                            group['original_request_id'] for group in groups
                            if not group['source_anchor_successor']))
        for group in groups:
            if group['source_anchor_successor']:
                self.assertNotIn('source_statement_facts',
                                 group['effective_request'])
                self.assertNotEqual(group['original_request_id'],
                                    group['effective_request_id'])
        self.assertFalse(prepared['provider_request_sent'])
        self.assertFalse(prepared['native_result_created'])
        self.assertFalse(prepared['production_authorized'])

    def test_successor_cannot_drop_original_units_or_required_items(self):
        source = {'semantic_source_id': 'sha256:' + 'a'*64,
                  'required_unit_ids': ['unit-0', 'unit-1']}
        originals = [
            {'request_id': 'original-0', 'source_id': source['semantic_source_id'],
             'company_id': 'jpmorgan_chase', 'units': [{'unit_id': 'unit-0'}],
             'required_candidate_assessments': [{'unit_id': 'unit-0'}],
             'source_statement_facts': [{'status': 'SOURCE_REPORTED_FACT'}]},
            {'request_id': 'original-1', 'source_id': source['semantic_source_id'],
             'company_id': 'jpmorgan_chase', 'units': [{'unit_id': 'unit-1'}],
             'required_candidate_assessments': [], 'source_statement_facts': []},
        ]
        successor = deepcopy(originals[0])
        successor.pop('source_statement_facts')
        successor['request_id'] = 'successor-0'
        successor['source_fact_review_contract'] = {
            'version': native.ANCHOR_VERSION,
            'original_request_id': originals[0]['request_id']}
        with patch.object(native, 'prepare_regulatory_semantic_source',
                          return_value=source), patch.object(native,
                          'requests_from_source', return_value=originals), patch.object(
                          native, 'candidate_request', return_value=successor):
            prepared = native.prepare_native_input(company_id='jpmorgan_chase')
            self.assertEqual(['original-0', 'original-1'],
                [group['original_request_id'] for group in prepared['groups']])
            self.assertEqual(['successor-0', 'original-1'],
                [group['effective_request_id'] for group in prepared['groups']])
            bad = deepcopy(successor)
            bad['required_candidate_assessments'] = []
            with patch.object(native, 'candidate_request', return_value=bad):
                with self.assertRaisesRegex(ValueError,
                        'D03_NATIVE_PREPARATION_EFFECTIVE_REQUEST_CHANGED'):
                    native.prepare_native_input(company_id='jpmorgan_chase')
            bad = deepcopy(successor)
            bad['source_fact_review_contract']['original_request_id'] = 'other-group'
            with patch.object(native, 'candidate_request', return_value=bad):
                with self.assertRaisesRegex(ValueError,
                        'D03_NATIVE_PREPARATION_EFFECTIVE_REQUEST_CHANGED'):
                    native.prepare_native_input(company_id='jpmorgan_chase')
            with patch.object(native, 'requests_from_source',
                              return_value=originals[:1]):
                with self.assertRaisesRegex(ValueError,
                        'D03_NATIVE_PREPARATION_SOURCE_PARTITION_CHANGED'):
                    native.prepare_native_input(company_id='jpmorgan_chase')
            bad = deepcopy(successor)
            bad['units'] = []
            with patch.object(native, 'candidate_request', return_value=bad):
                with self.assertRaisesRegex(ValueError,
                        'D03_NATIVE_PREPARATION_EFFECTIVE_REQUEST_CHANGED'):
                    native.prepare_native_input(company_id='jpmorgan_chase')
        with self.assertRaisesRegex(ValueError,
                'D03_NATIVE_PREPARATION_CODE_ROOT_CHANGED'):
            native.prepare_native_input(company_id='jpmorgan_chase',
                                        repo_root=ROOT.parent)


if __name__ == '__main__':
    unittest.main()
