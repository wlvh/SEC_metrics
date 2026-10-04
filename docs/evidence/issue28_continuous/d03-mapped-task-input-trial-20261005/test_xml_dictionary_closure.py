from copy import deepcopy
import unittest

import task_mapping as mapping
from vnext.capacity_semantic_review import _shared_units, _restore_units


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


if __name__=='__main__':unittest.main()
