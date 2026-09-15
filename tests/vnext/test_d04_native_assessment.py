"""D04 current statements, literal source roles and diagnostic separation."""
from copy import deepcopy
import unittest

from tests.vnext.test_capacity_semantic_review import source_packet
from vnext.canonical import content_hash
from vnext.r6_semantic_source import _seal_unit, _bytes
from vnext.d04_native_assessment import native_source, requests_from_source, validate_response


def request_for(text, quoted=False, year=2025):
    source = source_packet(); source.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04')
    old = source['units'][0]; payload = deepcopy(old['payload'])
    payload['blocks'][0].update(text=text, html_quotation_context=quoted)
    unit = _seal_unit(old['document_id'], 'VISIBLE_TEXT', payload, 0)
    source.update(units=[unit], required_unit_ids=[unit['unit_id']])
    source['documents'][0].update(language_candidate_block_indices=[7], native_candidate_ordinals=[])
    source['prepared_annual_input']['table_input']['target_period'] = {
        'period_start': str(year) + '-01-01', 'period_end': str(year) + '-12-31', 'fiscal_year': year}
    source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
    return requests_from_source(native_source(source))[0]


def response_for(request, kind='DOUBT_DISCLOSED', timing='CURRENT_REPORT'):
    return {'request_id': request['request_id'], 'units': [{
        'unit_id': request['units'][0]['unit_id'], 'reviewed': True, 'unresolved': [], 'findings': [{
            'kind': kind, 'timing': timing, 'subject': 'TARGET_REGISTRANT',
            'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': 7}],
            'reason': 'Recorded classification for the supplied source statement.'}]}]}


class D04NativeProtocolTest(unittest.TestCase):
    def test_nearby_words_and_future_alleviation_do_not_prove_the_relation(self):
        cases = [
            ('There is substantial doubt about the asset valuation, which does not affect our ability to continue as a going concern.', 'DOUBT_DISCLOSED'),
            ('Management expects to alleviate substantial doubt about our ability to continue as a going concern.', 'DOUBT_ALLEVIATED'),
            ('Substantial doubt about our ability to continue as a going concern will have been alleviated after the proposed financing.', 'DOUBT_ALLEVIATED'),
        ]
        for text, kind in cases:
            request = request_for(text)
            with self.subTest(text=text):
                checked = validate_response(request=request, raw_response=_bytes(response_for(request, kind)))
                self.assertTrue(checked['unresolved'])

    def test_undefined_native_going_concern_flag_cannot_be_erased(self):
        source = source_packet()
        source.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04')
        did = source['units'][0]['document_id']
        unit = _seal_unit(did, 'NATIVE_FACTS', {'facts': [{'fact': {'ordinal': 19,
            'qualified_name': 'custom:GoingConcernFlag', 'text': 'false', 'context_ref': 'c',
            'unit_ref': '', 'scale': '0', 'sign': '', 'tag': 'ix:nonnumeric'},
            'attributes': {}, 'expanded_concept': ['urn:test', 'GoingConcernFlag'], 'namespace_environment_id': 'ns'}],
            'contexts': {}, 'units': {}, 'namespace_environments': {}}, 0)
        source.update(units=[unit], required_unit_ids=[unit['unit_id']])
        source['documents'][0].update(language_candidate_block_indices=[], native_candidate_ordinals=[19])
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        request = requests_from_source(native_source(source))[0]
        response = response_for(request, 'VALUATION_OR_OTHER_MEANING')
        response['units'][0]['findings'][0]['evidence'] = [{'kind': 'NATIVE_FACT', 'source_index': 19}]
        checked = validate_response(request=request, raw_response=_bytes(response))
        self.assertEqual(checked['unresolved'][0]['reason'], 'D04_NATIVE_CONCEPT_MEANING_NOT_ESTABLISHED')

    def test_uncertain_related_content_is_retained_and_cannot_become_absence(self):
        for text in (
            'A going concern assessment is described below.',
            'We do not believe these conditions raise substantial doubt about our ability to continue as a going concern.',
            'Management is evaluating whether there is substantial doubt about our ability to continue as a going concern.',
        ):
            request = request_for(text)
            checked = validate_response(request=request, raw_response=_bytes(response_for(request, 'VALUATION_OR_OTHER_MEANING')))
            self.assertTrue(checked['unresolved'])
            self.assertEqual(checked['unresolved'][0]['source_index'], 7)
            self.assertEqual(checked['unresolved'][0]['statement_text'], text)

    def test_bound_other_entity_conditional_and_alleviation_relations(self):
        for text, kind, subject, timing in (
            ("There is substantial doubt about our supplier's ability to continue as a going concern.", 'DOUBT_DISCLOSED', 'OTHER_ENTITY', 'CURRENT_REPORT'),
            ('If these events occur, there is substantial doubt about our ability to continue as a going concern.', 'CONDITIONAL_OR_BOILERPLATE', 'TARGET_REGISTRANT', 'CONDITIONAL'),
            ('Substantial doubt about our ability to continue as a going concern has been alleviated.', 'DOUBT_ALLEVIATED', 'TARGET_REGISTRANT', 'CURRENT_REPORT'),
            ('Substantial doubt about our ability to continue as a going concern has not been alleviated.', 'DOUBT_DISCLOSED', 'TARGET_REGISTRANT', 'CURRENT_REPORT'),
        ):
            request = request_for(text)
            response = response_for(request, kind, timing)
            response['units'][0]['findings'][0]['subject'] = subject
            with self.subTest(text=text):
                checked = validate_response(request=request, raw_response=_bytes(response))
                self.assertEqual(checked['unresolved'], [])
                response['units'][0]['findings'][0].update(kind='NO_DOUBT_DECLARATION', subject='TARGET_REGISTRANT', timing='CURRENT_REPORT')
                with self.assertRaisesRegex(ValueError, 'D04_SOURCE_.*CONFLICT'):
                    validate_response(request=request, raw_response=_bytes(response))

    def test_source_polarity_and_exclusion_cannot_be_changed_by_labels(self):
        for text, correct in (
            ('These conditions raise substantial doubt about our ability to continue as a going concern.', 'DOUBT_DISCLOSED'),
            ('Management concluded there is no substantial doubt about our ability to continue as a going concern.', 'NO_DOUBT_DECLARATION'),
        ):
            request = request_for(text)
            validate_response(request=request, raw_response=_bytes(response_for(request, correct)))
            for kind, subject, timing in (
                ('NO_DOUBT_DECLARATION' if correct == 'DOUBT_DISCLOSED' else 'DOUBT_DISCLOSED', 'TARGET_REGISTRANT', 'CURRENT_REPORT'),
                ('VALUATION_OR_OTHER_MEANING', 'TARGET_REGISTRANT', 'CURRENT_REPORT'),
                (correct, 'TARGET_REGISTRANT', 'HISTORICAL'),
                ('OTHER_ENTITY', 'OTHER_ENTITY', 'CURRENT_REPORT'),
            ):
                response = response_for(request, kind, timing)
                response['units'][0]['findings'][0]['subject'] = subject
                with self.subTest(text=text, kind=kind, subject=subject, timing=timing), self.assertRaisesRegex(ValueError, 'D04_SOURCE_.*CONFLICT'):
                    validate_response(request=request, raw_response=_bytes(response))

    def test_historical_doubt_and_current_no_doubt_keep_separate_axes(self):
        request = request_for('In 2016 there was substantial doubt about our ability to continue as a going concern. '
                              'In 2017 management concluded there was no substantial doubt about our ability to continue as a going concern.', year=2017)
        response = response_for(request, timing='HISTORICAL')
        current = deepcopy(response['units'][0]['findings'][0])
        current.update(kind='NO_DOUBT_DECLARATION', timing='CURRENT_REPORT')
        response['units'][0]['findings'].append(current)
        checked = validate_response(request=request, raw_response=_bytes(response))
        self.assertEqual(checked['response'], response)
        self.assertEqual(len(checked['findings']), 2)
        self.assertEqual(checked['unresolved'], [])
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


def text_arguments(statement, kind, timing):
    from tests.vnext.test_text_coverage import annual, binding
    from vnext.text_coverage import build_text_document
    from vnext.normal_source_authority import ROOT
    from vnext.specs import compile_spec_file
    from vnext import capacity_text_results as api
    from vnext.review import create_system_review_decision
    from vnext.requirements import load_requirement_snapshot
    raw = binding(annual('<p>' + statement + '</p>'))
    document = build_text_document(**raw); did = document['text_document_id']
    for block in document['blocks']:
        block['html_quotation_context'] = False
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
    finding = {'kind': kind, 'subject': 'TARGET_REGISTRANT', 'timing': timing,
        'unit_id': unit['unit_id'], 'reason': 'Synthetic record-building classification; not source admission.',
        'resolved_evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': index, 'text': statement}]}
    body = {'record_type': 'D04_NATIVE_SOURCE_ASSESSMENT_SET', 'source_id': source['semantic_source_id'],
        'company_id': source['company_id'], 'required_request_ids': [r['request_id'] for r in requests],
        'completed': [{'request_id': r['request_id'], 'candidate': {'selected': {'source_assessment': {'findings': ([finding] if kind else [])}}}}
                      for r in requests], 'all_source_requests_accepted': True, 'missing_request_ids': [],
        'failed_requests': [], 'source_findings': ([finding] if kind else []), 'mode': 'RECORDED_TEST_ONLY',
        'proposed_branch': 'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW' if kind and timing == 'CURRENT_REPORT' else
                           'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'}
    assessment = {**body, 'assessment_set_id': content_hash(value=body)}
    args = {'compiled_spec': spec, 'target': target, 'source': source, 'assessment': assessment,
        'source_references': [raw['source_reference']], 'raw_bytes_by_id': {raw['raw_blob']['raw_asset_id']: raw['raw_bytes']}}
    return args


class D04NativeTextRecordsTest(unittest.TestCase):
    def test_native_acceptor_rejects_same_reference_with_wrong_classification(self):
        from types import SimpleNamespace
        from vnext.d04_native_assessment import build_acceptance
        statement = 'These conditions raise substantial doubt about our ability to continue as a going concern.'
        args = text_arguments(statement, 'DOUBT_DISCLOSED', 'CURRENT_REPORT')
        request = requests_from_source(args['source'])[0]
        finding = args['assessment']['source_findings'][0]
        evidence = [{k:e[k] for k in ('kind', 'source_index')} for e in finding['resolved_evidence']]
        response = {'request_id': request['request_id'], 'units': [{'unit_id': finding['unit_id'],
            'reviewed': True, 'unresolved': [], 'findings': [{k:finding[k] for k in ('kind', 'subject', 'timing', 'reason')} | {'evidence': evidence}]}]}
        prepared = SimpleNamespace(request_bytes=_bytes(request), source_bytes=_bytes(args['source']))
        plan = {key: content_hash(value=key) for key in ('selected_representation_hash', 'ai_invocation_plan_id',
            'source_identity_hash', 'task_contract_hash')}
        accepted = build_acceptance(prepared=prepared, plan=plan, response_body=_bytes(response))
        self.assertEqual(accepted['evidence_status'], 'PASS')
        for kind, timing in [('NO_DOUBT_DECLARATION', 'CURRENT_REPORT'), ('VALUATION_OR_OTHER_MEANING', 'CURRENT_REPORT'),
                             ('DOUBT_DISCLOSED', 'HISTORICAL')]:
            changed = deepcopy(response)
            changed['units'][0]['findings'][0].update(kind=kind, timing=timing)
            self.assertEqual(changed['units'][0]['findings'][0]['evidence'], evidence)
            with self.subTest(kind=kind, timing=timing), self.assertRaisesRegex(ValueError, 'D04_SOURCE_.*CONFLICT'):
                build_acceptance(prepared=prepared, plan=plan, response_body=_bytes(changed))

    def reviewed_result(self, args):
        from vnext import capacity_text_results as api
        from vnext.review import create_system_review_decision
        from vnext.requirements import load_requirement_snapshot
        from vnext.normal_source_authority import ROOT
        candidate = api.create_deterministic_text_candidate(**args)
        evidence = api.build_text_evidence(candidate=candidate, **args)
        review, _ = api.build_text_review_unit(compiled_spec=args['compiled_spec'], candidate=candidate,
            evidence_check=evidence, source_bindings=args['source_references'])
        requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/ai_first_v3_3_1')
        decision = create_system_review_decision(review_unit=review, required_claims=args['target']['scope'],
            decided_at_utc='2026-09-15T00:00:00Z', requirement=requirement)
        return api.replay_text_result(**args, company_traits=[], candidate=candidate,
            evidence_check=evidence, review_unit=review, review_decisions=[decision])[0]

    def test_actual_current_and_historical_statements_and_genuine_absence(self):
        cases = [
            ('These conditions raise substantial doubt about our ability to continue as a going concern.', 'DOUBT_DISCLOSED', 'CURRENT_REPORT'),
            ('There is no substantial doubt about our ability to continue as a going concern.', 'NO_DOUBT_DECLARATION', 'CURRENT_REPORT'),
            ('Substantial doubt about our ability to continue as a going concern has been alleviated.', 'DOUBT_ALLEVIATED', 'CURRENT_REPORT'),
            ('In 2024 there was substantial doubt about our ability to continue as a going concern.', 'DOUBT_DISCLOSED', 'HISTORICAL'),
            ('Revenue is recognized when services are delivered.', None, 'CURRENT_REPORT'),
        ]
        for statement, kind, timing in cases:
            with self.subTest(kind=kind, timing=timing):
                args = text_arguments(statement, kind, timing)
                result = self.reviewed_result(args)
                if kind and timing == 'CURRENT_REPORT':
                    self.assertEqual(result['value'], statement)
                else:
                    self.assertIsNone(result['value'])
                    self.assertEqual(result['reason_code'], 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE')
                    from vnext.capacity_run import project_defined_absence
                    row, _ = project_defined_absence(case={'registered_input': {'assessment': args['assessment']},
                        'selection': {'status': 'TEXT_QUAL'}, 'text_arguments': args}, result=result,
                        row={}, company={'display_name': 'Sample', 'primary_cik': '12345'})
                    self.assertIn('未披露持续经营疑虑', row['notes'])

    def test_resigned_false_exclusion_cannot_reach_review_or_public_absence(self):
        from vnext import capacity_text_results as api
        from vnext.capacity_run import project_defined_absence
        true_absence = text_arguments('Revenue is recognized when services are delivered.', None, 'CURRENT_REPORT')
        result = self.reviewed_result(true_absence)
        statement = 'These conditions raise substantial doubt about our ability to continue as a going concern.'
        for kind, timing in [('VALUATION_OR_OTHER_MEANING', 'CURRENT_REPORT'), ('DOUBT_DISCLOSED', 'HISTORICAL'),
                             ('NO_DOUBT_DECLARATION', 'CURRENT_REPORT'), (None, 'CURRENT_REPORT')]:
            args = text_arguments(statement, kind, timing)
            with self.subTest(kind=kind, timing=timing), self.assertRaisesRegex(ValueError, 'D04_SOURCE_.*CONFLICT'):
                api.create_deterministic_text_candidate(**args)
            args['assessment']['proposed_branch'] = 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
            args['assessment']['assessment_set_id'] = content_hash(value={k:v for k,v in args['assessment'].items() if k != 'assessment_set_id'})
            with self.subTest(public_kind=kind), self.assertRaisesRegex(ValueError, 'D04_SOURCE_.*CONFLICT'):
                project_defined_absence(case={'registered_input': {'assessment': args['assessment']},
                    'selection': {'status': 'TEXT_QUAL'}, 'text_arguments': args}, result=result,
                    row={}, company={'display_name': 'Sample', 'primary_cik': '12345'})
