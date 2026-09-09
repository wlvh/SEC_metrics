"""Real publication boundary tests; no model or SEC transport is constructed."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vnext import annual_publication as annual, annual_adoption as adoption
from vnext import invocation_control as controller, publication as pub
from vnext.canonical import content_hash
from vnext.records import ANNUAL_PUBLICATION_MANIFEST_TYPE, validate_record
from vnext.requirements import load_requirement_snapshot

ROOT = Path(__file__).resolve().parents[2]


class AnnualPublicationBoundaryTest(unittest.TestCase):
    def test_actual_repository_and_unowned_active_roots_are_rejected(self):
        for root in (ROOT, ROOT / 'temporary', ROOT.parent):
            with self.subTest(root=root), self.assertRaises(ValueError):
                annual.safe_root(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'outputs').mkdir()
            (root / 'outputs/active_publication.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'UNOWNED_ACTIVE'):
                annual.safe_root(root)

    def test_historical_views_cannot_be_forged_or_sent_to_execution(self):
        with self.assertRaises(controller.InvocationControlError):
            controller.HistoricalAnnualInvocationView(factory=object(), authority={})
        with self.assertRaises(ValueError):
            adoption._ReadOnlyReplay(object(), ROOT, {})
        with self.assertRaises(controller.InvocationControlError):
            controller.execute_successor_invocation(repo_root=ROOT, authority={'verified': True},
                plan={'record_type': 'SUCCESSOR_AI_INVOCATION_PLAN'})
        with self.assertRaisesRegex(ValueError, 'CAPABILITY_REQUIRED'):
            annual.guard_mirror_repair(publication_root=ROOT)

    def test_frozen_registry_scanner_reads_code_as_data(self):
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'config').mkdir()
            shutil.copyfile(ROOT / 'config/company_registry.csv', root / 'config/company_registry.csv')
            (root / 'scripts').mkdir(); (root / 'tools').mkdir()
            (root / 'scripts/example.py').write_text("company = '1048286'\n")
            rows = annual._scalability_snapshot(root)
            self.assertTrue(any(r['type'] == 'cik' and r['allowed'] == '0' for r in rows))

    def test_annual_manifest_cannot_acquire_formal_credit_or_disguise_type(self):
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v6')
        pointer = json.loads((ROOT / 'outputs/active_publication.json').read_text())
        original = json.loads((ROOT / 'outputs/publications' / pointer['publication_id'] / 'publication_manifest.json').read_text())
        body = {k: v for k, v in original.items() if k not in {'record_type', 'publication_id'}}
        body.update(artifact_requirement_generation='EXPLICIT_REQUIREMENT_V1',
            requirement_id=requirement['requirement_id'], requirement_hashes=requirement['hashes'],
            requirement_closure_hash=requirement['requirement_closure_hash'], projection_requirement_hashes=requirement['hashes'],
            annual_adoption_receipt_id='sha256:' + '0' * 64, publication_credit=annual.CREDIT)
        manifest = {'record_type': ANNUAL_PUBLICATION_MANIFEST_TYPE,
                    'publication_id': 'publication_' + content_hash(value=body)[7:], **body}
        self.assertEqual(manifest, validate_record(record=manifest))
        upgraded = copy.deepcopy(manifest); upgraded['publication_credit'] = 'LIVE'
        with self.assertRaisesRegex(ValueError, 'no formal publication credit'):
            validate_record(record=upgraded)
        disguised = copy.deepcopy(manifest); disguised['record_type'] = 'SUCCESSOR_PUBLICATION_MANIFEST'
        with self.assertRaises(ValueError):
            validate_record(record=disguised)


if __name__ == '__main__':
    unittest.main()
