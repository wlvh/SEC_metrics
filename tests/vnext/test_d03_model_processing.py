import json
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from vnext import d03_model_processing as model
from vnext.canonical import content_hash, sha256_bytes
from vnext.native_unit_index import evidence_json_bytes


class D03ModelProcessingTest(unittest.TestCase):
    def setUp(self):
        self.unit = {'unit_id': 'unit:visible', 'kind': 'VISIBLE_TEXT',
                     'payload': {'blocks': [{'block_index': 0, 'html_quotation_context': False,
                         'text': 'We are currently cooperating with the SEC investigation.'}]}}
        ref = {'raw_asset_id': 'sha256:'+'1'*64, 'company_id': 'fixture_company',
            'source_url': 'https://www.sec.gov/Archives/edgar/data/1048286/000104828626000007/mar-20251231.htm',
            'accession': '0001048286-26-000007', 'document_name': 'mar-20251231.htm',
            'source_role': 'target_primary'}
        ref = {'record_type': 'SOURCE_REFERENCE', **ref, 'source_reference_id': content_hash(value=ref),
               'request_attempt_id': 'request:synthetic:source'}
        self.source = {'company_id': 'fixture_company', 'semantic_source_id': 'source:fixture',
            'prepared_annual_input': {'table_input': {'target_period': '2025'}},
            'documents': [{'filing': {'form': '10-K', 'filingDate': '2026-02-10'},
                           'source_reference': ref, 'raw_blob': {'raw_asset_id': ref['raw_asset_id']}}],
            'units': [self.unit], 'required_unit_ids': [self.unit['unit_id']],
            'source_serialization_complete': True, 'source_proofs': [],
            'source_admission': {'synthetic_test_only': True}}
        self.payload = {'source_id': self.source['semantic_source_id'], 'company_id': 'fixture_company',
            'target_period': '2025', 'source_filing': self.source['documents'][0]['filing'],
            'visible_columns': ['source_index', 'html_quotation_context', 'text'],
            'complete_visible_rows': [[0, False, self.unit['payload']['blocks'][0]['text']]],
            'visible_unit_bounds': [{'unit_id': self.unit['unit_id'], 'start_row': 0, 'end_row_exclusive': 1}],
            'native_units': [], 'shared_source_dictionaries': {},
            'responsibility_unit_ids': [self.unit['unit_id']], 'visible_context_role': 'RESPONSIBILITY'}
        self.response = {'reviewed_unit_ids': [self.unit['unit_id']], 'findings': [{
            'kind': 'CURRENT_REGULATORY_ACTION', 'subject': 'fixture registrant', 'event_dates': [],
            'reported_context_times': [], 'status': 'Explicitly ongoing as reported',
            'evidence': [{'unit_id': self.unit['unit_id'], 'kind': 'VISIBLE_BLOCK', 'source_index': 0}],
            'description': 'The filing states current cooperation with the SEC investigation.'}],
            'scope_current_involvement': 'EXPLICIT_PRESENT', 'unresolved': ['Target detail remains unproven']}
        self.prompt = (model.ROOT/'docs/evidence/issue28_continuous/d03-complete-context-plan-20261003/input-prompt.txt').read_text()

    def packet(self, payload=None, response=None):
        wire = {'model': 'deepseek-flash', 'messages': [
            {'role': 'system', 'content': self.prompt},
            {'role': 'user', 'content': model._bytes(payload or self.payload).decode()}],
            'max_tokens': 4096, 'temperature': 0, 'stream': False,
            'response_format': {'type': 'json_object'}, 'thinking': {'type': 'disabled'}}
        request_raw = model._bytes(wire)
        response_raw = model._bytes(response or self.response)
        return {'request_body': request_raw, 'response_body': response_raw,
            'expected_request_sha256': sha256_bytes(content=request_raw),
            'expected_response_sha256': sha256_bytes(content=response_raw)}

    def test_clear_nonempty_current_proposal_remains_pending_not_verified(self):
        with patch.object(model, 'prepare_regulatory_semantic_source', return_value=self.source):
            out = model.build_development_company_assessment(data_root='/fixture', company_id='fixture_company',
                packets=[self.packet()], expected_source_sha256=sha256_bytes(content=evidence_json_bytes(self.source)))
        asset, candidate, evidence, unit = out['records']
        self.assertEqual(candidate['status'], 'REVIEW_REQUIRED')
        self.assertEqual(unit['status'], 'PENDING')
        self.assertEqual(unit['normalized_scope'], {})
        self.assertFalse(unit['system_approval_eligible'])
        self.assertFalse(out['provider_attempt_created'])
        self.assertFalse(out['native_result_created'])
        self.assertEqual(out['processing']['rows'][0]['original_response'], self.response)
        self.assertIn('Target detail remains unproven', out['rendered_review_bytes'].decode())
        self.assertIn('Explicitly ongoing as reported', out['rendered_review_bytes'].decode())
        self.assertIn('EXPLICIT', out['rendered_review_bytes'].decode())

    def test_empty_findings_preserve_unresolved_no_absence_credit(self):
        answer = {**self.response, 'findings': [], 'scope_current_involvement': 'UNRESOLVED'}
        rows, _ = model._complete(self.source, [self.packet(response=answer)])
        self.assertEqual(rows[0]['original_response'], answer)

    def test_missing_or_duplicate_complete_owner_refused(self):
        for packets in [[], [self.packet(), self.packet()]]:
            with self.assertRaisesRegex(ValueError, 'COMPLETE_'):
                model._complete(self.source, packets)

    def test_reference_kind_boolean_and_foreign_unit_refused(self):
        for ref in [{'unit_id': self.unit['unit_id'], 'kind': 'NATIVE_FACT', 'source_index': 0},
                    {'unit_id': self.unit['unit_id'], 'kind': 'VISIBLE_BLOCK', 'source_index': True},
                    {'unit_id': 'foreign', 'kind': 'VISIBLE_BLOCK', 'source_index': 0}]:
            value = deepcopy(self.response); value['findings'][0]['evidence'] = [ref]
            with self.assertRaisesRegex(ValueError, 'REFERENCE_'):
                model._complete(self.source, [self.packet(response=value)])

    def test_external_wire_sha_and_source_context_refused(self):
        packet = self.packet(); packet['expected_response_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'EXTERNAL_WIRE_CHANGED'):
            model._complete(self.source, [packet])
        value = deepcopy(self.payload); value['complete_visible_rows'][0][2] = 'different'
        with self.assertRaisesRegex(ValueError, 'VISIBLE_CONTEXT_CHANGED'):
            model._complete(self.source, [self.packet(payload=value)])

    def test_exact_duplicate_is_not_cleaned_and_unicode_is_preserved(self):
        value = deepcopy(self.response); value['findings'].append(deepcopy(value['findings'][0]))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_FINDING'):
            model._complete(self.source, [self.packet(response=value)])
        value = deepcopy(self.response); value['findings'][0]['description'] += '\u037e'
        rows, _ = model._complete(self.source, [self.packet(response=value)])
        self.assertEqual(rows[0]['original_response'], value)

    def test_live_origin_is_refused_before_any_source_read(self):
        with patch.object(model, 'prepare_regulatory_semantic_source') as read:
            with self.assertRaisesRegex(ValueError, 'REAL_EXECUTION_NOT_AUTHORIZED'):
                model.build_development_company_assessment(data_root='/forbidden', company_id='no-read',
                    packets=[], expected_source_sha256='wrong', origin='LIVE')
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
