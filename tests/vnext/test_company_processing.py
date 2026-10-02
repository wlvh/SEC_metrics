"""Processing trust/ownership regressions; original native reader has material probes."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext.canonical import canonical_json_bytes, content_hash
from scripts.vnext.company_handoff import binding
from scripts.vnext import company_processing as p


class SavedProcessingTrustTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.packet=root/'processing';self.program=root/'program';self.trust=root/'trust'
        for directory in [self.packet,self.program,self.trust]:directory.mkdir()
        (self.packet/'config').mkdir();(self.packet/'config/ordinary_going_concern_assessment.json').write_bytes(b'original record bytes')
        (self.program/'scripts').mkdir();(self.program/'scripts/core.py').write_bytes(b'original program bytes')
        self.metadata={'company_id':'test_company','metric_id':'D04','new_call_authority':False,'production_authorized':False,
            'files':{'config/ordinary_going_concern_assessment.json':binding(self.packet/'config/ordinary_going_concern_assessment.json')},
            'runtime_files':{'scripts/core.py':binding(self.program/'scripts/core.py')}}
        self.seal(self.metadata)
        environment=patch.dict(os.environ,{p.TRUST_VARIABLE:str(self.trust)});environment.start();self.addCleanup(environment.stop)

    def seal(self,metadata):
        metadata['processing_id']=content_hash(value={k:v for k,v in metadata.items() if k!='processing_id'})
        raw=canonical_json_bytes(value=metadata)
        (self.packet/'processing.json').write_bytes(raw)
        (self.trust/(metadata['processing_id'][7:]+'.json')).write_bytes(raw)

    def authenticate(self,company='test_company'):
        return p.authenticate_processing(packet_root=self.packet,program_root=self.program,company_id=company)

    def test_exact_trusted_inputs_pass_without_business_calls(self):
        self.assertEqual(self.metadata,self.authenticate())

    def test_wrong_company_rejected(self):
        with self.assertRaisesRegex(ValueError,'WRONG_COMPANY'):self.authenticate('other_company')

    def test_changed_original_response_record_rejected(self):
        (self.packet/'config/ordinary_going_concern_assessment.json').write_bytes(b'rehashed old answer')
        with self.assertRaisesRegex(ValueError,'BOUND_FILE_CHANGED'):self.authenticate()

    def test_self_rehash_cannot_enroll_or_promote_processing(self):
        v={**self.metadata,'mode':'LIVE'};v['processing_id']=content_hash(value={k:x for k,x in v.items() if k!='processing_id'})
        (self.packet/'processing.json').write_bytes(canonical_json_bytes(value=v))
        with self.assertRaises((FileNotFoundError,ValueError)):self.authenticate()

    def test_sec_or_result_hidden_in_processing_packet_rejected(self):
        (self.packet/'Result.json').write_bytes(b'not an input')
        with self.assertRaisesRegex(ValueError,'MEMBER_SET_CHANGED'):self.authenticate()

    def test_changed_runtime_rejected(self):
        (self.program/'scripts/core.py').write_bytes(b'new rules')
        with self.assertRaisesRegex(ValueError,'BOUND_FILE_CHANGED'):self.authenticate()

    def test_nested_input_alias_rejected(self):
        config=self.packet/'config';original=config/'ordinary_going_concern_assessment.json';raw=original.read_bytes()
        original.unlink();config.rmdir();external=self.packet.parent/'aliased';external.mkdir()
        (external/original.name).write_bytes(raw);config.symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'MEMBER_SET_CHANGED|ALIAS'):self.authenticate()
