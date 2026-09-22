"""Strict successor ownership; old nested failures and interpretation stay intact."""
from copy import deepcopy
import unittest

from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.canonical import canonical_json_bytes, content_hash, strict_json_loads
from vnext.capacity_program_roles import program_source
from vnext.capacity_reference_contract import upgrade_request, restore_base_request, restore_response
from vnext.capacity_semantic_review import requests_from_source, validate_response
from vnext.r6_semantic_source import _seal_unit


def fixture():
    source, _ = quantity_source('<p>Our products are sold worldwide.</p>'
                               '<p>Our contract manufacturers have sufficient production capacity for anticipated demand.</p>')
    old = source['units'][0]
    units = [_seal_unit(old['document_id'], 'VISIBLE_TEXT', {'blocks': [block]}, index)
             for index, block in enumerate(old['payload']['blocks'])]
    source.update(units=units, required_unit_ids=[u['unit_id'] for u in units], capacity_navigation=[])
    source['documents'][0]['source_unit_ids'] = source['required_unit_ids']
    source['semantic_source_id'] = content_hash(value={k: v for k, v in source.items() if k != 'semantic_source_id'})
    source = program_source(source)
    base = requests_from_source(source)[0]
    owner = next(i for i, u in enumerate(units) if 'anticipated demand' in u['payload']['blocks'][0]['text'])
    finding = {'kind': 'CAPACITY_QUALITATIVE', 'subject': 'TARGET_REGISTRANT', 'timing': 'CURRENT_REPORT',
               'reason': 'Original qualitative statement, with no production quantity.',
               'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': units[owner]['payload']['blocks'][0]['block_index']}]}
    response = {'units': [{'unit_index': i, 'reviewed': True, 'unresolved': [], 'calculation_limits': []}
                          for i in range(len(units))], 'findings': [finding]}
    return source, base, response, owner


class CapacityReferenceContractTest(unittest.TestCase):
    def setUp(self):
        self.source, self.base, self.response, self.owner = fixture()
        self.request = upgrade_request(self.base)

    def decode(self, response=None):
        return restore_response(request=self.request,
                                raw_response=canonical_json_bytes(value=self.response if response is None else response))

    def test_flat_identity_roundtrip_preserves_prompt_source_and_semantics(self):
        before = deepcopy(self.base)
        base, raw, original = self.decode()
        self.assertEqual(restore_base_request(self.request), self.base)
        self.assertEqual(base, before)
        self.assertEqual(self.request['system_prompt'], self.base['system_prompt'])
        self.assertEqual(self.request['units'], self.base['units'])
        self.assertEqual(original, self.response)
        normalized = strict_json_loads(text=raw.decode())
        self.assertEqual(normalized['units'][self.owner]['findings'], self.response['findings'])
        checked = validate_response(request=base, raw_response=raw, source=self.source)
        self.assertEqual(checked['findings'][0]['unit_id'], base['units'][self.owner]['unit_id'])
        self.assertEqual(checked['unresolved'], [])

    def test_old_cross_unit_response_still_fails_and_is_not_relocated(self):
        base, raw, _ = self.decode()
        old = strict_json_loads(text=raw.decode())
        old['units'][(self.owner + 1) % len(old['units'])]['findings'] = old['units'][self.owner]['findings']
        old['units'][self.owner]['findings'] = []
        original = deepcopy(old)
        with self.assertRaisesRegex(ValueError, 'B13_REFERENCE_OUTSIDE_SUPPLIED_SOURCE'):
            validate_response(request=base, raw_response=canonical_json_bytes(value=old), source=self.source)
        with self.assertRaisesRegex(ValueError, 'RESPONSE_CENSUS_CHANGED'):
            self.decode(old)
        self.assertEqual(old, original)

    def test_unknown_kind_index_boolean_empty_and_extra_evidence_rejected(self):
        for evidence in ([{'kind': 'VISIBLE_BLOCK', 'source_index': 999999}],
                         [{'kind': 'NATIVE_FACT', 'source_index': self.response['findings'][0]['evidence'][0]['source_index']}],
                         [{'kind': 'VISIBLE_BLOCK', 'source_index': True}], [],
                         [{'kind': 'VISIBLE_BLOCK', 'source_index': 0, 'unit_index': 0}]):
            bad = deepcopy(self.response); bad['findings'][0]['evidence'] = evidence
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.decode(bad)

    def test_missing_duplicate_and_unreviewed_units_are_rejected(self):
        for change in ('missing', 'duplicate', 'boolean', 'not_reviewed', 'nested'):
            bad = deepcopy(self.response)
            if change == 'missing': bad['units'].pop()
            elif change == 'duplicate': bad['units'][-1] = deepcopy(bad['units'][0])
            elif change == 'boolean': bad['units'][0]['unit_index'] = False
            elif change == 'not_reviewed': bad['units'][0]['reviewed'] = False
            else: bad['units'][0]['findings'] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                base, raw, _ = self.decode(bad)
                validate_response(request=base, raw_response=raw, source=self.source)

    def test_cross_unit_and_duplicate_findings_or_evidence_are_rejected(self):
        for change in ('cross_unit', 'duplicate_finding', 'duplicate_evidence'):
            bad = deepcopy(self.response)
            if change == 'cross_unit':
                other = self.source['units'][(self.owner + 1) % len(self.source['units'])]
                bad['findings'][0]['evidence'].append({'kind': 'VISIBLE_BLOCK', 'source_index': other['payload']['blocks'][0]['block_index']})
            elif change == 'duplicate_finding': bad['findings'].append(deepcopy(bad['findings'][0]))
            else: bad['findings'][0]['evidence'] *= 2
            with self.subTest(change=change), self.assertRaises(ValueError): self.decode(bad)

    def test_resealed_ambiguity_foreign_document_and_protocol_are_rejected(self):
        from vnext.capacity_semantic_review import _shared_units
        for change in ('ambiguous', 'foreign'):
            units = deepcopy(self.source['units'])
            if change == 'ambiguous': units.append(deepcopy(units[0]))
            else: units[-1]['document_id'] = 'sha256:' + '9' * 64
            bad = deepcopy(self.base)
            bad['units'], bad['shared_source_dictionaries'] = _shared_units(units)
            bad['request_id'] = content_hash(value={k: v for k, v in bad.items() if k != 'request_id'})
            with self.subTest(change=change), self.assertRaises(ValueError): upgrade_request(bad)
        bad = deepcopy(self.request)
        bad['response_protocol']['finding_reference_scope'] = 'Accept any source.'
        bad['request_id'] = content_hash(value={k: v for k, v in bad.items() if k != 'request_id'})
        with self.assertRaisesRegex(ValueError, 'MAPPING_CHANGED'): restore_base_request(bad)

    def test_reordered_status_rows_do_not_change_reference_owner(self):
        bad = deepcopy(self.response)
        bad['units'].reverse()
        self.assertEqual(self.decode()[1], self.decode(bad)[1])

    def test_unsupported_base_and_extra_top_level_identity_are_rejected(self):
        for field, value in [('record_type', 'D04_NATIVE_INTERPRETATION_REQUEST'),
                             ('program_quantity_role_contract_version', None)]:
            bad = deepcopy(self.base); bad[field] = value
            bad['request_id'] = content_hash(value={k: v for k, v in bad.items() if k != 'request_id'})
            with self.subTest(field=field), self.assertRaises(ValueError): upgrade_request(bad)
        bad = deepcopy(self.response); bad['request_id'] = self.request['request_id']
        with self.assertRaises(ValueError): self.decode(bad)

    def test_native_acceptance_and_partition_reconstruct_exact_variant(self):
        from tests.vnext.test_capacity_program_roles import acceptance
        from vnext.native_unit_index import reconstruct_requests, validate_request_partition
        from vnext.capacity_reference_contract import VERSION
        checked = validate_response(request=self.request, raw_response=canonical_json_bytes(value=self.response), source=self.source)
        self.assertEqual(checked['request_id'], self.request['request_id'])
        self.assertEqual(checked['response'], self.response)
        result = acceptance(self.source, self.request, self.response)
        self.assertEqual(result['evidence_status'], 'PASS')
        self.assertEqual(validate_request_partition(self.source, [self.request]), [VERSION])
        self.assertEqual(reconstruct_requests(self.source, [VERSION]), [self.request])
        missing = deepcopy(self.response); missing['units'].pop()
        with self.assertRaises(ValueError): acceptance(self.source, self.request, missing)

    def test_code_identity_alone_does_not_authorize_another_reference_draw(self):
        from types import SimpleNamespace
        from vnext.continuous_semantic_calls import request_digest
        policy = SimpleNamespace(model='deepseek-flash')
        changed = deepcopy(self.base)
        changed['source_id'] = content_hash(value='Only runtime/provenance identity changed')
        changed['request_id'] = content_hash(value={k:v for k,v in changed.items() if k != 'request_id'})
        other = upgrade_request(changed)
        self.assertNotEqual(other['request_id'], self.request['request_id'])
        self.assertEqual(request_digest(other, policy), request_digest(self.request, policy))
        self.assertNotEqual(request_digest(self.base, policy), request_digest(self.request, policy))
