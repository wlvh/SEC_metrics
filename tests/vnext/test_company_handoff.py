"""Transaction tests; source authentication has separate material probes."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext import company_handoff as handoff


class CompanyImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root/'state'
        self.packages = []
        for ordinal in (1, 2):
            package = self.root/str(ordinal)
            (package/'config').mkdir(parents=True)
            (package/'evidence').mkdir()
            checkpoint = {'checkpoint_id': 'sha256:'+str(ordinal)*64,
                          'company_id': 'test_company', 'rules': {},
                          'source_history_id': 'same_history'}
            (package/handoff.EXPORT_PATH).write_text(json.dumps(checkpoint))
            (package/'evidence/requests_log.csv').write_text('baseline\n'+'new\n'*(ordinal-1))
            self.packages.append(package)
        self.guard = patch.object(handoff, 'check_package', side_effect=self.authenticated)
        self.guard.start()
        self.addCleanup(self.guard.stop)

    @staticmethod
    def authenticated(*, package_root, company_id):
        result = json.loads((package_root/handoff.EXPORT_PATH).read_text())
        if result['company_id'] != company_id:
            raise ValueError('WRONG_COMPANY')
        return result

    def install(self, ordinal, fault=None):
        return handoff.install_company(package_root=self.packages[ordinal-1],
            state_root=self.state, company_id='test_company', fault=fault)

    def test_interruptions_keep_previous_result_and_source_then_allow_retry(self):
        for position in ('before_source_replace', 'after_old_source_move', 'after_new_source_move'):
            with self.subTest(position=position):
                self.state = self.root/position
                first = self.install(1)
                saved_result = self.state/'company-results.json'
                saved_result.write_bytes(b'previous result bytes')
                def fail(step):
                    if step == position:
                        raise RuntimeError('INJECTED_INTERRUPTION')
                with self.assertRaisesRegex(RuntimeError, 'INJECTED_INTERRUPTION'):
                    self.install(2, fail)
                with handoff.locked_company(self.state):
                    restored = handoff.recover_import(self.state)
                self.assertEqual(first['checkpoint_id'], restored['checkpoint_id'])
                self.assertEqual(first['checkpoint_id'], self.authenticated(
                    package_root=self.state/'source', company_id='test_company')['checkpoint_id'])
                self.assertEqual(b'previous result bytes', saved_result.read_bytes())
                self.assertEqual('FAILED', json.loads((self.state/'latest_import.json').read_text())['status'])
                second = self.install(2)
                self.assertEqual(first['source_root'], second['source_root'])
                self.assertEqual('ALREADY_INSTALLED', self.install(2)['status'])
                self.assertTrue((self.state/'versions'/first['checkpoint_id'][7:]).is_dir())

    def test_declared_event_saved_paths_preserve_original_body_and_header_locators(self):
        base = 'https://www.sec.gov/Archives/edgar/data/1048286/000119312525009110/'
        requirements = [{'source_url': base+name, 'roles': [role]} for name, role in (
            ('d890503d8k.htm', 'fiscal_event_primary'),
            ('0001193125-25-009110.hdr.sgml', 'fiscal_event_header'))]
        rows = [{'source_url': r['source_url'], 'document_name': r['source_url'].rsplit('/',1)[-1],
                 'status_code': '200', 'error': '',
                 'repo_relative_path': 'evidence/request_attempts/'+str(i)+'/body',
                 'headers_repo_relative_path': 'evidence/request_attempts/'+str(i)+'/headers.json'}
                for i,r in enumerate(requirements)]
        saved = json.loads(json.dumps(rows))
        aliases = handoff.event_saved_paths(requirements, rows, 'marriott_international', {1048286})
        self.assertEqual(len(aliases), 4)
        self.assertEqual(aliases['evidence/accession_materials/marriott_international_1048286_000119312525009110/d890503d8k.htm'], rows[0]['repo_relative_path'])
        self.assertEqual(rows, saved)
        existing = self.root/'evidence/accession_materials/old_display_1048286_000119312525009110'
        existing.mkdir(parents=True)
        retained = handoff.event_saved_paths(requirements, rows, 'marriott_international', {1048286}, source_root=self.root)
        self.assertTrue(all('old_display_1048286_' in p for p in retained))
        with self.assertRaisesRegex(ValueError, 'SAVED_PATH_IDENTITY_INVALID'):
            handoff.event_saved_paths(requirements, rows, 'different_company', {1})
        failed = {**rows[0], 'status_code': '403', 'error': 'HTTP 403'}
        after = handoff.event_saved_paths(requirements, [*rows,failed], 'marriott_international', {1048286})
        self.assertFalse(any('d890503d8k.htm' in p for p in after))

    def test_first_install_interruption_never_exposes_uncommitted_source(self):
        for position in ('before_source_replace', 'after_old_source_move', 'after_new_source_move'):
            with self.subTest(position=position):
                self.state = self.root/position
                def fail(step):
                    if step == position:
                        raise RuntimeError('INJECTED_INTERRUPTION')
                with self.assertRaises(RuntimeError):
                    self.install(1, fail)
                with handoff.locked_company(self.state):
                    self.assertIsNone(handoff.recover_import(self.state))
                self.assertFalse((self.state/'source').exists())
                self.assertEqual('INSTALLED', self.install(1)['status'])

    def test_wrong_company_cannot_replace_committed_source(self):
        first = self.install(1)
        with self.assertRaisesRegex(ValueError, 'WRONG_COMPANY'):
            handoff.install_company(package_root=self.packages[1], state_root=self.state,
                                    company_id='another_company')
        self.assertEqual(first['checkpoint_id'], json.loads((self.state/'current_source.json').read_text())['checkpoint_id'])

    def test_nonprefix_history_cannot_replace_committed_source(self):
        self.install(1)
        (self.packages[1]/'evidence/requests_log.csv').write_text('unrelated\n')
        with self.assertRaisesRegex(ValueError, 'SOURCE_HISTORY_NOT_PREFIX'):
            self.install(2)

    def test_symlink_paths_and_unowned_sources_are_refused(self):
        self.state.mkdir()
        (self.state/'source').mkdir()
        with self.assertRaisesRegex(ValueError, 'UNOWNED_SOURCE_ROOT'):
            self.install(1)
        alias = self.root/'alias'
        alias.symlink_to(self.packages[0], target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'NONALIAS_PATH_REQUIRED'):
            handoff.install_company(package_root=alias, state_root=self.state,
                                    company_id='test_company')

    def test_import_and_compute_lock_blocks_another_process(self):
        with handoff.locked_company(self.state):
            code = ('import fcntl,os,sys; fd=os.open(sys.argv[1],os.O_RDONLY); '
                    'fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)')
            child = subprocess.run([sys.executable, '-c', code, str(self.state)],
                                   capture_output=True, text=True)
            self.assertNotEqual(0, child.returncode)
            self.assertIn('BlockingIOError', child.stderr)

    def test_nonroot_readonly_packages_install_update_and_recover(self):
        for package in self.packages:
            for p in [package,*package.rglob('*')]:p.chmod(p.stat().st_mode & ~0o222)
        first=self.install(1)
        self.assertEqual('INSTALLED',first['status'])
        self.assertEqual(0,self.packages[0].stat().st_mode & 0o222)
        def interrupt(step):
            if step=='after_old_source_move':raise RuntimeError('INJECTED_READONLY_INTERRUPTION')
        with self.assertRaisesRegex(RuntimeError,'INJECTED_READONLY_INTERRUPTION'):self.install(2,interrupt)
        with handoff.locked_company(self.state):
            self.assertEqual(first['checkpoint_id'],handoff.recover_import(self.state)['checkpoint_id'])
        second=self.install(2)
        self.assertEqual('INSTALLED',second['status'])
        self.assertEqual(first['source_root'],second['source_root'])
        self.assertEqual('ALREADY_INSTALLED',self.install(2)['status'])
        self.assertEqual(0,(self.state/'versions'/second['checkpoint_id'][7:]).stat().st_mode & 0o222)


class SourceOnlyRulesTest(unittest.TestCase):
    def test_saved_native_assessment_is_not_collected_as_a_rule(self):
        from scripts.vnext.capacity_assessment_input import EXPORT_PATHS
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'config').mkdir()
            (root/'config/ordinary_policy.json').write_text('{"scope":"RULE"}')
            for relative in EXPORT_PATHS.values():
                (root/relative).write_text('{"company_id":"other_company","native_requests":[]}')
            manifest = root/'requirements/issue_28_v13/baseline_manifest.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"execution_authority":{"files":{}}}')
            with patch.object(handoff, 'ROOT', root):
                rules = handoff.rule_bindings()
            self.assertIn('config/ordinary_policy.json', rules)
            self.assertTrue(set(EXPORT_PATHS.values()).isdisjoint(rules))


if __name__ == '__main__':
    unittest.main()
