"""New request rows need installed execution ownership, not caller sidecars."""
import copy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from tests.vnext import test_ordinary_source_session as session_tests
from tests.vnext.common import REPO_ROOT as ROOT
from vnext import ordinary_source_authority as authority
from vnext.ordinary_source_session import OrdinarySourceSessionError
from vnext.batch_workflow import BatchWorkflowError
from vnext.normal_source_authority import NormalSourceAuthorityError
from vnext.canonical import content_hash
from sec_http import parse_request_log_rows,request_log_csv_bytes,refresh_request_log_manifest


class OrdinarySourceAuthorityTest(unittest.TestCase):
    setUpClass=classmethod(session_tests.OrdinarySourceSessionTest.setUpClass.__func__)

    def setUp(self):
        session_tests.OrdinarySourceSessionTest.setUp(self)
        self.owner=self.root/'installed';(self.owner/'.git').mkdir(parents=True)
        path=self.owner/authority.MANIFEST_PATH;path.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/authority.MANIFEST_PATH,path)
        patch.object(authority,'ROOT',self.owner).start()

    def append(self):
        for proof in self.original['source_proofs']:
            self.session.record_saved_response(url=proof['source_url'],accession=proof['accession'])
        return self.session.prepare_annual_input()['prepared_input']

    def test_real_creator_registers_append_for_restart_without_live_credit(self):
        prepared=self.append()
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'UNREGISTERED_LEDGER'):
            authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])
        checkpoint=authority.register_recorded_session(session=self.session)
        self.session._terminal_ids=[]  # Admission no longer depends on the old process object.
        admitted=authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])
        self.assertEqual(checkpoint['checkpoint_id'],admitted['checkpoint_id'])
        self.assertEqual('RECORDED_TEST_ONLY',admitted['source_credit'])
        self.assertFalse(admitted['real_sec_credit']);self.assertFalse(admitted['production_authorized'])
        self.assertEqual({'provider':0,'paid':0,'sec':0},admitted['new_business_calls'])

    def test_data_sidecar_and_resigned_ledger_cannot_enroll_without_installed_history(self):
        prepared=self.append();checkpoint=authority.register_recorded_session(session=self.session)
        journal=self.owner/'.git/ordinary-source-authority/recorded'/(checkpoint['ledger_sha256']+'.json');journal.unlink()
        export=self.data/authority.EXPORT_PATH;export.parent.mkdir(parents=True,exist_ok=True)
        export.write_text(json.dumps(checkpoint))
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'UNREGISTERED_LEDGER'):
            authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'OWNED_SESSION_REQUIRED'):
            authority.register_recorded_session(session={'session':checkpoint['session']})

    def test_changed_export_or_body_cannot_keep_the_checkpoint(self):
        prepared=self.append();checkpoint=authority.register_recorded_session(session=self.session)
        export=self.data/authority.EXPORT_PATH;export.parent.mkdir(parents=True,exist_ok=True)
        fake=copy.deepcopy(checkpoint);fake['real_sec_credit']=True
        fake['checkpoint_id']=content_hash(value={k:v for k,v in fake.items() if k!='checkpoint_id'});export.write_text(json.dumps(fake))
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'IMPORTED_CHECKPOINT_CHANGED'):
            authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])
        export.unlink();body=self.data/prepared['table_input']['source_repo_relative_path'];body.write_bytes(body.read_bytes()+b' ')
        with self.assertRaisesRegex(NormalSourceAuthorityError,'TRUSTED_SAVED_BASELINE_BYTES_CHANGED'):
            authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])

    def test_portable_installed_checkpoint_uses_the_same_original_source_checks(self):
        prepared=self.append();checkpoint=authority.register_recorded_session(session=self.session)
        selected,paths=authority.checkpoint_installation(source_root=self.data)
        self.assertEqual(checkpoint,selected);self.assertTrue(paths)
        export=self.data/authority.EXPORT_PATH;export.parent.mkdir(parents=True,exist_ok=True);export.write_text(json.dumps(checkpoint))
        shutil.copyfile(ROOT/authority.MANIFEST_PATH,self.data/authority.MANIFEST_PATH)
        with patch.object(authority,'ROOT',self.data):
            admission=authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])
        self.assertEqual('RECORDED_TEST_ONLY',admission['source_credit'])
        self.assertFalse((self.data/'.git').exists())

    def test_unknown_or_failed_session_cannot_register_a_current_source(self):
        p=self.original['source_proofs'][0]
        self.session.record_saved_response(url=p['source_url'],status_code=500)
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'SUCCESSFUL_SESSION_REQUIRED'):
            authority.register_recorded_session(session=self.session)
        (self.root/'journal/terminals/000001.json').unlink()
        with self.assertRaisesRegex(OrdinarySourceSessionError,'OUTCOME_UNKNOWN'):
            authority.register_recorded_session(session=self.session)

    def test_append_after_registered_checkpoint_and_changed_prefix_are_rejected(self):
        prepared=self.append();authority.register_recorded_session(session=self.session)
        path=self.data/'evidence/requests_log.csv';original=path.read_bytes()
        rows=parse_request_log_rows(text=original.decode());rows.append(dict(rows[-1]));path.write_bytes(request_log_csv_bytes(rows=rows))
        refresh_request_log_manifest(workdir=self.data,log_path=path)
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'UNREGISTERED_LEDGER'):
            authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])
        path.write_bytes(original);refresh_request_log_manifest(workdir=self.data,log_path=path)
        rows=parse_request_log_rows(text=original.decode());rows[0]['purpose']='changed';path.write_bytes(request_log_csv_bytes(rows=rows))
        refresh_request_log_manifest(workdir=self.data,log_path=path)
        with self.assertRaisesRegex(authority.OrdinarySourceAuthorityError,'UNREGISTERED_LEDGER'):
            authority.verify_ordinary_source_proofs(data_root=self.data,proofs=prepared['source_proofs'])


if __name__=='__main__':unittest.main()
