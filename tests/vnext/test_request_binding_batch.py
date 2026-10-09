"""One-operation proof reuse with original source checks, no persistent cache."""
import copy
from pathlib import Path
import shutil,tempfile,unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext import request_bindings as binding
from vnext import ordinary_current_update as update
from vnext.canonical import sha256_file
from sec_http import parse_request_log_rows,request_log_csv_bytes,refresh_request_log_manifest


class RequestBindingBatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proofs=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id='marriott_international')['source_proofs']

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        paths={'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for proof in self.proofs:paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
        for path in paths:
            target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO_ROOT/path,target)
        self.requests=[{k:p[k] for k in ('source_url','content_sha256','accession','document_name','request_attempt_id')}
                       | {'require_immutable':False} for p in self.proofs]

    def many(self,requests=None):
        return binding.validate_request_attempt_bindings(repo_root=self.root,requests=self.requests if requests is None else requests)

    def test_batch_proofs_are_exactly_equal_to_unchanged_single_api(self):
        before=copy.deepcopy(self.requests)
        expected=[binding.validate_request_attempt_binding(repo_root=self.root,**r) for r in self.requests]
        self.assertEqual(self.many(),expected);self.assertEqual(self.requests,before)

    def test_each_body_and_header_is_checked_even_after_an_earlier_pass(self):
        expected=self.many()
        for key in ('request_repo_relative_path','request_headers_repo_relative_path'):
            path=self.root/self.proofs[0][key];raw=path.read_bytes();path.write_bytes(raw+b' ')
            with self.assertRaises(binding.BatchWorkflowError) as many_error:self.many()
            with self.assertRaises(binding.BatchWorkflowError) as one_error:
                binding.validate_request_attempt_binding(repo_root=self.root,**self.requests[0])
            self.assertEqual(str(many_error.exception),str(one_error.exception))
            path.write_bytes(raw)
        self.assertEqual(self.many(),expected)

    def test_no_missing_or_wrong_named_source_becomes_a_pass(self):
        for field,value in [('request_attempt_id','not-an-attempt'),('accession','0000000000-00-000001'),
                            ('content_sha256','0'*64),('source_url','https://www.sec.gov/wrong'),('document_name','wrong')]:
            # Use the annual primary for accession/document identity controls.
            changed=copy.deepcopy(self.requests);i=next(i for i,r in enumerate(changed) if '/Archives/' in r['source_url']);changed[i][field]=value
            with self.subTest(field=field),self.assertRaises(binding.BatchWorkflowError):self.many(changed)

    def test_same_request_can_be_checked_for_two_roles_without_changing_identity(self):
        expected=self.many();actual=self.many([self.requests[0],self.requests[0]])
        self.assertEqual(actual,[expected[0],expected[0]])

    def test_stale_manifest_and_missing_body_are_not_cached(self):
        self.many();path=self.root/'evidence/requests_log.csv';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(binding.BatchWorkflowError):self.many()
        path.write_bytes((REPO_ROOT/'evidence/requests_log.csv').read_bytes())
        (self.root/self.proofs[0]['request_repo_relative_path']).unlink()
        with self.assertRaises(binding.BatchWorkflowError):self.many()

    def test_changed_log_during_operation_refuses_no_change(self):
        original=binding._verified_request_locator
        def check(**kwargs):
            result=original(**kwargs);p=self.root/'evidence/requests_log.csv';p.write_bytes(p.read_bytes()+b' ');return result
        with patch.object(binding,'_verified_request_locator',side_effect=check):
            with self.assertRaisesRegex(binding.BatchWorkflowError,'changed during'):self.many()

    def test_single_snapshot_attempt_ids_once_per_row_plus_selected_proofs(self):
        count=len(parse_request_log_rows(text=(self.root/'evidence/requests_log.csv').read_text()))
        with patch.object(binding,'request_log_attempt_id',wraps=binding.request_log_attempt_id) as ids:
            self.many()
        self.assertEqual(ids.call_count,count+len(self.requests))

    def test_current_entry_still_rejects_later_failed_get(self):
        self.assertEqual(len(update._current_sources(self.root,self.proofs)),len(self.proofs))
        path=self.root/'evidence/requests_log.csv';rows=parse_request_log_rows(text=path.read_text());old=next(r for r in rows if r['source_url']==self.proofs[0]['source_url'])
        rows.append({**old,'status_code':'503','error':'recorded failure','timestamp_utc':'2026-10-10T00:00:00Z'})
        path.write_bytes(request_log_csv_bytes(rows=rows));refresh_request_log_manifest(log_path=path,workdir=self.root)
        with self.assertRaisesRegex(ValueError,'LATEST_SOURCE_REQUEST_FAILED'):update._current_sources(self.root,self.proofs)

    def test_current_entry_uses_actual_batch_and_expected_snapshot(self):
        with patch.object(binding,'validate_request_attempt_bindings',wraps=binding.validate_request_attempt_bindings) as many:
            actual=update._current_sources(self.root,self.proofs)
        self.assertEqual(many.call_count,1)
        self.assertEqual(many.call_args.kwargs['expected_log_sha256'],sha256_file(path=self.root/'evidence/requests_log.csv'))
        self.assertEqual(actual,[{k:p[k] for k in ('source_url','accession','document_name','content_sha256')} for p in self.proofs])

    def test_invalid_batch_shape_does_not_read_sources(self):
        for value in (None,{},[{'request_attempt_id':'bad'}]):
            with self.subTest(value=value),self.assertRaisesRegex(binding.BatchWorkflowError,'batch'):
                self.many(value) if value is not None else binding.validate_request_attempt_bindings(repo_root=self.root,requests=None)


class SourceCheckConfigurationTest(unittest.TestCase):
    def test_checked_runtime_versions_do_not_require_financial_recalculation(self):
        before={'source_root':'same','company_id':'same','metric_id':'B01','processing_files':{
            'scripts/vnext/ordinary_current_update.py':'old-controller',
            'scripts/vnext/request_bindings.py':'old-checks',
            'scripts/vnext/calculator.py':'same-calculator','scripts/vnext/normal_annual_input.py':'same-period'}}
        after=copy.deepcopy(before);after['processing_files']['scripts/vnext/ordinary_current_update.py']='new-controller'
        after['processing_files']['scripts/vnext/request_bindings.py']='new-checks'
        self.assertTrue(update._same_processing_configuration(before,after))
        self.assertEqual(before['processing_files']['scripts/vnext/request_bindings.py'],'old-checks')
        for path in ('scripts/vnext/calculator.py','scripts/vnext/normal_annual_input.py'):
            changed=copy.deepcopy(after);changed['processing_files'][path]='changed-business'
            self.assertFalse(update._same_processing_configuration(before,changed))
        for key in ('source_root','company_id','metric_id'):
            changed=copy.deepcopy(after);changed[key]='different'
            self.assertFalse(update._same_processing_configuration(before,changed))

    def test_parser_or_prompt_configuration_is_never_discarded(self):
        for config in ({'prompt':'before'},{'provider':'before'},{'parser':'before'}):
            self.assertFalse(update._same_processing_configuration(config,{**config,next(iter(config)):'after'}))
