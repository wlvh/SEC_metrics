from copy import deepcopy
import unittest

import task_mapping as mapping
from vnext.capacity_semantic_review import _shared_units, _restore_units
from tests.vnext.test_d03_context_requests import D03ContextRequestsTest
from vnext.canonical import sha256_bytes
from vnext.native_unit_index import evidence_json_bytes


class XMLDictionaryClosureTest(unittest.TestCase):
    def setUp(self):
        self.source = {'units': [{'kind': 'NATIVE_FACTS', 'document_id': 'same-doc', 'unit_id': 'original-donor',
            'payload': {'facts': [], 'contexts': {
                'c2': {'raw_xml': '<context id="c2">exact\u037e</context>', 'namespace_environment_id': 'context-env'}},
                'units': {'u2': {'raw_xml': '<unit id="u2"><measure>m:USD</measure></unit>', 'namespace_environment_id': 'unit-env'}},
                'namespace_environments': {'context-env': {'ix':'inline'}, 'unit-env': {'m':'currency'}}}}]}
        self.parts = [{'kind':'NATIVE_SUPPLEMENTS','document_id':'same-doc','parent_source_unit_id':'original-root',
            'original_indices':[0],'payload':{'objects':[{'raw_xml':'<outer><ix:nonFraction contextRef="c2" unitRef="u2">10</ix:nonFraction></outer>',
                'namespaces':{'ix':'inline'},'namespace_environment_id':'root-env','nested_objects':[]}]}}]

    def test_nested_context_unit_and_separate_namespaces_retained_without_extra_owner(self):
        original = deepcopy(self.source); parts = deepcopy(self.parts)
        mapping._complete_xml_dictionaries(self.source, parts)
        self.assertEqual(len(parts),2)
        donor=parts[1]
        self.assertEqual(donor['parent_source_unit_id'],'original-donor')
        self.assertNotIn('unit_id',donor)
        self.assertTrue(donor['dictionary_context_only'])
        self.assertEqual(donor['original_indices'],[])
        self.assertEqual(donor['payload']['facts'],[])
        self.assertEqual(donor['payload'],self.source['units'][0]['payload'])
        packed,shared=_shared_units(parts)
        self.assertEqual(_restore_units(packed,shared),parts)
        self.assertIn('\u037e',shared['contexts']['c2']['raw_xml'])
        self.assertEqual(self.source,original)

    def test_equal_repeated_definitions_are_one_donor_not_duplicate_roles(self):
        self.source['units'].append(deepcopy(self.source['units'][0]))
        self.source['units'][1]['unit_id']='second-identical-source-unit'
        mapping._complete_xml_dictionaries(self.source,self.parts)
        self.assertEqual(len(self.parts),2)
        mapping._complete_xml_dictionaries(self.source,self.parts)
        self.assertEqual(len(self.parts),2)

    def test_missing_conflicting_and_namespace_missing_dependencies_stop(self):
        for change,expected in [('missing','DEPENDENCY_MISSING'),('conflicting','DEPENDENCY_CONFLICT'),('namespace','NAMESPACE_MISSING')]:
            with self.subTest(change=change):
                s=deepcopy(self.source)
                if change=='missing':s['units'][0]['payload']['contexts'].clear()
                elif change=='conflicting':
                    extra=deepcopy(s['units'][0]);extra['payload']['contexts']['c2']['raw_xml']='different';s['units'].append(extra)
                else:s['units'][0]['payload']['namespace_environments'].clear()
                with self.assertRaisesRegex(ValueError,expected):mapping._complete_xml_dictionaries(s,deepcopy(self.parts))

    def test_already_present_distinct_namespace_missing_is_rejected_by_actual_prepare(self):
        fixture=D03ContextRequestsTest();fixture.setUp()
        fact=deepcopy(fixture.fact['payload'])
        fact['facts'][0]['attributes'].pop('continuedat')
        fact['facts'][0]['fact']['tag']='ix:nonnumeric'
        fact['contexts']['c1']['namespace_environment_id']='context-only-env'
        raw='<outer><ix:nonnumeric contextRef="c1">same source text</ix:nonnumeric></outer>'
        supp={'objects':[{'attributes':{'id':'outer'},'raw_xml':raw,
            'raw_xml_sha256':sha256_bytes(content=raw.encode()),'nested_objects':[],
            'namespace_environment_id':'env','namespaces':{'ix':'inline-uri'}}]}
        for defined in (False,True):
            with self.subTest(namespace_defined=defined):
                payload=deepcopy(fact)
                if defined:payload['namespace_environments']['context-only-env']={'xbrli':'context-uri'}
                f=fixture.unit('NATIVE_FACTS',payload);x=fixture.unit('NATIVE_SUPPLEMENTS',supp)
                source=fixture.seal([fixture.visible,f,x]);digest=sha256_bytes(content=evidence_json_bytes(source))
                table=mapping.census(source,digest);owned=[r for r in table['refs'] if r[1]!='VISIBLE_BLOCK']
                if not defined:
                    with self.assertRaisesRegex(ValueError,'XML_DICTIONARY_NAMESPACE_MISSING'):
                        mapping.prepare(source,digest,table,owned)
                else:
                    task=mapping.prepare(source,digest,table,owned)
                    self.assertIn('context-only-env',task['payload']['shared_native_dictionaries']['namespace_environments'])


if __name__=='__main__':unittest.main()
