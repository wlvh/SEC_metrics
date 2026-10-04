from copy import deepcopy
import unittest

import logical_source as logical
from tests.vnext.test_d03_context_requests import D03ContextRequestsTest
from vnext.canonical import sha256_bytes
from vnext.native_unit_index import evidence_json_bytes


class LogicalContinuationTest(unittest.TestCase):
    def setUp(self):
        self.f = D03ContextRequestsTest()
        self.f.setUp()
        p = deepcopy(self.f.fact['payload'])
        p['facts'][0]['fact']['tag'] = 'ix:nonnumeric'
        self.fact = self.f.unit('NATIVE_FACTS', p)
        self.supplement = deepcopy(self.f.supp['payload'])
        nested = self.supplement['objects'][0]['nested_objects'][0]
        nested.update(local_name='continuation', namespace='inline-uri')
        self.anchor = {'unit_id': self.fact['unit_id'], 'kind': 'NATIVE_FACT', 'source_index': 9}

    def source(self, supplement=None, extra=()):
        s = self.f.seal([self.f.visible, self.fact,
                         self.f.unit('NATIVE_SUPPLEMENTS', self.supplement if supplement is None else supplement), *extra])
        return s, sha256_bytes(content=evidence_json_bytes(s))

    def result(self, supplement=None, extra=()):
        s, d = self.source(supplement, extra)
        return logical.assemble(s, d, [self.anchor])

    def test_literal_chain_preserves_unicode_bytes_and_namespace_context(self):
        s, digest = self.source()
        out = logical.assemble(s, digest, [self.anchor])
        r = out['rows'][0]
        self.assertEqual(r['status'], 'COMPLETE_XML_CHAIN')
        self.assertEqual(r['segments'][0]['raw_xml'], '<continued id="continued">exact\u037e</continued>')
        self.assertEqual(r['original_anchor_item']['context'], self.fact['payload']['contexts']['c1'])
        self.assertEqual(out['physical_segments_total'], 1)
        self.assertEqual(out['original_required_unit_ids'], s['required_unit_ids'])
        self.assertFalse(out['full_original_scope_covered'])
        self.assertFalse(out['semantic_acceptance'])
        self.assertFalse(out['old_eight_location_contract_changed'])
        self.assertEqual(logical.replay(s, digest, out, sha256_bytes(content=evidence_json_bytes(out))), out)

    def test_dangling_cycle_wrong_namespace_and_wrong_kind_are_specific_unresolved(self):
        for attrs, metadata, expected in [
            ({'continuedat': 'missing'}, {}, 'CONTINUATION_MISSING'),
            ({'continuedat': 'continued'}, {}, 'CONTINUATION_CYCLE'),
            ({'continuedat': 'f1'}, {}, 'CONTINUATION_CYCLE'),
            ({}, {'namespace': 'other-uri'}, 'CONTINUATION_WRONG_ELEMENT'),
            ({}, {'local_name': 'footnote'}, 'CONTINUATION_WRONG_ELEMENT')]:
            with self.subTest(expected=expected):
                p = deepcopy(self.supplement); n = p['objects'][0]['nested_objects'][0]
                n['attributes'].update(attrs); n.update(metadata)
                r = self.result(p)['rows'][0]
                self.assertEqual(r['status'], 'UNRESOLVED')
                self.assertEqual(r['unresolved_reason'], expected)

    def test_duplicate_target_and_foreign_document_do_not_pick_a_match(self):
        other = self.f.unit('NATIVE_SUPPLEMENTS', deepcopy(self.supplement), 'doc:two')
        self.assertEqual(self.result(extra=(other,))['rows'][0]['status'], 'COMPLETE_XML_CHAIN')
        duplicate = deepcopy(self.supplement)
        duplicate['objects'][0]['attributes']['id'] = 'different-outer'
        extra = self.f.unit('NATIVE_SUPPLEMENTS', duplicate)
        self.assertEqual(self.result(extra=(extra,))['rows'][0]['unresolved_reason'], 'CONTINUATION_AMBIGUOUS')
        s = self.f.seal([self.fact, other]); d = sha256_bytes(content=evidence_json_bytes(s))
        self.assertEqual(logical.assemble(s, d, [self.anchor])['rows'][0]['unresolved_reason'], 'CONTINUATION_MISSING')

    def test_source_anchor_raw_slice_and_packet_tampering_refused(self):
        s, d = self.source()
        changed = deepcopy(s); changed['units'][0]['payload']['blocks'][0]['text'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            logical.assemble(changed, d, [self.anchor])
        for anchor in [dict(self.anchor, source_index=True), dict(self.anchor, source_index=99)]:
            with self.assertRaises(ValueError): logical.assemble(s, d, [anchor])
        with self.assertRaisesRegex(ValueError, 'ANCHOR_DUPLICATE'):
            logical.assemble(s, d, [self.anchor, self.anchor])
        p = deepcopy(self.supplement); p['objects'][0]['nested_objects'][0]['raw_xml_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'XML_SLICE_CHANGED'): self.result(p)
        out = logical.assemble(s, d, [self.anchor]); expected = sha256_bytes(content=evidence_json_bytes(out))
        out['rows'][0]['segments'][0]['raw_xml'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'PACKET_CHANGED'): logical.replay(s, d, out, expected)


if __name__ == '__main__':
    unittest.main()
