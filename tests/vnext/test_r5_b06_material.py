"""Explicit full saved-material checks; run with R5_B06_CANDIDATE_ROOT set."""
from pathlib import Path
import copy,json,os,tempfile,unittest
from unittest.mock import patch
from vnext import r5_b06_publication as release,r5_b06_structured as primary,publication
from vnext.run_store import load_frozen_run,create_run,append_run_record,validate_and_freeze_run
from vnext.canonical import strict_json_file,canonical_json_bytes,content_hash
from vnext.batch_workflow import _registry_rows

class B06MaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value=os.environ.get('R5_B06_CANDIDATE_ROOT')
        if not value:raise RuntimeError('R5_B06_CANDIDATE_ROOT required; material acceptance cannot be SKIP')
        cls.root=Path(value);cls.saved=strict_json_file(path=cls.root/'prepared.json');cls.bundle=cls.root/'outputs/publications'/cls.saved['publication_id'];cls.data=cls.bundle/'internal/annual_snapshot/data';cls.runs=cls.bundle/'internal/annual_snapshot/runs'
    def test_complete_version_and_cold_sources(self):
        m=publication.verify_publication_bundle(bundle_dir=self.bundle);self.assertEqual('BLOCKED',m['candidate_status']);v=publication.PublicationView(publication_id=m['publication_id'],bundle_dir=self.bundle,manifest=m)
        batch=json.loads(v.read_bytes(relative_path=release.BATCH));self.assertEqual(250,len(batch['cumulative_result_bindings']));self.assertEqual(240,batch['inherited_result_count']);self.assertEqual(batch['predecessor_public_row_count']+len(batch['new_public_keys']),len(release._rows(v.read_bytes(relative_path='metrics_matrix.csv'))));self.assertEqual(318,batch['unchanged_public_row_count'])
        for company in _registry_rows(repo_root=self.data):
            native=v.native_result(company_id=company['company_id'],metric_id='B06');self.assertEqual(company['company_id'],native['result']['company_id']);self.assertTrue(native['sources'])
    def test_old_debt_producer_unavailable_still_creates_native_result(self):
        import sec_pipeline
        company=next(c for c in _registry_rows(repo_root=self.data) if c['company_id']=='enphase_energy')
        with tempfile.TemporaryDirectory(dir=self.root) as tmp,patch.object(sec_pipeline,'resolve_total_debt_component',side_effect=AssertionError('OLD_B06_PRODUCER_CALLED')):
            result=primary.create_primary_run(data_root=self.data,run_dir=Path(tmp)/'run',company=company)
            self.assertEqual('PASS',result['result']['reason_code']);self.assertEqual('FROZEN',result['manifest']['status'])
    def test_removing_scope_source_and_rehashing_run_is_rejected(self):
        source=self.runs/'ford_motor_company';manifest,records,decisions=load_frozen_run(run_dir=source,repo_root=self.data)
        cf=[s for s in manifest['source_references'] if s['source_role']=='companyfacts'];self.assertLess(len(cf),len(manifest['source_references']))
        rawids={s['raw_asset_id'] for s in cf}
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            out=Path(tmp)/'run';create_run(run_dir=out,run_id='run:test:r5-omitted-scope',company_id=manifest['company_id'],company_traits=manifest['company_traits'],target_period=manifest['target_period'],source_references=cf,missing_required_source_roles=[],spec_file_hashes=manifest['spec_file_hashes'],requirement_hashes=manifest['requirement_hashes'],requirement_id=manifest['requirement_id'],requirement_closure_hash=manifest['requirement_closure_hash'],artifact_requirement_generation=manifest['artifact_requirement_generation'])
            for r in records:
                if r['record_type']=='SOURCE_REFERENCE' and r not in cf:continue
                if r['record_type']=='RAW_BLOB' and r['raw_asset_id'] not in rawids:continue
                append_run_record(run_dir=out,record=r)
            with self.assertRaisesRegex(ValueError,'R5_REQUIRED_SOURCE_SET_CHANGED'):validate_and_freeze_run(run_dir=out,repo_root=self.data)
    def test_saved_source_rewrite_cannot_self_sign_origin(self):
        # The internally consistent candidate stays intact; inject a different
        # byte at the Git-object I/O boundary. Internal self-consistency cannot
        # replace the independent saved-source anchor. No validator is mocked.
        company=next(c for c in _registry_rows(repo_root=self.data) if c['company_id']=='enphase_energy')
        selected=primary.discover(data_root=self.data,company=company);source=next(s for s in selected['sources'] if '/companyfacts/' in s['source_url']);p=self.data/source['request_repo_relative_path']
        original=release.subprocess.check_output
        def changed(args,**kwargs):
            value=original(args,**kwargs)
            return value+b' ' if args[:2]==['git','show'] and args[2].endswith(':'+source['request_repo_relative_path']) else value
        with patch.object(release.subprocess,'check_output',changed):
            with self.assertRaisesRegex(ValueError,'R5_SAVED_SOURCE_ORIGIN_CHANGED'):release._verify_saved_input_origin(self.data,self.saved['code']['implementation_head'])
    def test_production_switch_denied_and_repeat_prepare_reuses(self):
        for fn in (release.commit_authority,release.guard_switch,release.guard_recovery):
            with self.assertRaisesRegex(publication.PublicationError,'NOT_AUTHORIZED'):fn()
        result=release.prepare(candidate_root=self.root);self.assertEqual('REUSED_COMPLETE_CANDIDATE',result['status']);self.assertEqual(self.saved['publication_id'],result['publication_id'])

if __name__=='__main__':unittest.main()
