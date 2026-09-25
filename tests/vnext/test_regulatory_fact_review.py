"""D03 source anchors remain mechanical in the explicit offline successor."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.normal_source_authority import ROOT
from vnext.regulatory_fact_review import (_candidate_uncertainty,
    candidate_request, validate_candidate_response)
from vnext.r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source,
    validate_response)


class RegulatoryFactReviewTest(unittest.TestCase):
    def test_jpm_anchor_is_reviewed_without_old_status_override(self):
        self.enterContext(original_sources_only())
        source = prepare_regulatory_semantic_source(
            repo_root=ROOT, company_id='jpmorgan_chase')
        originals = requests_from_source(source)
        original = next(request for request in originals
            if any(fact['status'] == 'SOURCE_REPORTED_FACT'
                   for fact in request['source_statement_facts']))
        fact = next(fact for fact in original['source_statement_facts']
            if fact['status'] == 'SOURCE_REPORTED_FACT')
        successor = candidate_request(original, source=source)
        # The authentic saved-source reprepare above and forged-original check
        # below exercise that boundary. Reuse the proven source for the small
        # response-shape matrix instead of reparsing the annual report each time.
        auth = patch('vnext.regulatory_fact_review._authenticated_original')
        auth.start()
        self.addCleanup(auth.stop)
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
            'unresolved': ['Other candidate language is not settled in this test.']}],
            'candidate_reviews': [{'candidate_id': successor['source_fact_candidates'][0]['candidate_id'],
                                   'unit_id': unit['unit_id'], 'finding_indices': [0]}]}
        with self.assertRaisesRegex(ValueError,
                                    'D03_AFFIRMATIVE_AGGREGATE_FACT_CLASSIFICATION_CONFLICT'):
            validate_response(request=original,
                raw_response=canonical_json_bytes(value={
                    'request_id': original['request_id'], 'units': response['units']}))
        response['request_id'] = successor['request_id']
        raw = canonical_json_bytes(value=response)
        checked = validate_candidate_response(original_request=original, source=source,
            request=successor, raw_response=raw)
        self.assertFalse(checked['source_fact_current_status_proven_by_program'])
        self.assertFalse(checked['native_result_created'])
        self.assertFalse(checked['raw_provider_response_preserved_separately'])
        self.assertEqual(checked['provider_response'], response)
        self.assertEqual(checked['provider_response_raw_sha256'],
                         sha256_bytes(content=raw))
        self.assertEqual(len(checked['source_fact_candidate_review']), 1)
        self.assertTrue(checked['unresolved'])
        other = deepcopy(response)
        other['units'][0]['findings'][0].update(
            kind='OTHER_ENTITY', subject='OTHER_ENTITY',
            reported_status='NOT_STATED')
        other_checked = validate_candidate_response(original_request=original, source=source,
            request=successor, raw_response=canonical_json_bytes(value=other))
        self.assertEqual(len(other_checked['source_fact_candidate_review']), 1)
        missing = deepcopy(response)
        missing['units'][0]['findings'] = []
        missing['units'][0]['context_only_source_indices'].append(fact['block_index'])
        with self.assertRaisesRegex(ValueError, 'D03_ANCHOR_CANNOT_BE_CONTEXT_ONLY'):
            validate_candidate_response(original_request=original, source=source,
                request=successor, raw_response=canonical_json_bytes(value=missing))
        changed = deepcopy(successor)
        changed['source_fact_candidates'][0]['raw_span_sha256'] = 'sha256:' + '0'*64
        changed['request_id'] = content_hash(value={key: value for key, value in
            changed.items() if key != 'request_id'})
        with self.assertRaisesRegex(ValueError, 'D03_ANCHOR_REQUEST_NOT_SOURCE_BOUND'):
            validate_candidate_response(original_request=original, source=source,
                request=changed, raw_response=canonical_json_bytes(value=response))
        conflict = deepcopy(response)
        conflict['units'][0]['findings'][0].update(
            kind='CURRENT_REGULATORY_ACTION', subject='TARGET_REGISTRANT',
            reported_status='ONGOING_AS_REPORTED')
        conflict['units'][0]['findings'].append(deepcopy(other['units'][0]['findings'][0]))
        conflict['candidate_reviews'][0]['finding_indices'] = [0, 1]
        conflict_checked = validate_candidate_response(original_request=original,
            source=source, request=successor,
            raw_response=canonical_json_bytes(value=conflict))
        self.assertEqual(len(conflict_checked['source_fact_candidate_review']), 1)
        self.assertTrue(conflict_checked['unresolved'])
        unassigned = deepcopy(conflict)
        unassigned['candidate_reviews'][0]['finding_indices'] = [0]
        with self.assertRaisesRegex(ValueError, 'D03_ANCHOR_CITED_FINDING_UNASSIGNED'):
            validate_candidate_response(original_request=original, source=source,
                request=successor, raw_response=canonical_json_bytes(value=unassigned))
        forged = deepcopy(original)
        forged['source_statement_facts'][0]['source_reference_id'] = 'forged-source-reference'
        forged['source_statement_facts'][0]['subject_binding'] = 'forged-subject'
        forged['request_id'] = content_hash(value={key: value for key, value in
            forged.items() if key != 'request_id'})
        auth.stop()
        with self.assertRaisesRegex(ValueError, 'D03_ANCHOR_AUTHENTIC_ORIGINAL_REQUIRED'):
            candidate_request(forged, source=source)

    def test_same_block_candidates_cannot_split_conflict_into_false_resolution(self):
        anchors = [{'candidate_id': 'first', 'unit_id': 'unit', 'block_index': 7},
                   {'candidate_id': 'second', 'unit_id': 'unit', 'block_index': 7}]
        reviews = {'first': {'finding_indices': [0]},
                   'second': {'finding_indices': [1]}}
        units = {'unit': {'findings': [
            {'kind': 'CURRENT_REGULATORY_ACTION',
             'reported_status': 'ONGOING_AS_REPORTED', 'subject': 'TARGET_REGISTRANT'},
            {'kind': 'OTHER_ENTITY', 'reported_status': 'NOT_STATED',
             'subject': 'OTHER_ENTITY'}]}}
        unresolved = _candidate_uncertainty(anchors=anchors,
            reviews=reviews, units=units)
        self.assertEqual({row['candidate_id'] for row in unresolved},
                         {'first', 'second'})
        self.assertEqual({row['reason'] for row in unresolved},
                         {'MULTIPLE_CANDIDATES_SAME_BLOCK_REQUIRES_SEMANTIC_REVIEW'})
