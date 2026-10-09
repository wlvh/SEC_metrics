"""Native acceptance tests require this work package's real sealed materials."""
import copy,json,os,tempfile,shutil
from pathlib import Path
import unittest
from unittest.mock import patch
from vnext import b06_new_source as w,b06_source_admission as a
from vnext.canonical import strict_json_file,content_hash
from vnext.specs import compile_spec_file
from vnext.run_store import load_frozen_run

class B06NewSourceMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value=os.environ.get('B06_NEW_SOURCE_MATERIAL_ROOT')
        if not value:raise RuntimeError('B06_NEW_SOURCE_MATERIAL_ROOT is required; not a skipped acceptance')
        cls.base=Path(value);cls.companies=list(a.policy()['samples'])
    def locations(self,cid):return self.base/cid/'accepted-data',self.base/cid/'accepted-run'
    def test_two_true_native_frozen_results(self):
        for cid in self.companies:
            data,run=self.locations(cid);m,records,_=load_frozen_run(run_dir=run,repo_root=data)
            self.assertEqual('FROZEN',m['status']);rs=[r for r in records if r['record_type']=='METRIC_RESULT'];self.assertEqual(1,len(rs));self.assertEqual('EXACT',rs[0]['quality']);self.assertIsNotNone(rs[0]['value'])
    def test_source_admission_is_required_by_native_cold_read(self):
        data,run=self.locations(self.companies[0])
        with patch.object(a,'_trusted_entries',return_value=({'stage_id':'TEST_ONLY_EMPTY_TRUST_STORE'},[])):
            with self.assertRaisesRegex(ValueError,'TRUSTED_ACQUISITION_OR_IMPORT_REQUIRED'):load_frozen_run(run_dir=run,repo_root=data)
    def test_no_old_relation_or_annual_input_fallback(self):
        with patch('vnext.r5_b06_scope.scope_inputs',side_effect=AssertionError('old human relationship forbidden')),patch('vnext.r5_b06_structured.discover',side_effect=AssertionError('latest discovery forbidden')),patch('vnext.annual_input.prepare_annual_input',side_effect=AssertionError('calendar-only entry forbidden')):
            for cid in self.companies:
                data,run=self.locations(cid);load_frozen_run(run_dir=run,repo_root=data)
    def test_same_input_reentry_reuses_exact_native_run(self):
        for cid in self.companies:
            data,run=self.locations(cid);before={p.relative_to(run).as_posix():p.read_bytes() for p in run.rglob('*') if p.is_file()}
            out=w.create_primary_run(data_root=data,run_dir=run,company_id=cid)
            self.assertEqual({'provider':0,'paid':0,'sec':0},out['calls']);self.assertEqual(before,{p.relative_to(run).as_posix():p.read_bytes() for p in run.rglob('*') if p.is_file()})
    def test_rebound_saved_verification_is_recomputed(self):
        cid=self.companies[-1];data,run=self.locations(cid);m,_,_=load_frozen_run(run_dir=run,repo_root=data)
        with tempfile.TemporaryDirectory() as tmp:
            new=Path(tmp)/'data';shutil.copytree(data,new)
            key=m['run_id'][len(w.PREFIX):];b=strict_json_file(path=new/'b06_bindings'/(key+'.json'));b['verification']['carrying_amount']='0';b['verification']['complete']=True;b['verification']['unresolved']=[]
            changed=content_hash(value=b)[7:];w._write(new/'b06_bindings'/(changed+'.json'),b);m={**m,'run_id':w.PREFIX+changed};spec=compile_spec_file(path=new/'catalog/r5/B06_new_source.md',dependency_specs={})
            with self.assertRaisesRegex(ValueError,'B06_SAVED_VERIFICATION_CHANGED'):w.replay(data_root=new,manifest=m,spec=spec)
    def test_actual_root_cannot_be_candidate_output(self):
        with self.assertRaisesRegex(ValueError,'EXTERNAL_CANDIDATE_ROOT_REQUIRED'):w._external(a.ROOT)

if __name__=='__main__':unittest.main()
