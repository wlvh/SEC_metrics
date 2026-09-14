"""B13 shared source identity, complete coverage and role counterexamples."""
from copy import deepcopy
from pathlib import Path
import json
import tarfile
import unittest

from vnext.canonical import content_hash
from vnext.capacity_semantic_review import _shared_units, _restore_units, requests_from_source, validate_response
from vnext.normal_source_authority import ROOT
from vnext.r6_semantic_source import _bytes, _seal_unit


def source_packet():
    doc = 'sha256:' + '1' * 64
    units = [_seal_unit(doc, 'VISIBLE_TEXT', {'blocks': [
        {'block_index': 7, 'text': 'Our plant can manufacture 100 widgets per quarter.',
         'raw_start_byte': 0, 'raw_end_byte': 52, 'raw_span_sha256': 'sha256:' + '2' * 64,
         'html_quotation_context': False}]}, 0)]
    body = {'record_type': 'B13_COMPLETE_SEMANTIC_SOURCE', 'source_serialization_complete': True,
        'company_id': 'enphase_energy', 'units': units, 'required_unit_ids': [u['unit_id'] for u in units],
        'documents': [{'document_id': doc, 'filing': {'form': '10-K'}, 'registrant_name_binding': {}}],
        'prepared_annual_input': {'entity': '1463101', 'table_input': {'target_period': {}},
                                  'fiscal_year_label_resolution': {k: None for k in
                                    ('selected_fiscal_year', 'basis', 'original_dei_fiscal_year',
                                     'original_companyfacts_fiscal_year_values', 'metadata_conflict_retained')}},
        'capacity_navigation': [{'unit_id': units[0]['unit_id'], 'kind': 'VISIBLE_BLOCK', 'source_index': 7}],
        'native_capacity_role_assessments': []}
    return {**body, 'semantic_source_id': content_hash(value=body)}


def response_for(request):
    return {'request_id': request['request_id'], 'units': [
        {'unit_id': request['units'][0]['unit_id'], 'reviewed': True, 'unresolved': [], 'findings': [
            {'kind': 'AVAILABLE_CAPACITY', 'subject': 'TARGET_REGISTRANT', 'timing': 'CURRENT_REPORT',
             'reason': 'Quarterly widget manufacturing capacity only; no actual production amount.',
             'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': 7,
                           'text': 'Our plant can manufacture 100 widgets per quarter.'}]}]}]}


class CapacitySemanticReviewTest(unittest.TestCase):
    def test_sales_only_source_cannot_be_labelled_actual_production(self):
        source = source_packet()
        old = source['units'][0]
        payload = deepcopy(old['payload'])
        payload['blocks'][0]['text'] = 'We sold 6.4 million units and shipped 706.1 MWh of batteries.'
        unit = _seal_unit(old['document_id'], 'VISIBLE_TEXT', payload, 0)
        source['units'] = [unit]; source['required_unit_ids'] = [unit['unit_id']]
        source['capacity_navigation'][0]['unit_id'] = unit['unit_id']
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        request = requests_from_source(source)[0]
        response = response_for(request)
        finding = response['units'][0]['findings'][0]
        finding['evidence'][0]['text'] = payload['blocks'][0]['text']
        finding['kind'] = 'ACTUAL_PRODUCTION'
        with self.assertRaisesRegex(ValueError, 'SALES_ONLY_SOURCE_IS_NOT_ACTUAL_PRODUCTION'):
            validate_response(request=request, raw_response=_bytes(response))
        finding['kind'] = 'SALES_OR_SHIPMENTS'
        validate_response(request=request, raw_response=_bytes(response))

    def test_complete_source_and_exact_quotes_required(self):
        request = requests_from_source(source_packet())[0]
        response = response_for(request)
        checked = validate_response(request=request, raw_response=_bytes(response))
        self.assertEqual(checked['response'], response)
        self.assertFalse(checked['semantic_correctness_verified'])
        for mutate in ('omit_unit', 'omit_candidate', 'invent_quote', 'wrong_request'):
            bad = deepcopy(response)
            if mutate == 'omit_unit': bad['units'] = []
            if mutate == 'omit_candidate': bad['units'][0]['findings'] = []
            if mutate == 'invent_quote': bad['units'][0]['findings'][0]['evidence'][0]['text'] = 'Produced 100 widgets.'
            if mutate == 'wrong_request': bad['request_id'] = 'other'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_response(request=request, raw_response=_bytes(bad))

    def test_shared_metadata_is_restored_and_conflicts_rejected(self):
        ns = {'x': 'urn:test'}
        env = content_hash(value=ns)
        context = {'raw_xml': '<context id="c">2025</context>', 'namespace_environment_id': env}
        payload = {'facts': [], 'contexts': {'c': context}, 'units': {}, 'namespace_environments': {env: ns}}
        units = [_seal_unit('doc', 'NATIVE_FACTS', deepcopy(payload), i) for i in range(2)]
        packed, shared = _shared_units(units)
        self.assertEqual(_restore_units(packed, shared), units)
        shared['contexts']['c']['raw_xml'] = 'changed'
        self.assertNotEqual(_restore_units(packed, shared), units)
        bad = deepcopy(units)
        bad[1]['payload']['contexts']['c']['raw_xml'] = 'collision'
        with self.assertRaisesRegex(ValueError, 'COLLISION'):
            _shared_units(bad)

    def test_source_unit_missing_from_declared_census_rejected(self):
        source = source_packet()
        source['required_unit_ids'] = []
        source['semantic_source_id'] = content_hash(value={k: v for k, v in source.items() if k != 'semantic_source_id'})
        with self.assertRaisesRegex(ValueError, 'UNIT_SET_CHANGED'):
            requests_from_source(source)


class CapacitySemanticReviewMaterialTest(unittest.TestCase):
    def test_complete_saved_packages_restore_without_navigation_filter(self):
        path = ROOT / 'docs/evidence/issue28_continuous/resume-2026-09-14/b13-complete-source.tar.gz'
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                source = json.load(archive.extractfile(member))
                requests = requests_from_source(source)
                self.assertEqual(requests, requests_from_source(json.loads(json.dumps(source, sort_keys=True))))
                units = [u for request in requests for u in _restore_units(
                    request['units'], request['shared_source_dictionaries'])]
                self.assertEqual(units, source['units'])
                self.assertLess(len(requests), len(units))
                original = sum(len(_bytes(u)) for u in units)
                packed = sum(len(_bytes([r['units'], r['shared_source_dictionaries']])) for r in requests)
                self.assertLess(packed, original)
                print(member.name, {'original_units': len(units), 'requests': len(requests),
                                    'original_bytes': original, 'shared_bytes': packed})


if __name__ == '__main__':
    unittest.main()
