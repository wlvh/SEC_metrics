"""Bounded offline B13 scan/adjudication candidate; no provider or native credit."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from tests.vnext.test_capacity_reference_contract import fixture
from vnext.canonical import canonical_json_bytes, content_hash
from vnext.capacity_reference_contract import upgrade_request
from vnext.capacity_two_stage import (
    interpretation_request, scan_request,
    validate_interpretation, validate_scan,
)


class CapacityTwoStageTest(unittest.TestCase):
    def setUp(self):
        self.source, base, response, self.owner = fixture()
        self.request = upgrade_request(base, compact=True, role_labels=True,
                                       relevance_scope=True)
        self.ref = 'B' + str(response['findings'][0]['evidence'][0]['source_index'])
        self.scan = scan_request(self.request)
        self.scan_response = {
            'units_reviewed': list(range(len(self.request['units']))),
            'candidate_refs': [self.ref], 'unresolved_refs': [],
        }
        self.scan_raw = canonical_json_bytes(value=self.scan_response)
        self.scan_result = validate_scan(
            request=self.request, scan_request_value=self.scan,
            raw_response=self.scan_raw)
        books = self.request['response_protocol']['classification_codebooks']
        self.interpretation_response = {
            'units': [{'unit_index': index, 'reviewed': True, 'unresolved': [],
                       'calculation_limits': []}
                      for index in range(len(self.request['units']))],
            'findings': [['physical_capacity_context',
                          books['subject'].index('TARGET_REGISTRANT'),
                          books['timing'].index('CURRENT_REPORT'),
                          [self.ref], 'Current contract manufacturing capacity is described.']],
        }

    def test_nonempty_two_stage_uses_complete_original_source_and_semantics(self):
        second = interpretation_request(request=self.request,
            scan_result=self.scan_result, scan_raw_response=self.scan_raw)
        self.assertEqual(self.scan['units'], self.request['units'])
        self.assertEqual(second['units'], self.request['units'])
        self.assertEqual(second['source_id'], self.request['source_id'])
        self.assertEqual(second['response_protocol'], self.request['response_protocol'])
        result = validate_interpretation(
            request=self.request, scan_result=self.scan_result,
            scan_raw_response=self.scan_raw,
            interpretation=second,
            raw_response=canonical_json_bytes(value=self.interpretation_response),
            source=self.source)
        self.assertFalse(result['native_credit'])
        self.assertFalse(result['model_accuracy_proven'])
        self.assertEqual(result['original_validator_result']['unresolved'], [])
        self.assertEqual(result['original_validator_result']['findings'][0]['kind'],
                         'CAPACITY_QUALITATIVE')

    def test_scan_rejects_omitted_units_wrong_refs_and_candidate_overflow(self):
        changes = [
            ({'units_reviewed': [self.owner]}, 'UNIT_CENSUS'),
            ({'units_reviewed': [False, *range(1, len(self.request['units']))]}, 'UNIT_CENSUS'),
            ({'candidate_refs': ['F' + self.ref[1:]]}, 'REFERENCE_INVALID'),
            ({'candidate_refs': [self.ref] * 2}, 'REFERENCE_INVALID'),
            ({'candidate_refs': [], 'unresolved_refs': [self.ref]}, 'UNRESOLVED'),
            ({'candidate_refs': ['B999999']}, 'REFERENCE_INVALID'),
        ]
        for change, reason in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, reason):
                validate_scan(request=self.request, scan_request_value=self.scan,
                    raw_response=canonical_json_bytes(value={**self.scan_response, **change}))
        decimal_index = {**self.scan_response,
            'units_reviewed': [0.0, *range(1, len(self.request['units']))]}
        with self.assertRaisesRegex(ValueError, 'UNIT_CENSUS'):
            validate_scan(request=self.request, scan_request_value=self.scan,
                raw_response=json.dumps(decimal_index).encode())
        # A structurally valid but too large candidate set must stop instead
        # of silently dropping references to meet the output budget.
        from vnext.capacity_two_stage import _reference_inventory
        inventory = list(_reference_inventory(self.request))
        self.assertGreaterEqual(len(inventory), 2)
        with patch('vnext.capacity_two_stage.MAX_CANDIDATE_REFS', 1), \
             self.assertRaisesRegex(ValueError, 'CANDIDATE_CAP_EXCEEDED'):
            validate_scan(request=self.request, scan_request_value=self.scan,
                raw_response=canonical_json_bytes(value={**self.scan_response,
                    'candidate_refs': inventory[:2]}))

    def test_required_candidate_cannot_disappear_between_stages(self):
        from vnext.capacity_reference_contract import restore_base_request
        base = deepcopy(restore_base_request(self.request))
        base['required_candidate_assessments'] = [{
            'unit_id': base['units'][self.owner]['unit_id'],
            'kind': 'VISIBLE_BLOCK', 'source_index': int(self.ref[1:]),
            'signals': ['CAPACITY_LANGUAGE']}]
        base['request_id'] = content_hash(value={k: v for k, v in base.items()
                                                   if k != 'request_id'})
        required = upgrade_request(base, compact=True, role_labels=True,
                                   relevance_scope=True)
        scan = scan_request(required)
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CANDIDATE_OMITTED'):
            validate_scan(request=required, scan_request_value=scan,
                raw_response=canonical_json_bytes(value={**self.scan_response,
                    'candidate_refs': []}))

    def test_empty_scan_is_only_a_shape_check_not_an_absence_result(self):
        result = validate_scan(request=self.request, scan_request_value=self.scan,
            raw_response=canonical_json_bytes(value={**self.scan_response,
                'candidate_refs': []}))
        self.assertFalse(result['model_relevance_proven'])
        self.assertFalse(result['absence_established'])
        self.assertFalse(result['native_credit'])

    def test_second_stage_rejects_unscanned_findings_and_missing_candidate(self):
        second = interpretation_request(request=self.request,
            scan_result=self.scan_result, scan_raw_response=self.scan_raw)
        absent = deepcopy(self.interpretation_response)
        absent['findings'] = []
        with self.assertRaisesRegex(ValueError, 'CANDIDATE_UNASSESSED'):
            validate_interpretation(request=self.request, scan_result=self.scan_result,
                scan_raw_response=self.scan_raw,
                interpretation=second, raw_response=canonical_json_bytes(value=absent),
                source=self.source)
        outside = deepcopy(self.interpretation_response)
        outside['findings'][0][3] = ['B999999']
        with self.assertRaisesRegex(ValueError, 'FINDING_OUTSIDE_SCAN'):
            validate_interpretation(request=self.request, scan_result=self.scan_result,
                scan_raw_response=self.scan_raw,
                interpretation=second, raw_response=canonical_json_bytes(value=outside),
                source=self.source)

    def test_no_rebinding_or_unverified_scan_result(self):
        changed = deepcopy(self.scan)
        changed['units'].pop()
        with self.assertRaisesRegex(ValueError, 'SCAN_REQUEST_CHANGED'):
            validate_scan(request=self.request, scan_request_value=changed,
                raw_response=canonical_json_bytes(value=self.scan_response))
        changed = deepcopy(self.scan_result)
        changed['response']['candidate_refs'] = []
        with self.assertRaisesRegex(ValueError, 'SCAN_RESULT_NOT_BOUND'):
            interpretation_request(request=self.request, scan_result=changed,
                                   scan_raw_response=self.scan_raw)
        from vnext.capacity_two_stage import _reference_inventory
        first_two = list(_reference_inventory(self.request))[:2]
        self.assertEqual(len(first_two), 2)
        changed = deepcopy(self.scan_result)
        changed['response']['candidate_refs'] = first_two
        changed['scan_result_id'] = content_hash(value={k: v for k, v in changed.items()
                                                 if k != 'scan_result_id'})
        with patch('vnext.capacity_two_stage.MAX_CANDIDATE_REFS', 1):
            with self.assertRaisesRegex(ValueError, 'SCAN_RESULT_NOT_BOUND'):
                interpretation_request(request=self.request, scan_result=changed,
                                       scan_raw_response=self.scan_raw)
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_CAP_EXCEEDED'):
                interpretation_request(request=self.request, scan_result=changed,
                    scan_raw_response=canonical_json_bytes(value={**self.scan_response,
                        'candidate_refs': first_two}))


if __name__ == '__main__':
    unittest.main()
