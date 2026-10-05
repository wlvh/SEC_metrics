"""Exact mixed native request partitions; synthetic inputs, no provider calls.

The collector's archived-runtime reader and private journal location are test
doubles. Request reconstruction, native response/Evidence construction, full
acceptance receipt checks, registration loading and text coverage are real.
"""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.capacity_assessment_input import input_key, load_registered_input
from vnext.continuous_semantic_calls import request_body
from vnext.d04_native_assessment import build_acceptance, native_source
from vnext.native_assessment_replay import revalidation_receipt
from vnext.native_unit_index import reconstruct_requests, upgrade_request, validate_request_partition
from vnext import capacity_assessment_input as registered_api, invocation_control as control


def synthetic_source():
    from tests.vnext.test_d04_native_assessment import text_arguments
    from tests.vnext.test_text_coverage import annual, binding
    from vnext.r6_semantic_source import _seal_unit
    from vnext.sources import source_reference_record
    from vnext.text_coverage import build_text_document
    args = text_arguments('Revenue is recognized when services are delivered.', None, 'CURRENT_REPORT')
    source = deepcopy(args['source'])
    for field in ('semantic_source_id', 'original_complete_source_id', 'source_check_scope',
                  'response_contract_version', 'request_context_format'):
        source.pop(field, None)
    source['record_type'] = 'D04_COMPLETE_SEMANTIC_SOURCE'
    documents, units, raw_bytes = [], [], {}
    for index in range(3):
        form = '10-K' if index == 0 else '10-K/A'
        raw = binding(annual('<p>Revenue is recognized when service ' + str(index) + ' is delivered.</p>', form=form))
        name = 'source-' + str(index) + '.htm'
        accession = '0000012345-26-00000' + str(index + 1)
        raw['raw_blob']['storage_uri'] = 'fixture/' + name
        raw['source_reference'] = source_reference_record(raw_blob=raw['raw_blob'], company_id='sample_entity',
            source_url='https://www.sec.gov/Archives/edgar/data/12345/' + accession.replace('-', '') + '/' + name,
            accession=accession, document_name=name, source_role='target_primary', request_attempt_id='test-only-' + str(index))
        document = build_text_document(**raw)
        for block in document['blocks']:
            block['html_quotation_context'] = False
        unit = _seal_unit(document['text_document_id'], 'VISIBLE_TEXT', {'blocks': document['blocks']}, 0)
        units.append(unit)
        documents.append({'document_id': unit['document_id'], 'filing': {'form': form},
            'registrant_name_binding': {}, 'language_candidate_block_indices': [], 'native_candidate_ordinals': [],
            'source_reference': raw['source_reference'], 'raw_blob': raw['raw_blob'], 'source_unit_ids': [unit['unit_id']]})
        raw_bytes[raw['raw_blob']['raw_asset_id']] = raw['raw_bytes']
    source.update(documents=documents, units=units, required_unit_ids=[u['unit_id'] for u in units])
    source['semantic_source_id'] = content_hash(value=source)
    source = native_source(source, complete_response_contract=True)
    args.update(source=source, source_references=[d['source_reference'] for d in documents], raw_bytes_by_id=raw_bytes)
    return source, args


def response_bytes(request):
    rows = [{'reviewed': True, 'findings': [], 'unresolved': [],
             **({'unit_index': i} if 'indexed_unit_contract' in request else {'unit_id': u['unit_id']})}
            for i, u in enumerate(request['units'])]
    value = {'units': rows}
    if 'indexed_unit_contract' not in request:
        value['request_id'] = request['request_id']
    return canonical_json_bytes(value=value)


class NativeRequestVariantsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.text_args = synthetic_source()
        self.base = reconstruct_requests(self.source)
        self.assertEqual(len(self.base), 3)
        self.mixed = [self.base[0], upgrade_request(self.base[1]), self.base[2]]
        self.requirement = {'requirement_closure_hash': content_hash(value='synthetic current requirement')}
        self.policy = SimpleNamespace(model='deepseek-flash')

    def collect(self, requests, *, failed_original=False):
        prepared = [SimpleNamespace(source_bytes=canonical_json_bytes(value=self.source),
            request_bytes=canonical_json_bytes(value=r), requirement=self.requirement) for r in requests]
        state_rows, native_rows, replays = [], [], {}
        for ordinal, (p, request) in enumerate(zip(prepared, requests), start=1):
            plan = {key: content_hash(value=[key, request['request_id']]) for key in
                ('ai_invocation_plan_id', 'provider_request_identity', 'task_contract_hash')}
            plan.update(selected_representation_hash=request['request_id'], source_identity_hash=self.source['semantic_source_id'],
                requirement_closure_hash=self.requirement['requirement_closure_hash'],
                provider_request_body_sha256=sha256_bytes(content=request_body(request, self.policy)))
            raw = response_bytes(request)
            draft = build_acceptance(prepared=p, plan=plan, response_body=raw)
            receipt = control._persist_acceptance_receipt(root=self.root / ('receipt-' + str(ordinal)),
                plan=plan, response_body=raw, acceptance_draft=draft)
            revalidation = revalidation_receipt(prepared=p, plan=plan, original=receipt, expected=draft)
            intent = {'intent_id': content_hash(value=['synthetic intent', ordinal]), 'plan_id': plan['ai_invocation_plan_id'],
                      'requirement_closure_hash': plan['requirement_closure_hash']}
            terminal = {'terminal_id': content_hash(value=['synthetic terminal', ordinal]), 'intent_id': intent['intent_id'],
                        'status': 'SUCCEEDED', 'stop_reason': ''}
            wire = {'assistant_output_sha256': sha256_bytes(content=raw), 'mode': 'RECORDED_TEST_ONLY', 'error_class': ''}
            path = self.root / 'ledger/calls' / ('%04d' % ordinal)
            path.mkdir(parents=True)
            (path / 'semantic-request.json').write_bytes(p.request_bytes)
            (path / 'terminal.json').write_bytes(canonical_json_bytes(value=terminal))
            state_rows.append({'channel': 'PROVIDER', 'ordinal': ordinal, 'status': 'SUCCEEDED'})
            replays[request['request_id']] = {'success': {'acceptance_receipt': receipt,
                'acceptance_receipt_id': receipt['acceptance_receipt_id']}, 'revalidation': revalidation}
            native_rows.append({'request_id': request['request_id'], 'ordinal': ordinal, 'plan': plan,
                'semantic_request': request, 'assistant_output': raw.decode(), 'acceptance_receipt': receipt,
                'source_revalidation': revalidation, 'intent': intent, 'terminal': terminal, 'wire': wire})
        if failed_original:
            path = self.root / 'ledger/calls/0004'; path.mkdir()
            (path / 'semantic-request.json').write_bytes(canonical_json_bytes(value=self.base[1]))
            (path / 'terminal.json').write_bytes(canonical_json_bytes(value={'status': 'FAILED'}))
            state_rows.append({'channel': 'PROVIDER', 'ordinal': 4, 'status': 'FAILED'})
        saved = {p: p.read_bytes() for p in (self.root / 'ledger').rglob('*.json')}
        ledger = SimpleNamespace(root=self.root / 'ledger', live=False, locked=nullcontext,
                                 snapshot=lambda: {'rows': state_rows})
        def replay(*, prepared, path):
            return replays[json.loads(prepared.request_bytes)['request_id']]
        with patch('vnext.native_assessment_replay.replay_native_response', side_effect=replay) as reader:
            assessment = collect_native_assessments(prepared_requests=prepared, ledger=ledger)
        self.assertEqual(reader.call_count, len(requests))
        self.assertEqual(saved, {p: p.read_bytes() for p in saved})
        return assessment, native_rows

    def test_mixed_collection_registration_and_text_coverage_keep_original_success(self):
        old_raw = canonical_json_bytes(value=self.base[0])
        assessment, native_rows = self.collect(self.mixed, failed_original=True)
        self.assertEqual(assessment['native_request_variants'], ['BASE', 'INDEXED_UNITS_V1', 'BASE'])
        self.assertTrue(assessment['all_source_requests_accepted'])
        self.assertEqual(assessment['failed_requests'], [])
        self.assertEqual(assessment['required_request_ids'], [r['request_id'] for r in self.mixed])
        self.assertEqual(canonical_json_bytes(value=self.mixed[0]), old_raw)
        body = {'record_type': 'D04_REGISTERED_NATIVE_ASSESSMENT_INPUT', 'schema_version': 1,
            'source_id': self.source['semantic_source_id'], 'company_id': self.source['company_id'],
            'requirement_closure_hash': self.requirement['requirement_closure_hash'], 'mode': 'RECORDED_TEST_ONLY',
            'assessment': assessment, 'native_requests': native_rows, 'new_call_authority': False, 'production_authorized': False,
            'response_contract_version': self.source['response_contract_version']}
        packet = {**body, 'input_record_id': content_hash(value=body)}
        journal = self.root / 'journal'
        directory = journal / input_key(self.source, self.requirement); directory.mkdir(parents=True)
        (directory / (packet['input_record_id'][7:] + '.json')).write_bytes(canonical_json_bytes(value=packet))
        data = self.root / 'data'; (data / 'config').mkdir(parents=True)
        export = data / registered_api.EXPORT_PATHS['D04']
        export.write_bytes(canonical_json_bytes(value=packet))
        with patch.object(registered_api, '_journal', return_value=journal), \
             patch('vnext.continuous_call_policy.configured_transport_policy', return_value=self.policy), \
             patch.object(control, '_validate_acceptance_receipt', wraps=control._validate_acceptance_receipt) as verifier:
            loaded = load_registered_input(data_root=data, source=self.source, requirement=self.requirement)
            self.assertEqual(verifier.call_count, 3)
            self.assertEqual(verifier.call_args_list[0].kwargs['value'], native_rows[0]['acceptance_receipt'])
            self.assertEqual(verifier.call_args_list[0].kwargs['response_body'], response_bytes(self.base[0]))
            # Even a self-consistent fixture in the trusted test journal must
            # reconstruct the correct request variant at each original group.
            for variants in [['BASE'], ['BASE', 'WRONG_VERSION', 'BASE'], ['BASE', 'BASE', 'BASE']]:
                bad = deepcopy(packet)
                bad['assessment']['native_request_variants'] = variants
                bad['assessment']['assessment_set_id'] = content_hash(value={
                    k:v for k,v in bad['assessment'].items() if k != 'assessment_set_id'})
                bad['input_record_id'] = content_hash(value={k:v for k,v in bad.items() if k != 'input_record_id'})
                (directory / (bad['input_record_id'][7:] + '.json')).write_bytes(canonical_json_bytes(value=bad))
                export.write_bytes(canonical_json_bytes(value=bad))
                with self.subTest(loader_variants=variants), self.assertRaises(ValueError):
                    load_registered_input(data_root=data, source=self.source, requirement=self.requirement)
            export.write_bytes(canonical_json_bytes(value=packet))
        self.assertEqual(loaded, packet)
        self.assertEqual(loaded['native_requests'][0]['acceptance_receipt'], native_rows[0]['acceptance_receipt'])
        from vnext.capacity_text_results import create_deterministic_text_candidate
        args = {**self.text_args, 'assessment': assessment}
        self.assertEqual(create_deterministic_text_candidate(**args)['selected'], {})
        for variants in [['BASE'], ['BASE', 'WRONG_VERSION', 'BASE'], ['BASE', 'BASE', 'BASE']]:
            bad = deepcopy(assessment); bad['native_request_variants'] = variants
            bad['assessment_set_id'] = content_hash(value={k:v for k,v in bad.items() if k != 'assessment_set_id'})
            with self.subTest(variants=variants), self.assertRaises(ValueError):
                create_deterministic_text_candidate(**{**args, 'assessment': bad})

    def test_all_base_preserves_legacy_no_variant_field(self):
        assessment, _ = self.collect(self.base)
        self.assertNotIn('native_request_variants', assessment)
        self.assertEqual(reconstruct_requests(self.source), self.base)
        self.assertEqual(reconstruct_requests(self.source, ['BASE'] * 3), self.base)

    def test_missing_duplicate_reordered_and_cross_source_requests_are_rejected(self):
        changed = deepcopy(self.mixed[1]); changed['source_id'] = content_hash(value='other source')
        changed['request_id'] = content_hash(value={k:v for k,v in changed.items() if k != 'request_id'})
        for requests in [self.mixed[:2], [self.mixed[0], self.mixed[0], self.mixed[2]],
                         list(reversed(self.mixed)), [self.mixed[0], changed, self.mixed[2]]]:
            with self.subTest(ids=[r['request_id'] for r in requests]), self.assertRaises(ValueError):
                validate_request_partition(self.source, requests)
        for variants in [[], ['BASE'] * 2, ['BASE', 'WRONG', 'BASE']]:
            with self.assertRaises(ValueError):
                reconstruct_requests(self.source, variants)


if __name__ == '__main__':
    unittest.main()
