"""Cheap cold release-authority/scanner gate before full fifteen-Run replay.

This is dependency coverage only, not qualification or publication evidence.
The long release rehearsal separately checks the actual sealed bundle.
"""

import json
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_issue28_v2 import clone_authority
from vnext.canonical import atomic_write_json, content_hash, strict_json_file


class R4PortableDependencyTest(unittest.TestCase):
    def test_actual_successor_plan_and_old_a13_substitutions_fail(self):
        from vnext.r4_release import _release_authority
        with tempfile.TemporaryDirectory(prefix='r4-release-authority-mutation-') as directory:
            root = clone_authority(directory).parent.parent
            relative = 'config/release_plans/issue_28_r4_scoped_engine_v2.json'
            shutil.copy2(REPO_ROOT / relative, root / relative)
            original = strict_json_file(path=root / relative)
            self.assertEqual(len(_release_authority(root)[-1]), 60)
            mutations = (
                ('issue15_plan', None, None),
                ('issue15_requirement', 'requirement_id', 'issue_15_v1'),
                ('closure', 'requirement_closure_hash', 'sha256:' + '0' * 64),
                ('predecessor', 'parent_release_plan_id', 'issue_15_zero_ai_r2'),
                ('metric_set', 'added_metric_ids', ['A03', 'A04', 'A09', 'A11', 'A12', 'B06']),
            )
            for name, field, value in mutations:
                candidate = deepcopy(original)
                if name == 'issue15_plan':
                    candidate = strict_json_file(path=root / 'config/release_plans/issue_15_lodging_r3.json')
                else:
                    candidate[field] = value
                    candidate['release_plan_content_id'] = content_hash(value={k: v for k, v in candidate.items()
                        if k != 'release_plan_content_id'})
                try:
                    atomic_write_json(path=root / relative, value=candidate)
                    with self.subTest(mutation=name), self.assertRaises(ValueError):
                        _release_authority(root)
                finally:
                    atomic_write_json(path=root / relative, value=original)
            target = next((root / 'catalog/r4_v2').glob('A13_*.md'))
            legacy = next((REPO_ROOT / 'catalog/metrics').glob('A13_*.md'))
            target.write_bytes(legacy.read_bytes())
            with self.assertRaisesRegex(ValueError, 'Successor execution authority bytes differ: catalog/r4_v2/A13_'):
                _release_authority(root)

    def test_cold_release_and_scanners_need_no_original_checkout(self):
        baseline = strict_json_file(path=REPO_ROOT / 'requirements/issue_28_v2/baseline_manifest.json')
        bound = baseline['execution_authority']['files']
        foundation = strict_json_file(path=REPO_ROOT / 'requirements/issue_15_v1/foundation_verification_receipt.json')
        self.assertIn('config/vnext_release_plan.json', bound)
        for row in foundation['receipt_bindings']:
            if row['path'].startswith('outputs/acceptance_receipts/'):
                self.assertEqual(bound[row['path']], {key: row[key] for key in ('sha256', 'size')})
        # A future R4 switch changes this public mirror. It is retained as R3
        # input inside the publication, never newly pinned as current runtime.
        self.assertNotIn('outputs/scalability_audit.csv', bound)
        with tempfile.TemporaryDirectory(prefix='r4-cold-dependency-') as directory:
            snapshot = clone_authority(directory)
            root = snapshot.parent.parent.resolve()
            relative = 'config/release_plans/issue_28_r4_scoped_engine_v2.json'
            shutil.copy2(REPO_ROOT / relative, root / relative)
            code = textwrap.dedent('''
                import json, pathlib, sys
                root = pathlib.Path.cwd().resolve()
                forbidden = pathlib.Path(sys.argv[1]).resolve()
                def audit(event, args):
                    if event.startswith('socket.'):
                        raise AssertionError('NO_NETWORK')
                    if event in {'open', 'os.listdir', 'os.scandir'} and args and isinstance(args[0], (str, bytes)):
                        import os
                        path = pathlib.Path(os.fsdecode(args[0])).resolve()
                        if path.is_relative_to(forbidden):
                            raise AssertionError('NO_SOURCE_CHECKOUT: ' + str(path))
                sys.addaudithook(audit)
                sys.path[:0] = [str(root / 'scripts'), str(root)]
                from vnext import publication, r4_release
                requirement, plan, registry, specs, tasks, paths, keys = r4_release._release_authority(root)
                assert len(keys) == 60 and sum(k['applicability'] == 'APPLICABLE' for k in keys) == 6
                semantic = publication._execute_semantic_audit(repo_root=root)
                scalability = publication._execute_scalability_audit(repo_root=root)
                assert semantic['status'] == 'PASS' and semantic['hits'] == []
                assert not any(r.get('allowed') not in {'1', 'true', 'True'} for r in scalability)
                for name, module in list(sys.modules.items()):
                    if name.startswith('vnext.') and getattr(module, '__file__', None):
                        assert pathlib.Path(module.__file__).resolve().is_relative_to(root)
                print(json.dumps({'status': 'PASS', 'expected_coordinates': len(keys),
                    'semantic': 'PASS', 'scalability': 'PASS', 'provider_paid_sec': [0,0,0]}))
            ''')
            command = [sys.executable, '-B', '-c', code, str(REPO_ROOT.resolve())]
            if sys.platform == 'darwin':
                policy = ('(version 1)(allow default)(deny network*)'
                    + '(deny file-read* (subpath ' + json.dumps(str(REPO_ROOT.resolve())) + '))'
                    + '(deny file-write* (subpath ' + json.dumps(str(root)) + '))')
                command = ['/usr/bin/sandbox-exec', '-p', policy, *command]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-12000:])
            self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1])['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
