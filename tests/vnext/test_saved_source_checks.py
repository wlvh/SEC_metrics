"""Real selected proofs plus small missing/corruption/failure regressions."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext.annual_input import _saved_source
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.saved_source_checks import verify_saved_inputs, SavedSourceCheckError
from vnext.request_bindings import BatchWorkflowError
from sec_http import parse_request_log_rows, request_log_csv_bytes, refresh_request_log_manifest


class SavedSourceChecksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id='marriott_international')
        cls.proofs=cls.prepared['source_proofs']

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        paths={'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for p in self.proofs:
            paths.update((p['request_repo_relative_path'],p['request_headers_repo_relative_path']))
        for relative in paths:
            target=self.root/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(REPO_ROOT/relative,target)

    def test_complete_saved_package_without_git_journal_checks_actual_bytes(self):
        before=(self.root/'evidence/requests_log.csv').read_bytes()
        with patch('vnext.ordinary_source_authority._trusted_checkpoint',side_effect=AssertionError('No creator journal')):
            from vnext.ordinary_source_authority import verify_ordinary_source_proofs
            actual=verify_ordinary_source_proofs(data_root=self.root,proofs=self.proofs)
        self.assertEqual(actual['request_attempt_ids'],[p['request_attempt_id'] for p in self.proofs])
        self.assertFalse(actual['real_sec_credit']);self.assertFalse((self.root/'.git').exists())
        self.assertEqual((self.root/'evidence/requests_log.csv').read_bytes(),before)

    def test_corrupted_body_or_headers_are_rejected(self):
        p=self.proofs[0]
        for relative in (p['request_repo_relative_path'],p['request_headers_repo_relative_path']):
            path=self.root/relative;original=path.read_bytes();path.write_bytes(original+b' ')
            with self.assertRaises(BatchWorkflowError):verify_saved_inputs(data_root=self.root,proofs=self.proofs)
            path.write_bytes(original)

    def test_missing_selected_body_is_rejected(self):
        (self.root/self.proofs[0]['request_repo_relative_path']).unlink()
        with self.assertRaises(BatchWorkflowError):verify_saved_inputs(data_root=self.root,proofs=self.proofs)

    def test_missing_or_changed_attempt_identity_is_rejected(self):
        proofs=copy.deepcopy(self.proofs);proofs[0]['request_attempt_id']='sha256:'+'0'*64
        with self.assertRaises(BatchWorkflowError):verify_saved_inputs(data_root=self.root,proofs=proofs)
        proofs=copy.deepcopy(self.proofs);proofs[0]['request_headers_size']+=1
        with self.assertRaisesRegex(SavedSourceCheckError,'PROOF_DIFFERS'):
            verify_saved_inputs(data_root=self.root,proofs=proofs)

    def test_later_failed_request_cannot_be_hidden_by_old_success(self):
        path=self.root/'evidence/requests_log.csv';rows=parse_request_log_rows(text=path.read_text())
        failed={**next(r for r in rows if r['source_url']==self.proofs[0]['source_url']),
                'status_code':'503','error':'recorded failure','timestamp_utc':'2026-10-07T01:00:00Z'}
        path.write_bytes(request_log_csv_bytes(rows=[*rows,failed]));refresh_request_log_manifest(log_path=path,workdir=self.root)
        with self.assertRaisesRegex(SavedSourceCheckError,'LATEST_SOURCE_REQUEST_FAILED'):
            verify_saved_inputs(data_root=self.root,proofs=self.proofs)

    def test_wrong_filing_or_document_identity_is_rejected(self):
        proofs=copy.deepcopy(self.proofs)
        primary=next(p for p in proofs if '/Archives/' in p['source_url'])
        primary['accession']='0000000000-00-000001'
        with self.assertRaises(BatchWorkflowError):verify_saved_inputs(data_root=self.root,proofs=proofs)

    def test_empty_scope_is_not_complete(self):
        with self.assertRaisesRegex(SavedSourceCheckError,'PROOFS_REQUIRED'):
            verify_saved_inputs(data_root=self.root,proofs=[])


class RequestBindingsCompatibilityTest(unittest.TestCase):
    def test_original_imports_keep_same_exception_and_helpers(self):
        from vnext import request_bindings as helper, batch_workflow as old
        self.assertIs(old.BatchWorkflowError,helper.BatchWorkflowError)
        self.assertIs(old.request_attempt_binding,helper.request_attempt_binding)
        self.assertIs(old.validate_request_attempt_binding,helper.validate_request_attempt_binding)

    def test_helper_import_does_not_load_release_or_requirement(self):
        import subprocess,sys
        code="import sys;sys.path.insert(0,'scripts');import vnext.request_bindings;print(','.join(n for n in sys.modules if n in ('vnext.requirements','vnext.run_store','vnext.publication','vnext.batch_workflow')))"
        r=subprocess.run([sys.executable,'-B','-c',code],cwd=REPO_ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(r.stdout.strip(),'')


if __name__=='__main__':unittest.main()
