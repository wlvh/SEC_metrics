"""Pre-egress source integrity; Greek question marks are not ASCII semicolons."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from vnext.canonical import content_hash,strict_json_loads
from vnext.r6_semantic_source import _seal_unit
from vnext.continuous_semantic_calls import validate_source_unit_bytes,_json,_source_json,request_body,SemanticRequest,_FACTORY

class SourceUnitBytesTest(unittest.TestCase):
    def source(self,text):
        unit=_seal_unit('sha256:'+'a'*64,'VISIBLE_TEXT',{'blocks':[{'block_index':1,'text':text}]},0)
        value={'metric_id':'D04','units':[unit]};value['semantic_source_id']=content_hash(value=value);return value
    def test_unchanged_ascii_and_exact_original_unicode_are_valid(self):
        validate_source_unit_bytes(self.source('A business risk; no assessment.'))
        validate_source_unit_bytes(self.source('A business risk\u037e no assessment.'))
    def test_generic_nfc_serialization_is_rejected_before_authority_or_claim(self):
        source=self.source('A business risk\u037e no assessment.');decoded=strict_json_loads(text=_json(source).decode())
        self.assertIn(';',decoded['units'][0]['payload']['blocks'][0]['text'])
        with self.assertRaisesRegex(ValueError,'SOURCE_UNIT_SERIALIZATION_CHANGED'):validate_source_unit_bytes(decoded)
        obj=SemanticRequest(_FACTORY,_json(source),b'{}',b'{}',b'{}',{},SimpleNamespace(_check=lambda:None))
        with self.assertRaisesRegex(ValueError,'SOURCE_UNIT_SERIALIZATION_CHANGED'):obj.validate(None)
    def test_changed_size_hash_or_id_is_rejected(self):
        for key in ['payload_bytes','payload_sha256','unit_id']:
            source=self.source('Unchanged source')
            source['units'][0][key]=0 if key=='payload_bytes' else 'changed'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'SOURCE_UNIT_SERIALIZATION_CHANGED'):
                validate_source_unit_bytes(source)

    def test_native_serialization_and_wire_preserve_unicode_without_changing_canonical(self):
        import json
        from vnext.r6_semantic_source import _bytes
        for text in ['Original\u037e ; e\u0301 \u2126', 'Plain; unchanged']:
            source=self.source(text);raw=_source_json(source)
            self.assertEqual(strict_json_loads(text=raw.decode()),source)
            validate_source_unit_bytes(strict_json_loads(text=raw.decode()))
            request={**source,'system_prompt':'Read exact source.'}
            wire=request_body(request,SimpleNamespace(model='deepseek-flash'))
            decoded=json.loads(json.loads(wire)['messages'][1]['content'])
            self.assertEqual(decoded['units'][0]['payload']['blocks'][0]['text'],text)
            self.assertEqual(_bytes(decoded['units'][0]['payload']),_bytes(source['units'][0]['payload']))
        self.assertEqual(_source_json(self.source('Plain; unchanged')),_json(self.source('Plain; unchanged')))
        self.assertNotEqual(_source_json(self.source('Original\u037e')),_json(self.source('Original\u037e')))
