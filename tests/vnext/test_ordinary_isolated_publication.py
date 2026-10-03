"""Private release boundaries; full rehearsal requires a current native package."""
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext import ordinary_isolated_publication as release, publication as pub


class OrdinaryIsolatedPublicationBoundaryTest(unittest.TestCase):
    def test_official_root_ancestors_and_descendants_rejected(self):
        for root in (release.ROOT, release.ROOT.parent, release.ROOT / 'private-preview'):
            with self.subTest(root=str(root)), self.assertRaisesRegex(pub.PublicationError, 'OFFICIAL_ROOT_FORBIDDEN'):
                release._safe_root(root)

    def test_alias_and_active_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'actual').mkdir(); (root / 'alias').symlink_to(root / 'actual')
            with self.assertRaisesRegex(pub.PublicationError, 'UNALIASED_ROOT_REQUIRED'):
                release._safe_root(root / 'alias' / 'child')
            (root / 'outputs').mkdir(); (root / 'outputs/active_publication.json').write_text('{}')
            with self.assertRaisesRegex(pub.PublicationError, 'ACTIVE_OR_CHECKOUT_ANCESTOR'):
                release._safe_root(root / 'child')

    def test_existing_active_root_never_adopted_by_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root / 'outputs').mkdir()
            pointer = root / 'outputs/active_publication.json'; pointer.write_text('{"original":true}')
            with patch.object(release.preparation, 'verify', side_effect=AssertionError('input should not be read')):
                with self.assertRaisesRegex(pub.PublicationError, 'FRESH_PRIVATE_ROOT_REQUIRED'):
                    release.stage(preparation_root=root / 'unused', publication_root=root)
            self.assertEqual('{"original":true}', pointer.read_text())

    def test_local_json_cannot_supply_private_capability(self):
        with self.assertRaisesRegex(pub.PublicationError, 'PRIVATE_CAPABILITY_REQUIRED'):
            release.commit_authority(bundle_dir=Path('/private/tmp/untrusted'), manifest={})
        with self.assertRaisesRegex(pub.PublicationError, 'PRIVATE_CAPABILITY_REQUIRED'):
            release.guard_switch(pointer_path=Path('/private/tmp/untrusted'), manifest={},
                                 expected_active_id='untrusted', switch_mode='COMMIT')
        with self.assertRaisesRegex(pub.PublicationError, 'PRIVATE_CAPABILITY_REQUIRED'):
            release.guard_recovery(pointer_path=Path('/private/tmp/untrusted'), intent={})
        self.assertIsNone(release.recovery_hooks())

    def test_mirror_guard_preserves_identity_under_existing_exclusive_lock(self):
        # Run in a bounded child so regression to a nested flock cannot hang CI.
        import subprocess
        import sys
        import textwrap
        worker = textwrap.dedent("""
            import fcntl, sys, tempfile
            from pathlib import Path
            from types import SimpleNamespace
            from unittest.mock import patch
            from vnext import ordinary_isolated_publication as release, publication as pub
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve(); (root / 'outputs').mkdir()
                lock = root / 'outputs/active_publication.json.lock'
                selected = {'publication_id': 'selected', 'previous_publication_id': 'previous'}
                with lock.open('a+b') as held:
                    fcntl.flock(held, fcntl.LOCK_EX)
                    with patch.object(release, '_edge', return_value=(root, selected)), \
                         patch.object(pub.PublicationView, '_open_paths',
                                      return_value=SimpleNamespace(publication_id=sys.argv[1])) as internal:
                        try:
                            release.guard_mirror_repair(publication_root=root)
                        except pub.PublicationError as error:
                            assert sys.argv[1] == 'foreign'
                            assert str(error) == 'ORDINARY_PUBLICATION_MIRROR_EDGE_CHANGED'
                        else:
                            assert sys.argv[1] in {'selected', 'previous'}
                        internal.assert_called_once_with(publications_dir=root / 'outputs/publications',
                                                         pointer_path=root / 'outputs/active_publication.json')
        """)
        env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(release.ROOT / 'scripts'), str(release.ROOT)]),
               'PYTHONDONTWRITEBYTECODE': '1'}
        for active in ('selected', 'previous', 'foreign'):
            with self.subTest(active=active):
                result = subprocess.run([sys.executable, '-c', worker, active], cwd=release.ROOT,
                                        env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_self_signed_marker_cannot_register_an_existing_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            marker = release._record({'schema_version': 1, 'purpose': release.CREDIT,
                'publication_root': str(root), 'official_root': str(release.ROOT),
                'preparation_id': 'sha256:' + '0' * 64, 'predecessor': {},
                'production_authorized': False}, 'workspace_id')
            (root / release.MARKER).write_bytes(release._json(marker))
            with self.assertRaisesRegex(pub.PublicationError, 'CREATOR_PROCESS_REQUIRED'):
                with release._capability(root, {}):
                    self.fail('Caller marker became an owned workspace')


@unittest.skipUnless(os.environ.get('ORDINARY_ISOLATED_PUBLICATION_PREPARATION')
                     and os.environ.get('ORDINARY_ISOLATED_PUBLICATION_ROOT'),
                     'Requires a current complete native preparation and fresh private destination')
class OrdinaryIsolatedPublicationMaterialTest(unittest.TestCase):
    def test_stage_switch_rollback_restore_and_interrupted_recovery(self):
        root = Path(os.environ['ORDINARY_ISOLATED_PUBLICATION_ROOT']).resolve()
        source = Path(os.environ['ORDINARY_ISOLATED_PUBLICATION_PREPARATION']).resolve()
        self.assertFalse(root.exists())
        pointer = release.ROOT / 'outputs/active_publication.json'; original = pointer.read_bytes()
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')), \
             patch('sec_http.urlopen', side_effect=AssertionError('HTTP forbidden')):
            staged = release.stage(preparation_root=source, publication_root=root)
            candidate = staged['publication_id']; before = release.read_back(publication_root=root)
            after = release.switch(publication_root=root, publication_id=candidate, operation='publish')
            self.assertEqual(candidate, after['publication_id'])
            rolled = release.switch(publication_root=root, publication_id=candidate, operation='rollback')
            self.assertEqual(before, rolled)
            restored = release.switch(publication_root=root, publication_id=candidate, operation='restore')
            self.assertEqual(after, restored)
            release.switch(publication_root=root, publication_id=candidate, operation='rollback')

            class Interrupted(BaseException):
                pass

            def interrupt(*, fault_point):
                if fault_point == 'POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT':
                    raise Interrupted()

            with patch.object(pub, '_fault_injection_checkpoint', side_effect=interrupt):
                with self.assertRaises(Interrupted):
                    release.switch(publication_root=root, publication_id=candidate, operation='restore')
            recovered = release.switch(publication_root=root, publication_id=candidate, operation='recover')
            self.assertEqual(after, recovered)
            mirror = root / 'outputs/metrics_matrix.csv'; mirror.write_text('damaged')
            repaired = release.switch(publication_root=root, publication_id=candidate, operation='recover')
            self.assertEqual(after, repaired)
        self.assertEqual(original, pointer.read_bytes())
        (root / 'rehearsal-summary.json').write_text(json.dumps({'status': 'PASS', 'staged': staged,
            'predecessor_read_back': before, 'candidate_read_back': after,
            'checks': ['stage', 'publish', 'read-back', 'rollback', 'restore',
                       'post-pointer-interruption-recovery', 'damaged-mirror-repair', 'official-pointer-unchanged'],
            'credit': release.CREDIT, 'new_calls': [0, 0, 0]}, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
