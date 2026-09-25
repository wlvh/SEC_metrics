"""D03 source anchors remain mechanical in the explicit offline successor."""
from copy import deepcopy
import unittest

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import canonical_json_bytes, content_hash
from vnext.normal_source_authority import ROOT
from vnext.regulatory_fact_review import candidate_request, validate_candidate_response
from vnext.r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source,
    validate_response)


class RegulatoryFactReviewTest(unittest.TestCase):
    def test_jpm_anchor_is_reviewed_without_old_status_override(self):
        with original_sources_only():
            source = prepare_regulatory_semantic_source(
                repo_root=ROOT, company_id='jpmorgan_chase')
            originals = requests_from_source(source)
        original = next(request for request in originals
            if any(fact['status'] == 'SOURCE_REPORTED_FACT'
                   for fact in request['source_statement_facts']))
        fact = next(fact for fact in original['source_statement_facts']
            if fact['status'] == 'SOURCE_REPORTED_FACT')
        successor = candidate_request(original)
        self.assertNotIn('source_statement_facts', successor)
        self.assertEqual(successor['units'], original['units'])
        self.assertEqual(successor['required_candidate_assessments'],
                         original['required_candidate_assessments'])
        self.assertEqual(successor['source_fact_candidates'][0]['block_index'],
                         fact['block_index'])
        self.assertNotIn('reported_time', successor['source_fact_candidates'][0])
        unit = original['units'][0]
        response = {'request_id': original['request_id'], 'units': [{
            'unit_id': unit['unit_id'], 'reviewed': True,
            'findings': [{'kind': 'CONDITIONAL_OR_BOILERPLATE',
                          'subject': 'TARGET_REGISTRANT',
                          'reported_status': 'CONDITIONAL', 'event_dates': [],
                          'evidence': [{'kind': 'VISIBLE_BLOCK',
                                        'source_index': fact['block_index']}],
                          'reason': 'A semantic classification proposal needing context review.'}],
            'context_only_source_indices': [row['source_index']
                for row in original['required_candidate_assessments']
                if row['source_index'] != fact['block_index']],
            'unresolved': ['Other candidate language is not settled in this test.']}]}
        with self.assertRaisesRegex(ValueError,
                                    'D03_AFFIRMATIVE_AGGREGATE_FACT_CLASSIFICATION_CONFLICT'):
            validate_response(request=original,
                raw_response=canonical_json_bytes(value=response))
        response['request_id'] = successor['request_id']
        checked = validate_candidate_response(original_request=original,
            request=successor, raw_response=canonical_json_bytes(value=response))
        self.assertFalse(checked['source_fact_current_status_proven_by_program'])
        self.assertFalse(checked['native_result_created'])
        self.assertEqual(len(checked['source_fact_candidate_review']), 1)
        self.assertTrue(checked['unresolved'])
        other = deepcopy(response)
        other['units'][0]['findings'][0].update(
            kind='OTHER_ENTITY', subject='OTHER_ENTITY',
            reported_status='NOT_STATED')
        other_checked = validate_candidate_response(original_request=original,
            request=successor, raw_response=canonical_json_bytes(value=other))
        self.assertEqual(len(other_checked['source_fact_candidate_review']), 1)
        missing = deepcopy(response)
        missing['units'][0]['findings'] = []
        missing['units'][0]['context_only_source_indices'].append(fact['block_index'])
        with self.assertRaisesRegex(ValueError, 'D03_ANCHOR_CANNOT_BE_CONTEXT_ONLY'):
            validate_candidate_response(original_request=original,
                request=successor, raw_response=canonical_json_bytes(value=missing))
        changed = deepcopy(successor)
        changed['source_fact_candidates'][0]['raw_span_sha256'] = 'sha256:' + '0'*64
        changed['request_id'] = content_hash(value={key: value for key, value in
            changed.items() if key != 'request_id'})
        with self.assertRaisesRegex(ValueError, 'D03_ANCHOR_REQUEST_NOT_SOURCE_BOUND'):
            validate_candidate_response(original_request=original,
                request=changed, raw_response=canonical_json_bytes(value=response))
