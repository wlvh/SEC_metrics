from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import task_mapping as mapping
from test_logical_source import LogicalContinuationTest
from vnext.canonical import sha256_bytes
from vnext.capacity_semantic_review import _restore_units
from vnext.native_unit_index import evidence_json_bytes


class CompleteTaskMappingTest(unittest.TestCase):
    def setUp(self):
        self.base = LogicalContinuationTest(); self.base.setUp()
        for obj in self.base.supplement['objects']:
            obj['namespace_environment_id'] = 'env'
            for n in obj['nested_objects']: n['namespace_environment_id'] = 'env'
        self.source, self.digest = self.base.source()

    def reseal(self, units):
        s = self.base.f.seal(units)
        return s, sha256_bytes(content=evidence_json_bytes(s))

    def measurement(self, body, **kw):
        p = json.loads(json.loads(body)['messages'][1]['content'])
        n = len(p['owned_references'])
        return {'fits': n <= 2, 'context_tokens': 100 if n <= 2 else 250000}

    def test_every_original_item_once_and_shared_context_not_owned_twice(self):
        before = evidence_json_bytes(self.source)
        with patch.object(mapping, 'measure_request', return_value={'fits': True, 'context_tokens': 100}):
            p = mapping.plan(self.source, self.digest)
        self.assertTrue(p['complete_owner_mapping']); self.assertEqual(p['status'], 'ALL_INPUTS_FIT')
        all_refs = [r for t in p['tasks'] for r in t['owned_references']]
        self.assertEqual(len(all_refs), len(set(all_refs)))
        self.assertEqual(len(all_refs), 4)
        self.assertEqual(p['proposed_initial_request_count'], 3)
        for task in p['tasks']:
            payload = task['payload']
            self.assertEqual([row[2] for row in payload['complete_visible_context']],
                             [b['text'] for b in self.source['units'][0]['payload']['blocks']])
            for part in _restore_units(payload['native_partial_views'], payload['shared_native_dictionaries']):
                self.assertNotIn('unit_id', part)
                original = next(u for u in self.source['units'] if u['unit_id'] == part['parent_source_unit_id'])
                field = 'facts' if part['kind'] == 'NATIVE_FACTS' else 'objects'
                original_values = original['payload'][field]
                self.assertTrue(all(v in original_values for v in part['payload'][field]))
            self.assertFalse(payload['semantic_acceptance'])
        self.assertEqual(evidence_json_bytes(self.source), before)
        self.assertFalse(p['live_permission']); self.assertEqual(p['additional_call_opportunities_granted'], 0)

    def test_complete_chains_and_fact_footnote_context_keep_original_dependencies(self):
        supp = deepcopy(self.base.supplement)
        for local, attrs, raw in [
            ('relationship', {'fromrefs': 'f1', 'torefs': 'fn1'}, '<relationship fromrefs="f1" torefs="fn1"/>'),
            ('footnote', {'id': 'fn1'}, '<footnote id="fn1">reported\u037e fact context</footnote>')]:
            supp['objects'].append({'local_name': local, 'namespace': 'inline-uri', 'attributes': attrs,
                'raw_xml': raw, 'raw_xml_sha256': sha256_bytes(content=raw.encode()),
                'namespaces': {'ix': 'inline-uri'}, 'namespace_environment_id': 'env', 'nested_objects': []})
        s,d = self.base.source(supp); c = mapping.census(s,d)
        owner = next(r for r in c['refs'] if r[1]=='NATIVE_FACT')
        with patch.object(mapping, 'measure_request', return_value={'fits': True, 'context_tokens': 100}):
            t = mapping.prepare(s,d,c,[owner])
        self.assertEqual(len(t['payload']['native_context_references']), 4)
        self.assertEqual(len(t['payload']['complete_native_chain_paths'][0]['segments']),1)
        restored = _restore_units(t['payload']['native_partial_views'], t['payload']['shared_native_dictionaries'])
        self.assertTrue(any('reported\u037e' in obj['raw_xml'] for p in restored if p['kind']=='NATIVE_SUPPLEMENTS'
                            for obj in p['payload']['objects']))

    def test_source_duplicate_indices_and_missing_relation_endpoints_refused(self):
        p = deepcopy(self.base.fact['payload']); p['facts'].append(deepcopy(p['facts'][0]))
        fact = self.base.f.unit('NATIVE_FACTS',p)
        s,d = self.reseal([self.source['units'][0], fact, self.source['units'][2]])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE_ITEM'):mapping.census(s,d)
        supp = deepcopy(self.base.supplement);raw='<relationship fromrefs="missing" torefs="missing"/>'
        supp['objects'].append({'local_name':'relationship','namespace':'inline-uri',
            'attributes':{'fromrefs':'missing','torefs':'missing'},'raw_xml':raw,
            'raw_xml_sha256':sha256_bytes(content=raw.encode()),'namespace_environment_id':'env',
            'namespaces':{'ix':'inline-uri'},'nested_objects':[]})
        s,d = self.base.source(supp)
        with self.assertRaisesRegex(ValueError,'RELATION_ENDPOINT_MISSING'):mapping.census(s,d)
        changed=deepcopy(self.source);changed['company_id']='changed'
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):mapping.census(changed,self.digest)
        c=mapping.census(self.source,self.digest)
        owner=next(r for r in c['refs'] if r[1]=='VISIBLE_BLOCK')
        with self.assertRaisesRegex(ValueError,'OWNER_REFERENCE_SHAPE'):
            mapping.prepare(self.source,self.digest,c,[(True,owner[1],owner[2])])
        mutated=deepcopy(c);mutated['items'][owner]['text']='changed view'
        with self.assertRaisesRegex(ValueError,'MAPPING_CHANGED'):
            mapping.prepare(self.source,self.digest,mutated,[owner])
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):
            mapping.prepare(changed,self.digest,c,[owner])

    def test_reverse_order_footnote_relations_reach_context_fixed_point(self):
        payload=deepcopy(self.base.fact['payload'])
        second=deepcopy(payload['facts'][0]);second['fact']['ordinal']=10;second['attributes']['id']='f2'
        payload['facts'].append(second);fact=self.base.f.unit('NATIVE_FACTS',payload)
        supp=deepcopy(self.base.supplement)
        # The initially untriggered f2 relationship deliberately comes first.
        for local,attrs,raw in [
            ('relationship',{'fromrefs':'f2','torefs':'fn1'},'<relationship fromrefs="f2" torefs="fn1"/>'),
            ('relationship',{'fromrefs':'f1','torefs':'fn1'},'<relationship fromrefs="f1" torefs="fn1"/>'),
            ('footnote',{'id':'fn1'},'<footnote id="fn1">shared literal note</footnote>')]:
            supp['objects'].append({'local_name':local,'namespace':'inline-uri','attributes':attrs,
                'raw_xml':raw,'raw_xml_sha256':sha256_bytes(content=raw.encode()),'namespace_environment_id':'env',
                'namespaces':{'ix':'inline-uri'},'nested_objects':[]})
        s,d=self.reseal([self.source['units'][0],fact,self.base.f.unit('NATIVE_SUPPLEMENTS',supp)])
        c=mapping.census(s,d);owner=next(r for r in c['refs'] if r[1]=='NATIVE_FACT' and r[2]==9)
        with patch.object(mapping,'measure_request',return_value={'fits':True,'context_tokens':100}):t=mapping.prepare(s,d,c,[owner])
        self.assertIn([1,'NATIVE_FACT',10],t['payload']['native_context_references'])
        paths=t['payload']['complete_native_chain_paths']
        self.assertEqual(len(paths),2)
        self.assertEqual([x['anchor_is_owned'] for x in paths],[True,False])

    def test_resource_split_keeps_owned_items_and_never_truncates_a_complete_bundle(self):
        p = deepcopy(self.base.fact['payload'])
        for i in range(10,14):
            f=deepcopy(p['facts'][0]);f['fact']['ordinal']=i;f['attributes']={'id':'f'+str(i)}
            p['facts'].append(f)
        fact=self.base.f.unit('NATIVE_FACTS',p)
        s,d=self.reseal([self.source['units'][0],fact,self.source['units'][2]])
        with patch.object(mapping,'measure_request',side_effect=self.measurement):q=mapping.plan(s,d,maximum_fact_bundle=5)
        self.assertTrue(q['complete_owner_mapping']);self.assertEqual(q['status'],'ALL_INPUTS_FIT')
        self.assertEqual(sum(len(t['owned_references']) for t in q['tasks']),8)
        with patch.object(mapping,'measure_request',return_value={'fits':False,'context_tokens':250000}):q=mapping.plan(s,d)
        self.assertEqual(q['status'],'STOP_SHARED_VISIBLE_CONTEXT_RESOURCE')
        self.assertIsNone(q['proposed_initial_request_count'])
        self.assertEqual(len(q['stopped'][0]['owned_references']),2)


if __name__=='__main__':unittest.main()
