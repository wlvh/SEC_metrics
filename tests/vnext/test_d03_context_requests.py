from copy import deepcopy
import unittest

from vnext.canonical import content_hash, sha256_bytes
from vnext.d03_context_requests import resolve_context_requests, replay_context_packet
from vnext.native_unit_index import evidence_json_bytes
from vnext.r6_semantic_source import _bytes


class D03ContextRequestsTest(unittest.TestCase):
    def setUp(self):
        self.visible = self.unit('VISIBLE_TEXT', {'blocks': [
            {'block_index': 5, 'text': 'A government inquiry continues\u037e',
             'html_quotation_context': False},
            {'block_index': 6, 'text': 'The other proceeding ended.',
             'html_quotation_context': False}]})
        self.fact = self.unit('NATIVE_FACTS', {'facts': [{
            'attributes': {'id': 'f1', 'continuedat': 'continued'},
            'namespace_environment_id': 'env', 'expanded_concept': ['uri', 'Note'],
            'fact': {'ordinal': 9, 'context_ref': 'c1', 'unit_ref': '', 'text': 'First part'}}],
            'contexts': {'c1': {'raw_xml': '<context>2025</context>', 'namespace_environment_id': 'env'}}, 'units': {},
            'namespace_environments': {'env': {'ix': 'inline-uri'}}})
        root_raw = '<outer><continued id="continued">exact\u037e</continued></outer>'
        a, b = root_raw.index('<continued'), root_raw.index('</continued>') + len('</continued>')
        nested = {'attributes': {'id': 'continued'}, 'relative_start_character': a,
            'relative_end_character': b, 'namespaces': {'ix': 'inline-uri'},
            'raw_xml_sha256': sha256_bytes(content=root_raw[a:b].encode())}
        self.supp = self.unit('NATIVE_SUPPLEMENTS', {'objects': [{
            'attributes': {'id': 'outer'}, 'raw_xml': root_raw,
            'raw_xml_sha256': sha256_bytes(content=root_raw.encode()),
            'namespaces': {'ix': 'inline-uri'}, 'nested_objects': [nested]}]})
        self.source = self.seal([self.visible, self.fact, self.supp])
        self.anchor = {'unit_id': self.fact['unit_id'], 'kind': 'NATIVE_FACT', 'source_index': 9}

    def unit(self, kind, payload, document='doc:one'):
        raw = _bytes(payload)
        body = {'document_id': document, 'kind': kind, 'ordinal': 0, 'payload': payload,
                'payload_bytes': len(raw), 'payload_sha256': sha256_bytes(content=raw)}
        return {**body, 'unit_id': content_hash(value=body)}

    def seal(self, units):
        body = {'metric_id': 'D03', 'company_id': 'synthetic-only',
            'documents': [{'document_id': doc} for doc in sorted({u['document_id'] for u in units})],
            'units': units, 'required_unit_ids': [u['unit_id'] for u in units],
            'source_serialization_complete': True}
        return {**body, 'semantic_source_id': content_hash(value=body)}

    def run_requests(self, requests, source=None, **caps):
        s = self.source if source is None else source
        return resolve_context_requests(source=s,
            expected_source_sha256=sha256_bytes(content=evidence_json_bytes(s)),
            responsibility_unit_ids=[self.fact['unit_id']], requests=requests, **caps)

    def xml(self, element_id='continued'):
        return {'anchor': self.anchor, 'target': {'kind': 'XML_ELEMENT_ID', 'element_id': element_id}}

    def test_nested_xml_and_fact_context_are_exact_parts_not_new_owners(self):
        packet = self.run_requests([self.xml(), self.xml('f1')])
        xml, fact = [r['context'][0] for r in packet['rows']]
        self.assertEqual(xml['raw_xml'], '<continued id="continued">exact\u037e</continued>')
        self.assertEqual(xml['original_unit_id'], self.supp['unit_id'])
        self.assertEqual(fact['context'], self.fact['payload']['contexts']['c1'])
        self.assertEqual(fact['original_item'], self.fact['payload']['facts'][0])
        self.assertEqual(packet['responsibility_unit_ids'], [self.fact['unit_id']])
        self.assertFalse(packet['semantic_acceptance'])
        self.assertFalse(packet['company_result_created'])

    def test_fact_context_and_unit_keep_separate_namespace_dependencies_and_caps(self):
        payload = deepcopy(self.fact['payload'])
        payload['facts'][0]['fact']['unit_ref'] = 'u1'
        payload['contexts']['c1'] = {'raw_xml': '<xbrli:context id="c1"/>',
                                     'namespace_environment_id': 'context-env'}
        payload['units']['u1'] = {'raw_xml': '<xbrli:unit><xbrli:measure>z:USD</xbrli:measure></xbrli:unit>',
                                  'namespace_environment_id': 'unit-env'}
        payload['namespace_environments'] = {'env': {'z': 'urn:fact'},
            'context-env': {'xbrli': 'urn:context'},
            'unit-env': {'xbrli': 'urn:unit', 'z': 'urn:currency'}}
        dependency_unit = self.unit('NATIVE_FACTS', payload)
        source = self.seal([self.visible, dependency_unit, self.supp])
        old_fact, old_anchor = self.fact, self.anchor
        self.fact = dependency_unit
        self.anchor = {**self.anchor, 'unit_id': dependency_unit['unit_id']}
        try:
            packet = self.run_requests([self.xml('f1')], source)
            context = packet['rows'][0]['context'][0]
            self.assertEqual(context['namespace_environments'], payload['namespace_environments'])
            self.assertEqual(context['namespace_environments'][context['unit']['namespace_environment_id']]['z'],
                             'urn:currency')
            before_fix_shape = {k: v for k, v in context.items() if k != 'namespace_environments'}
            cap = len(evidence_json_bytes([before_fix_shape]))
            capped = self.run_requests([self.xml('f1')], source, max_context_bytes=cap)
            self.assertEqual(capped['rows'][0]['reason'], 'D03_CONTEXT_BYTE_LIMIT')
            broken = deepcopy(payload); del broken['namespace_environments']['unit-env']
            broken_unit = self.unit('NATIVE_FACTS', broken)
            with self.assertRaisesRegex(ValueError, 'DICTIONARY_MISSING'):
                self.run_requests([self.xml('f1')], self.seal([self.visible, dependency_unit, broken_unit, self.supp]))
        finally:
            self.fact, self.anchor = old_fact, old_anchor

    def test_complete_visible_range_keeps_original_text_and_indices(self):
        packet = self.run_requests([{'anchor': self.anchor,
            'target': {'kind': 'VISIBLE_BLOCK_RANGE', 'first': 5, 'last': 6}}])
        context = packet['rows'][0]['context']
        self.assertEqual([c['original_item'] for c in context], self.visible['payload']['blocks'])
        self.assertEqual([c['source_index'] for c in context], [5, 6])

    def test_missing_and_other_document_do_not_get_guessed(self):
        other = self.unit('VISIBLE_TEXT', {'blocks': [{'block_index': 99, 'text': 'elsewhere'}]}, 'doc:two')
        source = self.seal([*self.source['units'], other])
        packet = self.run_requests([self.xml('absent'), {'anchor': self.anchor,
            'target': {'kind': 'VISIBLE_BLOCK_RANGE', 'first': 99, 'last': 99}}], source)
        self.assertEqual([r['reason'] for r in packet['rows']], ['D03_CONTEXT_LOCATION_MISSING'] * 2)
        self.assertTrue(all(r['context'] is None for r in packet['rows']))

    def test_duplicate_xml_id_is_unresolved_not_last_match_wins(self):
        changed = deepcopy(self.fact['payload']); changed['facts'][0]['fact']['ordinal'] = 10
        extra = self.unit('NATIVE_FACTS', changed)
        packet = self.run_requests([self.xml('f1')], self.seal([*self.source['units'], extra]))
        self.assertEqual(packet['rows'][0]['reason'], 'D03_CONTEXT_LOCATION_AMBIGUOUS')

    def test_limits_retain_unresolved_request_without_partial_context(self):
        request = {'anchor': self.anchor,
            'target': {'kind': 'VISIBLE_BLOCK_RANGE', 'first': 5, 'last': 6}}
        for caps, reason in [({'max_visible_blocks': 1}, 'D03_CONTEXT_BLOCK_LIMIT'),
                             ({'max_context_bytes': 1}, 'D03_CONTEXT_BYTE_LIMIT')]:
            packet = self.run_requests([request], **caps)
            self.assertEqual(packet['rows'][0], {'request': request, 'status': 'UNRESOLVED',
                'reason': reason, 'context': None})
        packet = self.run_requests([self.xml(), self.xml('f1')])
        first_bytes = len(evidence_json_bytes(packet['rows'][0]['context']))
        capped = self.run_requests([self.xml(), self.xml('f1')], max_context_bytes=first_bytes)
        self.assertEqual(capped['rows'][0]['status'], 'LOCATED')
        self.assertEqual(capped['rows'][1]['reason'], 'D03_CONTEXT_BYTE_LIMIT')
        with self.assertRaisesRegex(ValueError, 'REQUEST_LIMIT'):
            self.run_requests([self.xml(), self.xml('f1')], max_requests=1)

    def test_foreign_anchor_boolean_index_and_unbounded_target_refused(self):
        for request, reason in [
            ({'anchor': {**self.anchor, 'unit_id': self.supp['unit_id']}, 'target': self.xml()['target']}, 'NOT_OWNED'),
            ({'anchor': {**self.anchor, 'source_index': True}, 'target': self.xml()['target']}, 'ANCHOR_CHANGED'),
            ({'anchor': self.anchor, 'target': {'kind': 'WHOLE_SOURCE'}}, 'TARGET_KIND'),
            ({'anchor': self.anchor, 'target': {'kind': 'VISIBLE_BLOCK_RANGE', 'first': True, 'last': 6}}, 'TARGET_SHAPE')]:
            with self.assertRaisesRegex(ValueError, reason):
                self.run_requests([request])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_REQUEST'):
            self.run_requests([self.xml(), self.xml()])

    def test_external_source_and_unit_identity_cannot_be_resigned_locally(self):
        changed = deepcopy(self.source); changed['units'][0]['payload']['blocks'][0]['text'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            resolve_context_requests(source=changed,
                expected_source_sha256=sha256_bytes(content=evidence_json_bytes(self.source)),
                responsibility_unit_ids=[self.fact['unit_id']], requests=[self.xml()])
        changed = self.seal(changed['units'])
        with self.assertRaisesRegex(ValueError, 'UNIT_CHANGED'):
            self.run_requests([self.xml()], changed)

    def test_cold_replay_rebuilds_context_and_refuses_even_resigned_tampering(self):
        packet = self.run_requests([self.xml()])
        args = {'source': self.source,
                'expected_source_sha256': sha256_bytes(content=evidence_json_bytes(self.source))}
        self.assertEqual(replay_context_packet(packet=packet,
            expected_packet_sha256=sha256_bytes(content=evidence_json_bytes(packet)), **args), packet)
        changed = deepcopy(packet); changed['rows'][0]['context'][0]['raw_xml'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'PACKET_CHANGED'):
            replay_context_packet(packet=changed,
                expected_packet_sha256=sha256_bytes(content=evidence_json_bytes(packet)), **args)
        with self.assertRaisesRegex(ValueError, 'REPLAY_CHANGED'):
            replay_context_packet(packet=changed,
                expected_packet_sha256=sha256_bytes(content=evidence_json_bytes(changed)), **args)


if __name__ == '__main__':
    unittest.main()
