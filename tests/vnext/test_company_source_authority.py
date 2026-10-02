"""An input package cannot enroll itself in the computing trust domain."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext.canonical import canonical_json_bytes, content_hash
from scripts.vnext.company_source_authority import (
    EXPORT_PATH, RECORD_TYPE, TRUST_VARIABLE, trusted_checkpoint, require_company)


class CompanyTrustTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        self.trust = self.root/'trust'
        (self.source/'config').mkdir(parents=True)
        self.trust.mkdir()
        body = {'record_type': RECORD_TYPE, 'company_id': 'one_company',
                'real_sec_credit': False, 'production_authorized': False}
        self.checkpoint = {**body, 'checkpoint_id': content_hash(value=body)}
        self.write(self.source/EXPORT_PATH, self.checkpoint)
        self.write(self.trust/(self.checkpoint['checkpoint_id'][7:]+'.json'), self.checkpoint)
        environment = patch.dict(os.environ, {TRUST_VARIABLE: str(self.trust)})
        environment.start()
        self.addCleanup(environment.stop)

    @staticmethod
    def write(path, value):
        path.write_bytes(canonical_json_bytes(value=value))

    def test_exact_independent_record_is_accepted(self):
        self.assertEqual(self.checkpoint, trusted_checkpoint(self.source))

    def test_rehashing_package_does_not_install_new_authority(self):
        changed = {**self.checkpoint, 'real_sec_credit': True}
        changed['checkpoint_id'] = content_hash(value={k:v for k,v in changed.items() if k!='checkpoint_id'})
        self.write(self.source/EXPORT_PATH, changed)
        with self.assertRaises(ValueError):
            trusted_checkpoint(self.source)

    def test_matching_id_with_changed_content_is_refused(self):
        self.write(self.source/EXPORT_PATH, {**self.checkpoint, 'real_sec_credit': True})
        with self.assertRaisesRegex(ValueError, 'NOT_IN_INSTALLED_TRUST'):
            trusted_checkpoint(self.source)

    def test_package_cannot_supply_its_own_trust_directory(self):
        local = self.source/'trust'; local.mkdir()
        self.write(local/(self.checkpoint['checkpoint_id'][7:]+'.json'), self.checkpoint)
        with patch.dict(os.environ, {TRUST_VARIABLE: str(local)}):
            with self.assertRaisesRegex(ValueError, 'TRUST_MUST_BE_SEPARATE'):
                trusted_checkpoint(self.source)

    def test_cross_company_is_refused_before_source_discovery(self):
        with self.assertRaisesRegex(ValueError, 'WRONG_COMPANY'):
            require_company(source_root=self.source, company_id='different_company')

    def test_alias_to_trusted_record_is_refused(self):
        registered = self.trust/(self.checkpoint['checkpoint_id'][7:]+'.json')
        moved = self.root/'outside.json'
        registered.rename(moved)
        registered.symlink_to(moved)
        with self.assertRaises(ValueError):
            trusted_checkpoint(self.source)


if __name__ == '__main__':
    unittest.main()
