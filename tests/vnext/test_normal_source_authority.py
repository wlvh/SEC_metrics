"""Caller-controlled imports cannot replace the installed acquisition baseline."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.normal_source_authority import verify_saved_source_proofs, NormalSourceAuthorityError


class NormalSourceAuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proofs = prepare_saved_annual_input(
            repo_root=REPO_ROOT, company_id='marriott_international')['source_proofs']

    def test_no_git_import_rechecks_bytes_and_rejects_caller_baseline(self):
        with tempfile.TemporaryDirectory(prefix='normal-source-authority-') as tmp:
            root = Path(tmp)
            files = {'config/company_registry.csv', 'evidence/requests_log.csv',
                     'evidence/requests_log_manifest.json'}
            for proof in self.proofs:
                files.update([proof['request_repo_relative_path'], proof['request_headers_repo_relative_path']])
            for relative in files:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO_ROOT / relative, path)
            receipt = verify_saved_source_proofs(data_root=root, proofs=self.proofs)
            self.assertEqual('PREEXISTING_SAVED_ACQUISITIONS_ONLY', receipt['source_credit'])
            self.assertFalse((root / '.git').exists())
            for relative in ['config/company_registry.csv', 'evidence/requests_log.csv',
                             self.proofs[0]['request_repo_relative_path'],
                             self.proofs[0]['request_headers_repo_relative_path']]:
                with self.subTest(relative=relative):
                    path = root / relative
                    original = path.read_bytes()
                    path.write_bytes(original + b' ')
                    # Even a matching caller-supplied manifest is not authority.
                    fake = json.loads((REPO_ROOT / 'config/normal_candidate_sources_v1.json').read_text())
                    from vnext.normal_source_authority import _git_blob_id
                    fake['files'][relative] = {'git_blob_id': _git_blob_id(path.read_bytes()), 'size': path.stat().st_size}
                    (root / 'config/normal_candidate_sources_v1.json').write_text(json.dumps(fake))
                    with self.assertRaisesRegex(NormalSourceAuthorityError, 'BASELINE_BYTES_CHANGED'):
                        verify_saved_source_proofs(data_root=root, proofs=self.proofs)
                    path.write_bytes(original)
            changed = copy.deepcopy(self.proofs)
            changed[0]['request_locator_kind'] = 'LEGACY_WORKING_LOCATOR'
            with self.assertRaisesRegex(NormalSourceAuthorityError, 'IMPORTED_REQUEST_PROOF_CHANGED'):
                verify_saved_source_proofs(data_root=root, proofs=changed)


if __name__ == '__main__':
    unittest.main()
