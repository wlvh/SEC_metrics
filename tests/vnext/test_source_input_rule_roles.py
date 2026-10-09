"""Source-root bootstrap roles; synthetic directory, no source/result credit."""
from pathlib import Path
import tempfile
import unittest

from vnext.canonical import canonical_json_bytes, sha256_file
from vnext.continuous_sec_acquisition import initialize_source_inputs
from vnext.normal_source_authority import ROOT, MANIFEST_PATH


class SourceInputRuleRolesTest(unittest.TestCase):
    def test_old_presentation_is_preserved_without_blocking_current_rule_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'source-baseline.json').write_bytes(canonical_json_bytes(value={
                'baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH)}))
            presentation = 'config/ordinary_public_projection_v1.json'
            business = 'config/issue28_normal_results_v2.json'
            old = b'{"synthetic_historical_presentation":true}\n'
            path = root/presentation; path.parent.mkdir(); path.write_bytes(old)
            files = {p:{'sha256':sha256_file(path=ROOT/p), 'size':(ROOT/p).stat().st_size}
                     for p in (presentation,business)}
            requirement = {'parent_snapshot':{'execution_authority':{'files':files},
                'policy':{'presentation_paths':[presentation]}}}
            initialize_source_inputs(root=root,requirement=requirement)
            self.assertEqual(path.read_bytes(),old)
            self.assertEqual((root/business).read_bytes(),(ROOT/business).read_bytes())
            # A genuine business-rule mismatch remains a refusal, not a silent
            # replacement of arbitrary configuration in the source directory.
            (root/business).write_bytes(b'changed business rules')
            with self.assertRaisesRegex(ValueError,'Immutable receipt bytes differ'):
                initialize_source_inputs(root=root,requirement=requirement)
            self.assertEqual(path.read_bytes(),old)
            self.assertEqual((root/business).read_bytes(),b'changed business rules')
