"""Pre-egress source integrity; Greek question marks are not ASCII semicolons."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from vnext.canonical import content_hash,strict_json_loads
from vnext.r6_semantic_source import _seal_unit
from vnext.continuous_semantic_calls import validate_source_unit_bytes,_json,SemanticRequest,_FACTORY

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
