"""The candidate CLI can only create fresh output outside production roots."""
from pathlib import Path
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from tools.vnext_normal_candidate import _new_external_root


class NormalCandidateCliBoundaryTest(unittest.TestCase):
    def test_source_existing_output_and_publication_ancestor_are_rejected(self):
        with self.assertRaises(ValueError):
            _new_external_root(REPO_ROOT / 'candidate-output')
        with self.assertRaises(ValueError):
            _new_external_root(Path('relative-output'))
        with tempfile.TemporaryDirectory(prefix='normal-cli-boundary-') as tmp:
            base = Path(tmp).resolve()
            with self.assertRaises(ValueError):
                _new_external_root(base)
            target = base / 'fresh'
            self.assertEqual(target, _new_external_root(target))
            self.assertFalse(target.exists())
            (base / 'outputs').mkdir()
            (base / 'outputs/active_publication.json').write_text('{}')
            with self.assertRaises(ValueError):
                _new_external_root(target)

    def test_output_alias_cannot_reuse_an_existing_directory(self):
        with tempfile.TemporaryDirectory(prefix='normal-cli-alias-') as tmp:
            base = Path(tmp).resolve()
            (base / 'existing').mkdir()
            alias = base / 'alias'
            alias.symlink_to(base / 'existing', target_is_directory=True)
            with self.assertRaises(ValueError):
                _new_external_root(alias)


if __name__ == '__main__':
    unittest.main()
