"""D04 current statements, literal source roles and diagnostic separation."""
from copy import deepcopy
import unittest

from tests.vnext.test_capacity_semantic_review import source_packet
from vnext.canonical import content_hash
from vnext.r6_semantic_source import _seal_unit, _bytes
from vnext.d04_native_assessment import native_source, requests_from_source, validate_response


def request_for(text, quoted=False):
    source = source_packet(); source.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04')
    old = source['units'][0]; payload = deepcopy(old['payload'])
    payload['blocks'][0].update(text=text, html_quotation_context=quoted)
    unit = _seal_unit(old['document_id'], 'VISIBLE_TEXT', payload, 0)
    source.update(units=[unit], required_unit_ids=[unit['unit_id']])
    source['documents'][0].update(language_candidate_block_indices=[7], native_candidate_ordinals=[])
    source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
    return requests_from_source(native_source(source))[0]


def response_for(request, kind='DOUBT_DISCLOSED', timing='CURRENT_REPORT'):
    return {'request_id': request['request_id'], 'units': [{
        'unit_id': request['units'][0]['unit_id'], 'reviewed': True, 'unresolved': [], 'findings': [{
            'kind': kind, 'timing': timing, 'subject': 'TARGET_REGISTRANT',
            'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': 7}],
            'reason': 'Recorded classification for the supplied source statement.'}]}]}


class D04NativeProtocolTest(unittest.TestCase):
    def test_historical_doubt_and_current_no_doubt_keep_separate_axes(self):
        request = request_for('In 2016 there was substantial doubt about our ability to continue as a going concern. '
                              'In 2017 management concluded there was no substantial doubt about our ability to continue as a going concern.')
        response = response_for(request, timing='HISTORICAL')
        current = deepcopy(response['units'][0]['findings'][0])
        current.update(kind='NO_DOUBT_DECLARATION', timing='CURRENT_REPORT')
        response['units'][0]['findings'].append(current)
        checked = validate_response(request=request, raw_response=_bytes(response))
        self.assertEqual(checked['response'], response)
        self.assertEqual(len(checked['findings']), 2)
        self.assertEqual([f['kind'] for f in checked['current_target_findings']], ['NO_DOUBT_DECLARATION'])

    def test_clean_opinion_cyber_and_valuation_are_not_going_concern_assertions(self):
        for text in ('The statements present fairly in all material respects.',
                     'No cybersecurity threat has materially affected our operations.',
                     'There is substantial doubt about the valuation of the acquired asset.'):
            request = request_for(text)
            for kind in ('DOUBT_DISCLOSED', 'NO_DOUBT_DECLARATION'):
                with self.subTest(text=text, kind=kind), self.assertRaisesRegex(ValueError, 'EXPLICIT_GOING_CONCERN_ASSERTION'):
                    validate_response(request=request, raw_response=_bytes(response_for(request, kind)))

    def test_quoted_current_claim_and_missing_candidate_are_rejected(self):
        request = request_for('There is substantial doubt about our ability to continue as a going concern.', quoted=True)
        with self.assertRaisesRegex(ValueError, 'QUOTED_TEXT'):
            validate_response(request=request, raw_response=_bytes(response_for(request)))
        request = request_for('A going concern assessment is described below.')
        response = response_for(request); response['units'][0]['findings'] = []
        with self.assertRaisesRegex(ValueError, 'KNOWN_CANDIDATE_NOT_ASSESSED'):
            validate_response(request=request, raw_response=_bytes(response))

    def test_reference_positions_and_original_diagnostic_source_cannot_upgrade(self):
        request = request_for('There is substantial doubt about our ability to continue as a going concern.')
        response = response_for(request); response['units'][0]['findings'][0]['evidence'][0]['source_index'] = 0
        with self.assertRaisesRegex(ValueError, 'REFERENCE_OUTSIDE_SOURCE'):
            validate_response(request=request, raw_response=_bytes(response))
        source = source_packet(); source['record_type'] = 'D04_HISTORICAL_PRIMARY_CONTROL_SOURCE'
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        with self.assertRaisesRegex(ValueError, 'COMPLETE_SOURCE_REQUIRED'):
            native_source(source)


class D04NativeTextRecordsTest(unittest.TestCase):
    def test_current_doubt_passes_review_and_historical_only_is_not_current_doubt(self):
        from tests.vnext.test_text_coverage import annual, binding
        from vnext.text_coverage import build_text_document
        from vnext.normal_source_authority import ROOT
        from vnext.specs import compile_spec_file
        from vnext import capacity_text_results as api
        from vnext.review import create_system_review_decision
        from vnext.requirements import load_requirement_snapshot
        statement = 'These conditions raise substantial doubt about our ability to continue as a going concern.'
        raw = binding(annual('<p>' + statement + '</p>'))
        document = build_text_document(**raw); did = document['text_document_id']
        unit = _seal_unit(did, 'VISIBLE_TEXT', {'blocks': document['blocks']}, 0)
        index = next(b['block_index'] for b in document['blocks'] if statement in b['text'])
        source = source_packet()
        source.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04', company_id='sample_entity',
            units=[unit], required_unit_ids=[unit['unit_id']])
        source['prepared_annual_input'].update(entity='12345', filing={'accessionNumber': raw['source_reference']['accession']})
        period = {'period_start': '2025-01-01', 'period_end': '2025-12-31', 'fiscal_year': 2025}
        source['prepared_annual_input']['table_input']['target_period'] = period
        source['documents'] = [{'document_id': did, 'filing': {'form': '10-K'}, 'registrant_name_binding': {},
            'language_candidate_block_indices': [index], 'native_candidate_ordinals': [],
            'source_reference': raw['source_reference'], 'raw_blob': raw['raw_blob'], 'source_unit_ids': [unit['unit_id']]}]
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        source = native_source(source); requests = requests_from_source(source)
        spec = compile_spec_file(path=ROOT/'catalog/r6/D04_going_concern_assessment_v1.md', dependency_specs={})
        scope = spec['compiled']['required_claims']
        target = {'company_id': 'sample_entity', 'entity': '12345', 'accession': raw['source_reference']['accession'],
            'period_start': period['period_start'], 'period_end': period['period_end'], 'scope': scope, 'scope_key': content_hash(value=scope)}
        for timing in ('CURRENT_REPORT', 'HISTORICAL'):
            finding = {'kind': 'DOUBT_DISCLOSED', 'subject': 'TARGET_REGISTRANT', 'timing': timing,
                'unit_id': unit['unit_id'], 'reason': 'Synthetic record-building classification; not source admission.',
                'resolved_evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': index, 'text': statement}]}
            body = {'record_type': 'D04_NATIVE_SOURCE_ASSESSMENT_SET', 'source_id': source['semantic_source_id'],
                'company_id': source['company_id'], 'required_request_ids': [r['request_id'] for r in requests],
                'completed': [{'request_id': r['request_id'], 'candidate': {'selected': {'source_assessment': {'findings': [finding]}}}}
                              for r in requests], 'all_source_requests_accepted': True, 'missing_request_ids': [],
                'failed_requests': [], 'source_findings': [finding], 'mode': 'RECORDED_TEST_ONLY',
                'proposed_branch': 'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW' if timing == 'CURRENT_REPORT' else
                                   'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'}
            assessment = {**body, 'assessment_set_id': content_hash(value=body)}
            args = {'compiled_spec': spec, 'target': target, 'source': source, 'assessment': assessment,
                'source_references': [raw['source_reference']], 'raw_bytes_by_id': {raw['raw_blob']['raw_asset_id']: raw['raw_bytes']}}
            candidate = api.create_deterministic_text_candidate(**args)
            evidence = api.build_text_evidence(candidate=candidate, **args)
            review, _ = api.build_text_review_unit(compiled_spec=spec, candidate=candidate,
                evidence_check=evidence, source_bindings=args['source_references'])
            requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/ai_first_v3_3_1')
            decision = create_system_review_decision(review_unit=review, required_claims=scope,
                decided_at_utc='2026-09-15T00:00:00Z', requirement=requirement)
            result, _, observations = api.replay_text_result(**args, company_traits=[], candidate=candidate,
                evidence_check=evidence, review_unit=review, review_decisions=[decision])
            if timing == 'CURRENT_REPORT':
                self.assertEqual(result['value'], statement)
                self.assertEqual(len(observations), 1)
            else:
                self.assertIsNone(result['value'])
                self.assertEqual(result['reason_code'], 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE')
                self.assertEqual(observations, [])
