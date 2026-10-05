"""Census dispatch tests with real trust lookup/parser and a stub ledger replay.

Full acquisition/admission replay is covered by the saved-material probes;
these tests isolate the added file-set boundary, without financial gold data.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext.canonical import canonical_json_bytes, content_hash, sha256_file
from scripts.vnext.company_event_census import installed_event_filings
from scripts.vnext.company_source_authority import EXPORT_PATH, RECORD_TYPE, TRUST_VARIABLE


class CompanyEventCensusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        self.trust = self.root/'trust'
        (self.source/'config').mkdir(parents=True)
        self.trust.mkdir()
        (self.source/'config/company_registry.csv').write_text(
            'company_id,primary_cik,roles\ncompany,123,primary:123;predecessor:456\n')
        self.first = self.header('123', '0000000123-23-000001', '20230715')
        self.header('456', '0000000456-23-000002', '20230615')
        self.header('123', '0000000123-22-000003', '20220615')
        self.header('123', '0000000123-23-000004', '20230815', form='10-K')
        files = {p.relative_to(self.source).as_posix():
                 {'sha256': sha256_file(path=p), 'size': p.stat().st_size}
                 for p in self.source.rglob('*.hdr.sgml')}
        body = {'record_type': RECORD_TYPE, 'company_id': 'company', 'files': files}
        self.admission = {**body, 'checkpoint_id': content_hash(value=body)}
        self.write(self.source/EXPORT_PATH, self.admission)
        self.write(self.trust/(self.admission['checkpoint_id'][7:]+'.json'), self.admission)
        environment = patch.dict(os.environ, {TRUST_VARIABLE: str(self.trust)})
        environment.start(); self.addCleanup(environment.stop)
        ledger = patch('scripts.vnext.company_source_authority._validate_admission_bytes')
        ledger.start(); self.addCleanup(ledger.stop)

    @staticmethod
    def write(path, value):
        path.write_bytes(canonical_json_bytes(value=value))

    def header(self, cik, accession, filed, form='8-K'):
        directory = self.source/'evidence/accession_materials'/(
            'company_'+cik+'_'+accession.replace('-', ''))
        directory.mkdir(parents=True)
        path = directory/(accession+'.hdr.sgml')
        path.write_text('<ACCESSION-NUMBER>'+accession+'\n<TYPE>'+form+
                        '\n<FILING-DATE>'+filed+'\n')
        return path

    def census(self, company='company', ciks=('123', '456')):
        return installed_event_filings(source_root=self.source, company_id=company,
            allowed_ciks=ciks, period_start='2023-01-01', period_end='2023-12-31')

    def test_original_window_form_and_predecessor_parsing_is_retained(self):
        self.assertEqual(['0000000123-23-000001', '0000000456-23-000002'],
                         [row['accession'] for row in self.census()])
        self.assertEqual(['123', '456'], [row['cik'] for row in self.census()])

    def test_extra_header_cannot_become_an_installed_census(self):
        self.header('123', '0000000123-23-000005', '20230915')
        with self.assertRaisesRegex(ValueError, 'FILE_SET_DIFFERS_FROM_TRUST'):
            self.census()

    def test_missing_declared_header_is_refused(self):
        self.first.unlink()
        with self.assertRaises(ValueError):
            self.census()

    def test_unauthorized_cik_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'WRONG_CIK'):
            self.census(ciks=('789',))

    def test_another_company_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'WRONG_COMPANY'):
            self.census(company='another')

    def test_rehashed_header_manifest_does_not_enroll_itself(self):
        extra = self.header('123', '0000000123-23-000005', '20230915')
        changed = {**self.admission, 'files': {**self.admission['files'],
            extra.relative_to(self.source).as_posix():
            {'sha256': sha256_file(path=extra), 'size': extra.stat().st_size}}}
        changed['checkpoint_id'] = content_hash(value={
            k:v for k,v in changed.items() if k != 'checkpoint_id'})
        self.write(self.source/EXPORT_PATH, changed)
        with self.assertRaises(ValueError):
            self.census()

    def test_alias_to_header_is_refused(self):
        elsewhere = self.root/'outside.hdr.sgml'
        self.first.rename(elsewhere)
        self.first.symlink_to(elsewhere)
        with self.assertRaises(ValueError):
            self.census()


if __name__ == '__main__':
    unittest.main()
