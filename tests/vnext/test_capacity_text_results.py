"""Native text records preserve real quarterly-capacity prose and Review."""
from copy import deepcopy
import json
import tarfile
import unittest

from vnext.canonical import content_hash
from vnext.capacity_semantic_review import requests_from_source
from vnext import capacity_text_results as api
from vnext.normal_source_authority import ROOT
from vnext.specs import compile_spec_file


def reseal(value, field):
    value[field] = content_hash(value={k: v for k, v in value.items() if k != field})
    return value


class CapacityTextResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tarfile.open(ROOT / 'docs/evidence/issue28_continuous/resume-2026-09-14/b13-complete-source.tar.gz') as archive:
            source = json.load(archive.extractfile('enphase_energy.json'))
        requests = requests_from_source(source)
        unit = next(u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT'
                    and any('approximately five-million microinverters per quarter' in b['text'] for b in u['payload']['blocks']))
        block = next(b for b in unit['payload']['blocks'] if 'approximately five-million microinverters per quarter' in b['text'])
        finding = {'kind': 'AVAILABLE_CAPACITY', 'subject': 'TARGET_REGISTRANT', 'timing': 'CURRENT_REPORT',
            'unit_id': unit['unit_id'], 'reason': 'Recorded source-role input for text record tests; not provider verification.',
            'resolved_evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': block['block_index'], 'text': block['text']}]}
        rows = []
        for request in requests:
            found = [finding] if unit['unit_id'] in {u['unit_id'] for u in request['units']} else []
            rows.append({'request_id': request['request_id'],
                         'candidate': {'selected': {'source_assessment': {'findings': found}}}})
        # Deliberately caller-supplied recorded inputs for the pure record API.
        # A real Run must reject these without registered native executions.
        assessment = reseal({'record_type': 'B13_NATIVE_SOURCE_ASSESSMENT_SET',
            'source_id': source['semantic_source_id'], 'company_id': source['company_id'],
            'required_request_ids': [r['request_id'] for r in requests], 'completed': rows,
            'all_source_requests_accepted': True, 'missing_request_ids': [], 'failed_requests': [],
            'proposed_branch': 'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW', 'source_findings': [finding],
            'mode': 'RECORDED_TEST_ONLY'}, 'assessment_set_id')
        spec = compile_spec_file(path=ROOT / 'catalog/r5/B13_capacity_disclosures_v1.md', dependency_specs={})
        annual = source['prepared_annual_input']; period = annual['table_input']['target_period']
        scope = spec['compiled']['required_claims']
        target = {'company_id': source['company_id'], 'entity': annual['entity'],
            'accession': annual['filing']['accessionNumber'], 'period_start': period['period_start'],
            'period_end': period['period_end'], 'scope': scope, 'scope_key': content_hash(value=scope)}
        cls.arguments = {'compiled_spec': spec, 'target': target, 'source': source, 'assessment': assessment,
            'source_references': [d['source_reference'] for d in source['documents']],
            'raw_bytes_by_id': {d['raw_blob']['raw_asset_id']: (ROOT / d['raw_blob']['storage_uri']).read_bytes()
                                for d in source['documents']}}
        cls.expected_text = block['text']

    def reviewed(self, args=None):
        from vnext.review import create_system_review_decision
        from vnext.requirements import load_requirement_snapshot
        args = self.arguments if args is None else args
        candidate = api.create_deterministic_text_candidate(**args)
        evidence = api.build_text_evidence(candidate=candidate, **args)
        unit, _ = api.build_text_review_unit(compiled_spec=args['compiled_spec'], candidate=candidate,
            evidence_check=evidence, source_bindings=args['source_references'])
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/ai_first_v3_3_1')
        decision = create_system_review_decision(review_unit=unit, required_claims=args['target']['scope'],
            decided_at_utc='2026-09-14T14:00:00Z', requirement=requirement)
        return dict(args, company_traits=[], candidate=candidate, evidence_check=evidence,
                    review_unit=unit, review_decisions=[decision])

    def test_defined_absence_needs_complete_source_set_and_effective_review(self):
        args = deepcopy(self.arguments)
        from tests.vnext.test_text_coverage import annual, binding
        from tests.vnext.test_capacity_semantic_review import source_packet
        from vnext.text_coverage import build_text_document
        from vnext.r6_semantic_source import _seal_unit
        original = binding(annual('<h1>Business</h1><p>Revenue is recognized when services are delivered.</p>'))
        document = build_text_document(**original)
        source = source_packet(); source['company_id'] = original['expected_company_id']
        did = document['text_document_id']
        unit = _seal_unit(did, 'VISIBLE_TEXT', {'blocks': document['blocks']}, 0)
        source.update(units=[unit], required_unit_ids=[unit['unit_id']], capacity_navigation=[],
            source_check_scope='SYNTHETIC_COMPLETE_PRIMARY_TEST_ONLY')
        prepared = args['source']['prepared_annual_input']
        prepared['entity'] = original['expected_cik']
        prepared['filing']['accessionNumber'] = original['source_reference']['accession']
        source['prepared_annual_input'] = prepared
        source['documents'] = [{'document_id': did, 'filing': prepared['filing'],
            'registrant_name_binding': {}, 'source_reference': original['source_reference'],
            'raw_blob': original['raw_blob'], 'source_unit_ids': [unit['unit_id']]}]
        reseal(source, 'semantic_source_id')
        args.update(source=source, source_references=[original['source_reference']],
            raw_bytes_by_id={original['raw_blob']['raw_asset_id']: original['raw_bytes']})
        args['target'].update(company_id=source['company_id'], entity=prepared['entity'],
                              accession=prepared['filing']['accessionNumber'])
        assessment = args['assessment']
        requests = requests_from_source(source)
        assessment.update(company_id=source['company_id'], source_id=source['semantic_source_id'],
            required_request_ids=[r['request_id'] for r in requests],
            completed=[{'request_id': r['request_id'],
                        'candidate': {'selected': {'source_assessment': {'findings': []}}}} for r in requests])
        assessment['source_findings'] = []
        assessment['proposed_branch'] = 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
        reseal(assessment, 'assessment_set_id')
        reviewed = self.reviewed(args)
        result, trace, observations = api.replay_text_result(**reviewed)
        self.assertIsNone(result['value'])
        self.assertEqual(result['reason_code'], 'B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE')
        self.assertEqual(observations, [])
        self.assertEqual(trace['input_observation_ids'], [])
        from vnext.capacity_run import project_defined_absence
        row, evidence = project_defined_absence(case={
            'registered_input': {'assessment': assessment},
            'selection': {'status': 'NOT_AVAILABLE_SEC'}, 'text_arguments': args},
            result=result, row={}, company={'display_name': 'Synthetic fixture', 'primary_cik': '12345'})
        self.assertEqual(row['status'], 'NOT_AVAILABLE_SEC')
        self.assertEqual(row['value'], '')
        self.assertEqual(len(evidence), len(source['documents']))
        self.assertIn('Host scope-check record', evidence[0]['evidence_quote'])
        reviewed['review_decisions'] = []
        with self.assertRaisesRegex(ValueError, 'no decision|EFFECTIVE_REVIEW_REQUIRED'):
            api.replay_text_result(**reviewed)
        args['assessment']['completed'].pop()
        reseal(args['assessment'], 'assessment_set_id')
        with self.assertRaisesRegex(ValueError, 'REQUEST_COVERAGE_CHANGED'):
            api.create_deterministic_text_candidate(**args)

    def test_reviewed_capacity_prose_is_text_without_annualization_or_ratio(self):
        result, trace, observations = api.replay_text_result(**self.reviewed())
        self.assertEqual(result['value_kind'], 'TEXT_V1')
        self.assertEqual(result['value'], self.expected_text)
        self.assertEqual(result['unit'], 'text')
        self.assertEqual(len(observations), 1)
        self.assertEqual(trace['result'], self.expected_text)

    def test_forged_complete_flags_and_numeric_opportunity_do_not_become_text(self):
        for mutation in ('drop_request', 'add_actual_output', 'wrong_period'):
            args = deepcopy(self.arguments)
            if mutation == 'drop_request':
                args['assessment']['completed'].pop()
            elif mutation == 'add_actual_output':
                finding = deepcopy(args['assessment']['source_findings'][0]); finding['kind'] = 'ACTUAL_PRODUCTION'
                args['assessment']['source_findings'].append(finding)
                row = next(row for row in args['assessment']['completed']
                           if row['candidate']['selected']['source_assessment']['findings'])
                row['candidate']['selected']['source_assessment']['findings'].append(finding)
            else:
                args['target']['period_start'] = '2025-10-01'
            reseal(args['assessment'], 'assessment_set_id')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                api.create_deterministic_text_candidate(**args)

    def test_raw_source_and_effective_review_are_required(self):
        args = self.reviewed()
        args['review_decisions'] = []
        with self.assertRaises(ValueError):
            api.replay_text_result(**args)
        args = deepcopy(self.arguments)
        key = next(iter(args['raw_bytes_by_id']))
        args['raw_bytes_by_id'][key] += b'changed'
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_BYTES_CHANGED'):
            api.create_deterministic_text_candidate(**args)
