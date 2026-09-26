"""Bounded offline B13 scan/adjudication candidate; no provider or native credit."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tests.vnext.test_capacity_reference_contract import fixture
from vnext.canonical import canonical_json_bytes, content_hash
from vnext.capacity_reference_contract import (SCANNED_VERSION,
    restore_base_request, upgrade_request)
from vnext.capacity_semantic_review import validate_response
from vnext.capacity_two_stage import (
    build_scan_acceptance, interpretation_request, scan_request,
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
        from vnext.capacity_two_stage import restore_prior_interpretation_request
        self.assertEqual(second['source_reference_contract']['version'], SCANNED_VERSION)
        self.assertEqual(restore_prior_interpretation_request(second), self.request)
        self.assertEqual(restore_base_request(second), restore_base_request(self.request))
        from vnext.native_unit_index import validate_request_partition
        self.assertEqual(validate_request_partition(self.source, [second]), [SCANNED_VERSION])
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
        self.assertEqual(result['original_validator_result']['request_id'], second['request_id'])
        self.assertEqual(result['original_validator_result']['findings'][0]['kind'],
                         'CAPACITY_QUALITATIVE')

    def test_scanned_nonrequired_sales_can_be_correctly_excluded(self):
        sales = next(block for unit in self.source['units']
                     for block in unit['payload']['blocks'] if 'sold worldwide' in block['text'])
        ref = 'B' + str(sales['block_index'])
        scan_response = {**self.scan_response, 'candidate_refs': [ref]}
        scan_raw = canonical_json_bytes(value=scan_response)
        scan_result = validate_scan(request=self.request,
            scan_request_value=self.scan, raw_response=scan_raw)
        second = interpretation_request(request=self.request,
            scan_result=scan_result, scan_raw_response=scan_raw)
        response = deepcopy(self.interpretation_response)
        response['findings'] = [['sales_or_shipments', 0, 0, [ref],
                                 'Products sold are not actual factory output.']]
        raw = canonical_json_bytes(value=response)
        with self.assertRaisesRegex(ValueError, 'B13_V4_NONREQUIRED_BACKGROUND_FINDING'):
            validate_response(request=self.request, raw_response=raw, source=self.source)
        result = validate_interpretation(request=self.request,
            scan_result=scan_result, scan_raw_response=scan_raw,
            interpretation=second, raw_response=raw, source=self.source)
        self.assertEqual(result['original_validator_result']['unresolved'], [])
        self.assertEqual(result['original_validator_result']['request_id'], second['request_id'])
        self.assertEqual(result['original_validator_result']['findings'][0]['kind'],
                         'SALES_OR_SHIPMENTS')
        from vnext.capacity_native_assessment import build_acceptance
        with self.assertRaisesRegex(ValueError, 'SCAN_EXECUTION_PROOF_REQUIRED'):
            build_acceptance(prepared=SimpleNamespace(request_bytes=canonical_json_bytes(value=second)),
                             plan={}, response_body=raw)
        from vnext.continuous_semantic_calls import (
            execute_capacity_assessment, execute_capacity_interpretation,
            execute_capacity_scan)
        with self.assertRaisesRegex(ValueError, 'TWO_STAGE_EXECUTION_PROOF_REQUIRED'):
            execute_capacity_assessment(prepared=SimpleNamespace(
                request_bytes=canonical_json_bytes(value=second)),
                ledger=SimpleNamespace(live=True))
        with self.assertRaisesRegex(ValueError, 'TWO_STAGE_LIVE_EXECUTION_NOT_AUTHORIZED'):
            execute_capacity_interpretation(prepared=SimpleNamespace(
                request_bytes=canonical_json_bytes(value=second)),
                ledger=SimpleNamespace(live=True))
        with self.assertRaisesRegex(ValueError, 'TWO_STAGE_LIVE_EXECUTION_NOT_AUTHORIZED'):
            execute_capacity_scan(prepared=SimpleNamespace(
                request_bytes=canonical_json_bytes(value=self.scan)),
                ledger=SimpleNamespace(live=True))

    def test_scanned_physical_capacity_cannot_be_discarded_as_other_context(self):
        second = interpretation_request(request=self.request,
            scan_result=self.scan_result, scan_raw_response=self.scan_raw)
        books = second['response_protocol']['classification_codebooks']
        for kind, subject, timing in (
            ('other_context', 'TARGET_REGISTRANT', 'CURRENT_REPORT'),
            ('other_context', 'OTHER_ENTITY', 'CURRENT_REPORT'),
            ('other_entity', 'OTHER_ENTITY', 'CURRENT_REPORT'),
            ('other_context', 'TARGET_REGISTRANT', 'HISTORICAL'),
        ):
            answer = deepcopy(self.interpretation_response)
            answer['findings'][0][0] = kind
            answer['findings'][0][1] = books['subject'].index(subject)
            answer['findings'][0][2] = books['timing'].index(timing)
            with self.subTest(kind=kind, subject=subject, timing=timing), \
                 self.assertRaisesRegex(ValueError,
                     'B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW'):
                validate_interpretation(request=self.request,
                    scan_result=self.scan_result, scan_raw_response=self.scan_raw,
                    interpretation=second,
                    raw_response=canonical_json_bytes(value=answer), source=self.source)

    def test_genuine_other_entity_and_historical_capacity_not_newly_rejected(self):
        from tests.vnext.test_capacity_utilization_source import quantity_source
        from vnext.capacity_program_roles import program_source
        from vnext.capacity_semantic_review import requests_from_source
        from vnext.capacity_two_stage import _direct_current_target_capacity
        cases = (
            ('<p>A supplier has manufacturing capacity for its own products.</p>',
             'other_entity', 'OTHER_ENTITY', 'CURRENT_REPORT'),
            ('<p>Our contract manufacturers previously had limited output; '
             'a supplier has manufacturing capacity for its own products.</p>',
             'other_entity', 'OTHER_ENTITY', 'CURRENT_REPORT'),
            ('<p>In fiscal 2023, our contract manufacturers had production '
             'capacity for anticipated demand.</p>',
             'historical_statement', 'TARGET_REGISTRANT', 'HISTORICAL'),
            ('<p>Our contract manufacturers used to have production '
             'capacity for anticipated demand.</p>',
             'historical_statement', 'TARGET_REGISTRANT', 'HISTORICAL'),
        )
        for html, kind, subject, timing in cases:
            with self.subTest(kind=kind):
                source, _ = quantity_source(html)
                source = program_source(source)
                base = requests_from_source(source)[0]
                prior = upgrade_request(base, compact=True, role_labels=True,
                                        relevance_scope=True)
                ref = 'B' + str(source['units'][0]['payload']['blocks'][0]['block_index'])
                scan = scan_request(prior)
                raw_scan = canonical_json_bytes(value={
                    'units_reviewed': list(range(len(prior['units']))),
                    'candidate_refs': [ref], 'unresolved_refs': []})
                result = validate_scan(request=prior, scan_request_value=scan,
                                       raw_response=raw_scan)
                second = interpretation_request(request=prior,
                    scan_result=result, scan_raw_response=raw_scan)
                books = second['response_protocol']['classification_codebooks']
                response = {'units': [{'unit_index': index, 'reviewed': True,
                    'unresolved': [], 'calculation_limits': []}
                    for index in range(len(prior['units']))],
                    'findings': [[kind, books['subject'].index(subject),
                        books['timing'].index(timing), [ref],
                        'The source states this capacity with the stated subject and period.']]}
                if kind == 'historical_statement':
                    self.assertFalse(_direct_current_target_capacity(
                        source['units'][0]['payload']['blocks'][0]['text'], 2025))
                    if 'used to have' in html:
                        checked = validate_interpretation(request=prior,
                            scan_result=result, scan_raw_response=raw_scan,
                            interpretation=second,
                            raw_response=canonical_json_bytes(value=response), source=source)
                        self.assertEqual(checked['original_validator_result']['unresolved'], [])
                    else:
                        # The old source validator may independently retain
                        # an unresolved historical relation.
                        with self.assertRaisesRegex(ValueError, 'B13_TWO_STAGE_UNRESOLVED'):
                            validate_interpretation(request=prior,
                                scan_result=result, scan_raw_response=raw_scan,
                                interpretation=second,
                                raw_response=canonical_json_bytes(value=response), source=source)
                else:
                    checked = validate_interpretation(request=prior,
                        scan_result=result, scan_raw_response=raw_scan,
                        interpretation=second,
                        raw_response=canonical_json_bytes(value=response), source=source)
                    self.assertEqual(checked['original_validator_result']['unresolved'], [])

    def test_historical_comparison_does_not_hide_current_contract_capacity(self):
        from tests.vnext.test_capacity_utilization_source import quantity_source
        from vnext.capacity_program_roles import program_source
        from vnext.capacity_semantic_review import requests_from_source
        statements = (
            'Unlike prior years, our contract manufacturers have sufficient '
            'production capacity for anticipated demand.',
            'Unlike fiscal 2023, our contract manufacturers have sufficient '
            'production capacity for anticipated demand.',
            'Our contract manufacturers previously had limited output, but '
            'they have sufficient production capacity for anticipated demand.',
        )
        for statement in statements:
            with self.subTest(statement=statement):
                source, _ = quantity_source('<p>' + statement + '</p>')
                source = program_source(source)
                prior = upgrade_request(requests_from_source(source)[0],
                    compact=True, role_labels=True, relevance_scope=True)
                ref = 'B' + str(source['units'][0]['payload']['blocks'][0]['block_index'])
                scan = scan_request(prior)
                raw_scan = canonical_json_bytes(value={
                    'units_reviewed': list(range(len(prior['units']))),
                    'candidate_refs': [ref], 'unresolved_refs': []})
                result = validate_scan(request=prior, scan_request_value=scan,
                                       raw_response=raw_scan)
                second = interpretation_request(request=prior,
                    scan_result=result, scan_raw_response=raw_scan)
                books = second['response_protocol']['classification_codebooks']
                for kind, subject, timing in (
                    ('other_context', 'OTHER_ENTITY', 'CURRENT_REPORT'),
                    ('other_entity', 'OTHER_ENTITY', 'CURRENT_REPORT'),
                    ('other_context', 'TARGET_REGISTRANT', 'HISTORICAL'),
                ):
                    answer = {'units': [{'unit_index': index, 'reviewed': True,
                        'unresolved': [], 'calculation_limits': []}
                        for index in range(len(prior['units']))],
                        'findings': [[kind, books['subject'].index(subject),
                            books['timing'].index(timing), [ref],
                            'The sentence is merely background for this metric.']]}
                    with self.subTest(kind=kind, subject=subject, timing=timing), \
                         self.assertRaisesRegex(ValueError,
                             'B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW'):
                        validate_interpretation(request=prior,
                            scan_result=result, scan_raw_response=raw_scan,
                            interpretation=second,
                            raw_response=canonical_json_bytes(value=answer), source=source)

    def test_scanned_uncertainty_cannot_be_silently_promoted(self):
        scan_response = {**self.scan_response, 'unresolved_refs': [self.ref]}
        scan_raw = canonical_json_bytes(value=scan_response)
        scan_result = validate_scan(request=self.request,
            scan_request_value=self.scan, raw_response=scan_raw)
        second = interpretation_request(request=self.request,
            scan_result=scan_result, scan_raw_response=scan_raw)
        with self.assertRaisesRegex(ValueError, 'SCAN_UNRESOLVED_LOST'):
            validate_interpretation(request=self.request, scan_result=scan_result,
                scan_raw_response=scan_raw, interpretation=second,
                raw_response=canonical_json_bytes(value=self.interpretation_response),
                source=self.source)

    def test_program_proved_physical_quantity_cannot_be_scanned_as_background(self):
        from tests.vnext.test_capacity_utilization_source import quantity_source
        from vnext.capacity_program_roles import program_source
        from vnext.capacity_semantic_review import requests_from_source
        source, _ = quantity_source(
            '<p>For fiscal year 2025, we produced 80 widgets worldwide.</p>')
        source = program_source(source)
        base = requests_from_source(source)[0]
        request = upgrade_request(base, compact=True, role_labels=True,
                                  relevance_scope=True)
        owned = request['program_quantity_contract']['verified_quantity_roles']
        self.assertEqual(len(owned), 1)
        ref = 'B' + str(owned[0]['source_index'])
        scan = scan_request(request)
        self.assertIn(ref, scan['scan_contract']['program_accounted_refs'])
        empty = {'units_reviewed': list(range(len(request['units']))),
                 'candidate_refs': [], 'unresolved_refs': []}
        validate_scan(request=request, scan_request_value=scan,
            raw_response=canonical_json_bytes(value=empty))
        with self.assertRaisesRegex(ValueError, 'PROGRAM_OWNED_DUPLICATED'):
            validate_scan(request=request, scan_request_value=scan,
                raw_response=canonical_json_bytes(value={**empty,
                    'candidate_refs': [ref]}))

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
        empty_raw = canonical_json_bytes(value={**self.scan_response,
            'candidate_refs': []})
        second = interpretation_request(request=self.request, scan_result=result,
            scan_raw_response=empty_raw)
        missed = deepcopy(self.interpretation_response)
        missed['findings'] = []
        missed['units'][self.owner]['unresolved'] = ['SCAN_OMISSION:' + self.ref]
        with self.assertRaisesRegex(ValueError, 'B13_TWO_STAGE_UNRESOLVED'):
            validate_interpretation(request=self.request, scan_result=result,
                scan_raw_response=empty_raw, interpretation=second,
                raw_response=canonical_json_bytes(value=missed), source=self.source)

    def test_scan_stage_receipt_has_no_metric_result_credit(self):
        plan = {key: content_hash(value=key) for key in
            ('selected_representation_hash', 'ai_invocation_plan_id',
             'source_identity_hash', 'task_contract_hash')}
        draft = build_scan_acceptance(prepared=SimpleNamespace(
            source_bytes=canonical_json_bytes(value=self.source),
            request_bytes=canonical_json_bytes(value=self.scan)),
            plan=plan, response_body=self.scan_raw)
        scan = draft['candidate_record']['selected']['source_scan']
        self.assertFalse(scan['native_credit'])
        self.assertFalse(scan['absence_established'])
        self.assertFalse(scan['model_relevance_proven'])
        self.assertEqual(draft['evidence_status'], 'PASS')
        self.assertNotIn('result', draft['candidate_record']['selected'])

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
        from vnext.capacity_two_stage import _reference_inventory
        other_ref = next(ref for ref in _reference_inventory(self.request)
                         if ref != self.ref)
        outside['findings'][0][3] = [other_ref]
        with self.assertRaisesRegex(ValueError, 'FINDING_OUTSIDE_SCAN'):
            validate_response(request=second,
                raw_response=canonical_json_bytes(value=outside), source=self.source)

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
