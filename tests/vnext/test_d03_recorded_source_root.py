"""Small routing/storage controls; constructed replies grant no business credit."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vnext import d03_recorded_response_set as store
from vnext.continuous_request_context import FORMAT_VERSION
from vnext.normal_source_authority import ROOT


class D03RecordedSourceRootTest(unittest.TestCase):
    def inputs(self):
        source={'company_id':'constructed','semantic_source_id':'source',
                'request_context_format':FORMAT_VERSION,'external_replay_only':True,
                'required_unit_ids':['unit']}
        request={'request_id':'request','units':[{'unit_id':'unit'}],
                 'source_statement_facts':[]}
        return source,request

    def test_registered_reconstruction_keeps_explicit_source_root_and_mode(self):
        source,request=self.inputs();data=Path('/external-registered-source')
        with patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=source) as rebuild, \
             patch('vnext.r6_regulatory_semantics.requests_from_source',return_value=[request]):
            self.assertEqual([request],store._requests(source,source_root=data))
        rebuild.assert_called_once_with(repo_root=data,company_id='constructed',
            request_context_format=FORMAT_VERSION,ordinary_registered=True)

    def test_legacy_default_uses_original_unmarked_call(self):
        source,request=self.inputs();source.pop('external_replay_only')
        with patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=source) as rebuild, \
             patch('vnext.r6_regulatory_semantics.requests_from_source',return_value=[request]):
            store._requests(source)
        rebuild.assert_called_once_with(repo_root=ROOT,company_id='constructed',request_context_format=FORMAT_VERSION)

    def test_changed_source_partition_or_invalid_mode_is_rejected(self):
        source,request=self.inputs()
        for rebuilt,requests in (({**source,'changed':True},[request]),(source,[])):
            with self.subTest(rebuilt=rebuilt), \
                 patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=rebuilt), \
                 patch('vnext.r6_regulatory_semantics.requests_from_source',return_value=requests), \
                 self.assertRaises(ValueError):
                store._requests(source,source_root=Path('/external-registered-source'))
        with self.assertRaisesRegex(ValueError,'SOURCE_MODE_INVALID'):
            store._requests({**source,'external_replay_only':1})

    def test_anchor_validation_receives_the_source_root(self):
        source,request=self.inputs();request['source_statement_facts']=[{'constructed':True}]
        data=Path('/external-registered-source');raw=b'constructed'
        checked={'findings':[],'unresolved':['constructed unresolved']}
        with patch('vnext.regulatory_fact_review.validate_candidate_response',return_value=(checked,request)) as validate:
            rows=store._checked_rows(source,[request],{'request':raw},source_root=data)
        self.assertEqual(1,rows[0]['unresolved_count'])
        self.assertEqual(data,validate.call_args.kwargs['repo_root'])

    def test_roundtrip_preserves_raw_unresolved_and_rechecks_a_previous_creator(self):
        from vnext.canonical import content_hash
        source,request=self.inputs();data=Path('/external-registered-source');raw=b'constructed raw answer'
        with tempfile.TemporaryDirectory() as folder, \
             patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=source) as rebuild, \
             patch('vnext.r6_regulatory_semantics.requests_from_source',return_value=[request]), \
             patch('vnext.r6_regulatory_semantics.validate_response',return_value={'findings':[],'unresolved':['constructed uncertainty']}):
            root=Path(folder).resolve()/'packet'
            recorded=store.record_offline_set(output_root=root,source=source,
                responses_by_original_id={'request':raw},source_root=data)
            packet=store.strict_json_file(path=root/'packet.json')
            packet['module_sha256']='1'*64
            packet['packet_id']=content_hash(value={k:v for k,v in packet.items() if k!='packet_id'})
            (root/'packet.json').write_bytes(store._json_bytes(packet))
            replay=store.replay_offline_set(packet_root=root,expected_packet_id=packet['packet_id'],source_root=data)
            self.assertEqual({'request':raw},replay['raw_response_bytes'])
            self.assertEqual(1,replay['unresolved_request_count'])
            self.assertEqual([0,0,0],replay['calls']);self.assertFalse(replay['native_result_created'])
            self.assertEqual(2,rebuild.call_count)
            self.assertTrue(all(c.kwargs['repo_root']==data and c.kwargs['ordinary_registered'] is True
                                for c in rebuild.call_args_list))
            with patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value={**source,'changed':True}), \
                 self.assertRaisesRegex(ValueError,'SAVED_SOURCE_CHANGED'):
                store.replay_offline_set(packet_root=root,expected_packet_id=packet['packet_id'],source_root=data)
            (root/'responses/0000.bin').write_bytes(raw+b'changed')
            with self.assertRaisesRegex(ValueError,'FILE_CHANGED'):
                store.replay_offline_set(packet_root=root,expected_packet_id=packet['packet_id'],source_root=data)
            self.assertFalse(recorded['native_result_created'])

    def test_incomplete_response_set_or_partial_write_has_no_complete_packet(self):
        source,request=self.inputs();data=Path('/external-registered-source')
        with tempfile.TemporaryDirectory() as folder, \
             patch('vnext.r6_regulatory_semantics.prepare_regulatory_semantic_source',return_value=source), \
             patch('vnext.r6_regulatory_semantics.requests_from_source',return_value=[request]), \
             patch('vnext.r6_regulatory_semantics.validate_response',return_value={'findings':[],'unresolved':[]}):
            root=Path(folder).resolve()/'packet'
            with self.assertRaisesRegex(ValueError,'MISSING_EXTRA_OR_NONBYTE'):
                store.record_offline_set(output_root=root,source=source,responses_by_original_id={},source_root=data)
            self.assertFalse(root.exists())
            real_write=store.write_immutable_bytes
            def interrupted(**kwargs):
                if kwargs['path'].name=='packet.json':raise OSError('constructed interrupted final write')
                return real_write(**kwargs)
            with patch.object(store,'write_immutable_bytes',side_effect=interrupted),self.assertRaises(OSError):
                store.record_offline_set(output_root=root,source=source,
                    responses_by_original_id={'request':b'constructed'},source_root=data)
            self.assertFalse((root/'packet.json').exists())
            with self.assertRaisesRegex(ValueError,'INCOMPLETE_OR_EXTRA'):
                store.replay_offline_set(packet_root=root,expected_packet_id='not-complete',source_root=data)
