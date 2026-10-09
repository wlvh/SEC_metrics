"""Retained old checkpoint/export compatibility only.

Current source byte/request/failure checks live in test_saved_source_checks.
Creator-journal, forged-sidecar and frozen-prefix rejection were retired by
Issue28 trusted-internal-20261006; historical tests stay in Git history.
"""
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from tests.vnext import test_ordinary_source_session as session_tests
from tests.vnext.common import REPO_ROOT as ROOT
from vnext import ordinary_source_authority as authority
from vnext.ordinary_source_session import OrdinarySourceSessionError


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



if __name__=='__main__':unittest.main()
