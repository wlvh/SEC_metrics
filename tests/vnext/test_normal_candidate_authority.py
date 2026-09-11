"""An imported candidate profile cannot redefine its installed authority."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.requirements import load_requirement_snapshot


class NormalCandidateAuthorityTest(unittest.TestCase):
    def test_installed_draft_loads_without_production_or_spending_permission(self):
        profile = load_requirement_snapshot(snapshot_dir=REPO_ROOT / 'requirements/issue_28_v11')
        self.assertEqual('NOT_ACTIVATED', profile['activation_state'])
        self.assertFalse(profile['policy']['production_authorized'])
        self.assertFalse(profile['policy']['provider_enabled'])
        self.assertGreater(len(profile['execution_authority']['files']), 200)

    def test_importer_cannot_prune_execution_binding_or_rewrite_any_snapshot_file(self):
        original = REPO_ROOT / 'requirements/issue_28_v11'
        for name in ['baseline_manifest.json', 'CONTRACT.md', 'decision_register.json',
                     'invariant_profile.json', 'transfer_manifest.json']:
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='normal-profile-adversary-') as tmp:
                path = Path(tmp) / 'requirements/issue_28_v11'
                shutil.copytree(original, path)
                target = path / name
                if name == 'baseline_manifest.json':
                    data = json.loads(target.read_text())
                    data['execution_authority']['files'] = {}
                    target.write_text(json.dumps(data))
                else:
                    target.write_bytes(target.read_bytes() + b' ')
                with self.assertRaisesRegex(ValueError, 'installed snapshot differs'):
                    load_requirement_snapshot(snapshot_dir=path)


if __name__ == '__main__':
    unittest.main()
