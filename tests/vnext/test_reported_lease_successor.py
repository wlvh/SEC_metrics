"""Original reopening boundaries; full lease arithmetic lives in parser tests."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vnext.ordinary_reported_lease_scope import _case_sources, _reported


class ReportedLeaseSuccessorTest(unittest.TestCase):
    def fixture(self, root):
        reports = {}; proofs = []
        for kind in ('primary', 'xml'):
            raw = ('original-' + kind).encode(); digest = hashlib.sha256(raw).hexdigest()
            (root / (kind + '.txt')).write_bytes(raw)
            ref = {'source_reference_id': kind, 'raw_asset_id': 'sha256:' + digest,
                'source_url': 'https://www.sec.gov/' + kind, 'accession': 'annual'}
            reports[kind] = [{'source_reference': ref}]
            proofs.append({'source_url': ref['source_url'], 'accession': 'annual',
                'content_sha256': digest, 'request_repo_relative_path': kind + '.txt'})
        scope = {'record_type': 'old', 'scope_class': 'industrial', 'scope_source_id': 'old',
            'reported_components': {'current_debt': {'source_reports': reports}},
            'limitations': ['INDUSTRIAL_ATTRIBUTABLE_EQUITY_NOT_ESTABLISHED'],
            'definition_complete': False, 'ratio': None}
        return {'selection': {'scope_source': scope}, 'source_proofs': proofs}

    def test_duplicate_same_original_proofs_are_not_a_second_source(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); case = self.fixture(root)
            case['source_proofs'] *= 2
            sources = _case_sources(case, root)
            self.assertEqual(b'original-primary', sources['primary']['raw_bytes'])
            self.assertEqual(b'original-xml', sources['xml']['raw_bytes'])

    def test_wrong_url_or_accession_cannot_supply_the_original(self):
        for field in ('source_url', 'accession'):
            with self.subTest(field=field), TemporaryDirectory() as folder:
                root = Path(folder); case = self.fixture(root)
                case['source_proofs'][0][field] = 'another-source'
                with self.assertRaisesRegex(ValueError, 'RELATION_ORIGINAL_PROOF_NOT_UNIQUE:primary'):
                    _case_sources(case, root)

    def test_two_distinct_original_paths_remain_ambiguous(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); case = self.fixture(root)
            (root / 'copy.txt').write_bytes(b'original-primary')
            case['source_proofs'].append({**case['source_proofs'][0], 'request_repo_relative_path': 'copy.txt'})
            with self.assertRaisesRegex(ValueError, 'RELATION_ORIGINAL_PROOF_NOT_UNIQUE:primary'):
                _case_sources(case, root)

    def test_body_change_after_inherited_check_is_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); case = self.fixture(root)
            (root / 'primary.txt').write_bytes(b'changed-after-check')
            sources = _case_sources(case, root)
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_BINDING_CHANGED'):
                _reported(case['selection']['scope_source'], sources=sources,
                          annual={'filing': {'accessionNumber': 'annual'}})

    def test_bank_relation_does_not_create_a_lease_inclusion_or_ratio(self):
        scope = {'scope_class': 'bank_funding', 'scope_source_id': 'old',
                 'definition_complete': False, 'ratio': None, 'limitations': ['INCOMPLETE']}
        result = _reported(scope, sources={}, annual={})
        self.assertEqual('NOT_APPLICABLE_TO_BANK_SCOPE', result['lease_inclusion']['status'])
        self.assertIsNone(result['ratio']); self.assertFalse(result['definition_complete'])
        self.assertNotIn('lease_inclusion', scope)

