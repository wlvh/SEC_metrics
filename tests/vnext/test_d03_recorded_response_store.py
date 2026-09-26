"""D03 recorded response bytes survive storage without gaining Run credit."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import content_hash
from vnext.canonical import strict_json_file
from vnext.d03_recorded_response_store import (
    record_offline_response, replay_offline_response)
from vnext.normal_source_authority import ROOT
from vnext.r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source)


class D03RecordedResponseStoreTest(unittest.TestCase):
    def test_real_ledger_root_cannot_hold_an_offline_packet(self):
        budget = strict_json_file(path=ROOT/
            'config/issue28_continuous_calls_v1.json')['budget_root']
        with self.assertRaisesRegex(ValueError,
                'D03_RECORDED_PACKET_LIVE_LEDGER_FORBIDDEN'):
            replay_offline_response(packet_root=Path(budget)/'forged-d03-recording')

    def test_original_response_bytes_and_unresolved_survive_cold_replay(self):
        self.enterContext(original_sources_only())
        source = prepare_regulatory_semantic_source(
            repo_root=ROOT, company_id='jpmorgan_chase')
        original = next(request for request in requests_from_source(source)
            if any(fact['status'] == 'SOURCE_REPORTED_FACT'
                   for fact in request['source_statement_facts']))
        fact = next(fact for fact in original['source_statement_facts']
                    if fact['status'] == 'SOURCE_REPORTED_FACT')
        # The response is a recorded test answer, not a provider execution.
        unit = original['units'][0]
        response = {'request_id': None, 'units': [{
            'unit_id': unit['unit_id'], 'reviewed': True,
            'findings': [{'kind': 'CONDITIONAL_OR_BOILERPLATE',
                          'subject': 'TARGET_REGISTRANT',
                          'reported_status': 'CONDITIONAL', 'event_dates': [],
                          'evidence': [{'kind': 'VISIBLE_BLOCK',
                                        'source_index': fact['block_index']}],
                          'reason': 'Recorded context \u037e remains unresolved.'}],
            'context_only_source_indices': [row['source_index']
                for row in original['required_candidate_assessments']
                if row['source_index'] != fact['block_index']],
            'unresolved': ['The actual subject and time are not established.']}],
            'candidate_reviews': []}
        from vnext.regulatory_fact_review import candidate_request
        request = candidate_request(original, source=source)
        response['request_id'] = request['request_id']
        response['candidate_reviews'] = [{
            'candidate_id': request['source_fact_candidates'][0]['candidate_id'],
            'unit_id': unit['unit_id'], 'finding_indices': [0]}]
        raw = (json.dumps(response, ensure_ascii=False, indent=2)+'\n').encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()/'packet'
            saved = record_offline_response(output_root=root, source=source,
                original_request=original, raw_response=raw)
            self.assertEqual(raw, (root/'raw-response.bin').read_bytes())
            self.assertFalse(saved['native_result_created'])
            self.assertEqual([0, 0, 0], saved['calls'])
            read = replay_offline_response(packet_root=root)
            self.assertEqual(raw, read['raw_response_bytes'])
            self.assertTrue(read['checked']['unresolved'])
            self.assertFalse(read['native_result_created'])
            if os.environ.get('D03_RECORDED_PACKET_COPY'):
                destination = Path(os.environ['D03_RECORDED_PACKET_COPY'])
                self.assertTrue(destination.is_absolute())
                self.assertFalse(destination.exists())
                shutil.copytree(root, destination)
            original_packet = (root/'packet.json').read_bytes()
            changed = json.loads(original_packet)
            changed['provider_execution_credit'] = 'LIVE'
            changed['packet_id'] = content_hash(value={key: value
                for key, value in changed.items() if key != 'packet_id'})
            (root/'packet.json').write_text(json.dumps(changed)+'\n')
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_PACKET_IDENTITY_OR_CREDIT_CHANGED'):
                replay_offline_response(packet_root=root)
            (root/'packet.json').write_bytes(original_packet)
            (root/'raw-response.bin').write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_PACKET_FILE_CHANGED'):
                replay_offline_response(packet_root=root)
            incomplete = Path(temporary).resolve()/'incomplete'
            incomplete.mkdir()
            (incomplete/'raw-response.bin').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,
                    'D03_RECORDED_PACKET_INCOMPLETE_OR_EXTRA_FILE'):
                replay_offline_response(packet_root=incomplete)


if __name__ == '__main__':
    unittest.main()
