"""Processing trust/ownership regressions; original native reader has material probes."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.vnext.canonical import canonical_json_bytes, content_hash
from scripts.vnext.company_handoff import binding
from scripts.vnext import company_processing as p
from scripts.vnext import normal_source_authority, company_source_authority


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

    def test_worker_cwd_is_external_work_not_development_checkout(self):
        for directory in (self.temp.name, str(Path(self.temp.name)/'not-created')):
            work=Path(directory)
            with patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{}',stderr='')) as run:
                p.worker('replay',self.program,self.packet,self.packet,work)
                self.assertEqual(run.call_args.kwargs['cwd'],work if work.is_dir() else work.parent)

    def test_nested_input_alias_rejected(self):
        config=self.packet/'config';original=config/'ordinary_going_concern_assessment.json';raw=original.read_bytes()
        original.unlink();config.rmdir();external=self.packet.parent/'aliased';external.mkdir()
        (external/original.name).write_bytes(raw);config.symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'MEMBER_SET_CHANGED|ALIAS'):self.authenticate()


class AcquiredProcessingBoundaryTest(unittest.TestCase):
    """Orchestration only; native source/assessment material probes are separate."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);self.root=base/'state';self.source=base/'source'
        self.original=base/'original-source';self.program=base/'program';self.packet=base/'packet'
        self.current_program=base/'current-program'
        for folder in (self.root,self.source,self.original,self.program,self.packet):folder.mkdir()
        (self.current_program/'requirements/issue_54_v1').mkdir(parents=True)
        (self.source/'whole-current-ledger.csv').write_bytes(b'original rows AND all mixed increments')
        self.metadata={'input_record_id':'sha256:'+'a'*64,'source_id':'sha256:'+'b'*64,
            'mode':'LIVE','requirement_closure_hash':'sha256:'+'c'*64,'processing_id':'sha256:'+'d'*64}
        self.admission={'original_checkpoint':{'all_companies':'unchanged'},'checkpoint_id':'current'}
        patches=[patch.dict(os.environ,{p.TRUST_VARIABLE:str(base/'trust')}),
                 patch.object(p,'authenticate_processing',return_value=self.metadata),
                 patch.object(normal_source_authority,'ROOT',self.current_program),
                 patch.object(company_source_authority,'require_company',return_value={
                     'original_checkpoint':None,'checkpoint_id':'original','metric_ids':['D04']})]
        for item in patches:item.start();self.addCleanup(item.stop)

    def compute(self,version=None):
        return p.compute_saved_processing(root=self.root,source=self.source,admission=self.admission,
            company_id='test_company',packet_root=self.packet,program_root=self.program,source_version=version)

    def test_acquired_input_requires_actual_original_company_version(self):
        with patch.object(p,'worker') as work:
            with self.assertRaisesRegex(ValueError,'ORIGINAL_SOURCE_VERSION_REQUIRED'):self.compute()
            work.assert_not_called()
        self.assertFalse((self.root/'updates').exists())

    def test_substantive_mismatch_does_not_generate_native_run(self):
        calls=[]
        def work(action,*args):
            calls.append(action)
            if action=='current':return {'source':{'whole':'current'},'requirement_closure_hash':'fixed'}
            if action=='equivalence':raise ValueError('UPDATE_NATIVE_SUBSTANTIVE_SOURCE_CHANGED')
            self.fail('native compute must not run on a changed source')
        with patch.object(p,'worker',side_effect=work): result=self.compute(self.original)
        self.assertEqual(calls,['current','equivalence'])
        self.assertEqual(result['status'],'PROCESSING_INPUT_REJECTED')
        self.assertIsNone(result['last_verified_candidate'])
        self.assertFalse(list((self.root/'updates').rglob('current.json')))
        self.assertEqual((self.source/'whole-current-ledger.csv').read_bytes(),b'original rows AND all mixed increments')

    def test_equivalence_precedes_original_runtime_and_keeps_both_versions(self):
        calls=[]
        def work(action,program,packet,source,directory):
            calls.append((action,Path(source)))
            if action=='current':return {'source':{'whole':'current'},'requirement_closure_hash':'fixed'}
            if action=='equivalence':return {'equivalence_id':'strict-proof','new_provider_execution':False}
            return {'native_assessment_completed':True,'run_id':'native','result_id':'original-result',
                    'publication':'WITHHELD','mode':'LIVE'}
        with patch.object(p,'worker',side_effect=work):result=self.compute(self.original)
        self.assertEqual([a for a,_ in calls],['current','equivalence','compute'])
        self.assertEqual(calls[-1][1],self.original)
        work_root=Path(result['last_verified_candidate']['rows_root']).parent
        self.assertEqual((work_root/'current-source/whole-current-ledger.csv').read_bytes(),
                         (self.source/'whole-current-ledger.csv').read_bytes())
        receipt=json.loads((work_root/'processing-receipt.json').read_text())
        self.assertEqual(receipt['source_checkpoint_id'],'current')
        self.assertEqual(receipt['original_source_checkpoint_id'],'original')
        self.assertEqual(receipt['mode'],'LIVE')
        self.assertFalse(result['business_metric_completed'])

    def test_cold_export_rebuilds_equivalence_instead_of_trusting_saved_json(self):
        work=self.root/'work';work.mkdir()
        (work/'processing-receipt.json').write_text(json.dumps({'current_source_equivalence':{'equivalence_id':'saved'},
            'current_source_runtime_root':str(self.current_program),'current_source_runtime_closure_hash':'fixed'}))
        (work/'current-semantic-source.json').write_text(json.dumps({'whole':'saved'}))
        with patch.object(p,'worker',return_value={'source':{'whole':'changed'},'requirement_closure_hash':'fixed'}) as check:
            with self.assertRaisesRegex(ValueError,'CURRENT_SOURCE_CHANGED'):
                p.verify_saved_equivalence(program_root=self.program,packet_root=self.packet,work=work)
            self.assertEqual(check.call_args.args[0],'current')

    def test_receipt_cannot_nominate_an_unprovided_source_runtime(self):
        work=self.root/'work';work.mkdir()
        (work/'processing-receipt.json').write_text(json.dumps({'current_source_equivalence':{'equivalence_id':'saved'},
            'current_source_runtime_root':str(self.program)}))
        with patch.object(p,'worker') as check:
            with self.assertRaisesRegex(ValueError,'CURRENT_SOURCE_RUNTIME_NOT_SUPPLIED'):
                p.verify_saved_equivalence(program_root=self.program,packet_root=self.packet,work=work)
            check.assert_not_called()

    def test_repeat_uses_current_fixed_runtime_without_resigning_original_proof(self):
        work=self.root/'work';work.mkdir()
        proof={'equivalence_id':'old-proof'}
        raw=json.dumps({'current_source_equivalence':proof,'current_source_runtime_root':'/unavailable-old-tree',
                        'current_source_runtime_closure_hash':'old'})
        (work/'processing-receipt.json').write_text(raw)
        (work/'current-semantic-source.json').write_text(json.dumps({'whole':'unchanged'}))
        with patch.object(p,'worker',side_effect=[{'source':{'whole':'unchanged'},'requirement_closure_hash':'new'},proof]) as check:
            p.verify_saved_equivalence(program_root=self.program,packet_root=self.packet,work=work,recheck_current=True)
            self.assertEqual(check.call_args_list[0].args[1],self.current_program)
        self.assertEqual((work/'processing-receipt.json').read_text(),raw)
