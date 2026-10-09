"""A full recorded D03 set remains raw-byte evidence, never native credit."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.continuous_request_context import FORMAT_VERSION
from vnext.d03_recorded_response_set import (
    _checked_rows, record_offline_set, replay_offline_set)
from vnext.normal_source_authority import ROOT
from vnext.r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source)


class D03RecordedResponseSetTest(unittest.TestCase):
    def test_real_anchor_group_uses_explicit_successor_request(self):
        from vnext.regulatory_fact_review import candidate_request
        self.enterContext(original_sources_only())
        source = prepare_regulatory_semantic_source(repo_root=ROOT,
            company_id='jpmorgan_chase',
            request_context_format=FORMAT_VERSION)
        original = next(request for request in requests_from_source(source)
            if request['source_statement_facts'])
        # The source and original request above are authentic; avoid reparsing
        # the multi-MB annual report solely to make a recorded response. The
        # actual _checked_rows call below still authenticates on its own.
        with patch('vnext.regulatory_fact_review._authenticated_original'):
            successor = candidate_request(original, source=source)
        anchor = successor['source_fact_candidates'][0]
        units = []
        for unit in original['units']:
            owns = unit['unit_id'] == anchor['unit_id']
            required = [row['source_index'] for row in
                original['required_candidate_assessments']
                if row['unit_id'] == unit['unit_id']
                and row['source_index'] != anchor['block_index']]
            units.append({'unit_id': unit['unit_id'], 'reviewed': True,
                'findings': ([{'kind': 'CONDITIONAL_OR_BOILERPLATE',
                    'subject': 'TARGET_REGISTRANT', 'event_dates': [],
                    'reported_status': 'CONDITIONAL',
                    'evidence': [{'kind': 'VISIBLE_BLOCK',
                                  'source_index': anchor['block_index']}],
                    'reason': 'Recorded proposal; source relation remains unresolved.'}]
                    if owns else []),
                'context_only_source_indices': required,
                'unresolved': ['Recorded proposal is not a business conclusion.']})
        raw = (json.dumps({'request_id': successor['request_id'],
            'units': units, 'candidate_reviews': [{
                'candidate_id': anchor['candidate_id'],
                'unit_id': anchor['unit_id'], 'finding_indices': [0]}]},
            ensure_ascii=False) + '\n').encode()
        rows = _checked_rows(source, [original], {original['request_id']: raw})
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]['source_anchor_successor'])
        self.assertEqual(original['request_id'], rows[0]['original_request_id'])
        self.assertEqual(successor['request_id'], rows[0]['effective_request_id'])
        self.assertGreater(rows[0]['unresolved_count'], 0)

    def test_complete_original_source_set_and_exact_raw_bytes_survive_cold_read(self):
        self.enterContext(original_sources_only())
        source = prepare_regulatory_semantic_source(repo_root=ROOT,
            company_id='marriott_international',
            request_context_format=FORMAT_VERSION)
        requests = requests_from_source(source)
        self.assertGreater(len(requests), 1)
        responses = {}
        for request in requests:
            units = []
            for unit in request['units']:
                required = [row['source_index'] for row in
                    request['required_candidate_assessments']
                    if row['unit_id'] == unit['unit_id']]
                units.append({'unit_id': unit['unit_id'], 'reviewed': True,
                    'findings': [], 'context_only_source_indices': required,
                    'unresolved': ['Recorded ; source interpretation not proven.']})
            responses[request['request_id']] = (
                json.dumps({'request_id': request['request_id'], 'units': units},
                           ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()/'packet'
            missing = dict(responses)
            missing.pop(requests[-1]['request_id'])
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_SET_MISSING_EXTRA_OR_NONBYTE_RESPONSE'):
                record_offline_set(output_root=root, source=source,
                                   responses_by_original_id=missing)
            self.assertFalse(root.exists())
            saved = record_offline_set(output_root=root, source=source,
                responses_by_original_id=responses)
            self.assertEqual([0, 0, 0], saved['calls'])
            self.assertFalse(saved['native_result_created'])
            self.assertEqual(len(requests), saved['request_count'])
            self.assertEqual(len(requests), saved['unresolved_request_count'])
            packet = json.loads((root/'packet.json').read_bytes())
            self.assertEqual('RECORDED_TEST_ONLY',
                             packet['provider_execution_credit'])
            self.assertFalse(packet['production_authorized'])
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_SET_EXTERNAL_EXPECTED_ID_REQUIRED'):
                replay_offline_set(packet_root=root, expected_packet_id=None)
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_SET_IDENTITY_OR_CREDIT_CHANGED'):
                replay_offline_set(packet_root=root,
                    expected_packet_id='sha256:' + '0'*64)
            checked = replay_offline_set(packet_root=root,
                expected_packet_id=saved['packet_id'])
            self.assertEqual(responses, checked['raw_response_bytes'])
            self.assertTrue(any(b'\xcd\xbe' in raw
                                for raw in checked['raw_response_bytes'].values()))
            self.assertFalse(checked['native_result_created'])
            self.assertEqual([0, 0, 0], checked['calls'])
            path = root/packet['rows'][0]['response_file']
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_SET_FILE_CHANGED'):
                replay_offline_set(packet_root=root,
                    expected_packet_id=saved['packet_id'])
            path.write_bytes(original)
            (root/'responses'/'extra.bin').write_bytes(b'forged')
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_SET_RESPONSE_CENSUS_CHANGED'):
                replay_offline_set(packet_root=root,
                    expected_packet_id=saved['packet_id'])


if __name__ == '__main__':
    unittest.main()
