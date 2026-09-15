"""Two real saved-source types through the reusable complete-version adapter."""
import csv
import io
import json
import os
from pathlib import Path
import shutil
import socket
import unittest
from unittest.mock import patch

from vnext import normal_run_v3 as normal, ordinary_release_preparation as release, run_store
from vnext.canonical import content_hash, sha256_file
from vnext.ratchet_release import _tree_files


@unittest.skipUnless(os.environ.get('ORDINARY_RELEASE_MATERIAL_ROOT'), 'Requires a fresh external material root')
class OrdinaryReleasePreparationMaterialTest(unittest.TestCase):
    def test_two_native_types_complete_version_and_resigned_row_rejection(self):
        root = Path(os.environ['ORDINARY_RELEASE_MATERIAL_ROOT']).resolve()
        self.assertFalse(root.exists()); root.mkdir(parents=True)
        pointer = normal.ROOT / 'outputs/active_publication.json'
        original_pointer = pointer.read_bytes()
        inputs = []
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')), \
             patch('sec_http.urlopen', side_effect=AssertionError('HTTP forbidden')):
            for company, metric in [('pfizer', 'B01'), ('salesforce', 'C02')]:
                base = root / 'inputs' / metric
                data, run = base / 'data', base / 'run'
                if os.environ.get('ORDINARY_RELEASE_INPUTS_ROOT'):
                    old = Path(os.environ['ORDINARY_RELEASE_INPUTS_ROOT']).resolve() / metric
                    shutil.copytree(old / 'data', data); shutil.copytree(old / 'run', run)
                else:
                    normal.install_normal_inputs(data_root=data, company_id=company, metric_id=metric)
                    created = normal.create_normal_run(data_root=data, run_dir=run, company_id=company, metric_id=metric)
                    self.assertEqual('PUBLISHED', created['result']['publication'])
                inputs.append({'data_root': data, 'run_dir': run})
            package = root / 'prepared'
            prepared = release.prepare(native_runs=inputs, output_root=package)
            composition = prepared['composition']
            selected = {r['metric_id']: r for r in composition['selected_results']}
            self.assertEqual({'B01', 'C02'}, set(selected))
            self.assertEqual('TEXT_V1', selected['C02']['value_kind'])
            self.assertNotEqual('TEXT_V1', selected['B01']['value_kind'])
            self.assertTrue(all(r['source_admission']['source_credit'] == 'PREEXISTING_SAVED_ACQUISITIONS_ONLY'
                                for r in selected.values()))
            self.assertEqual(388, len(composition['unselected_coordinate_keys']))
            self.assertFalse(composition['production_authorized'])
            self.assertFalse(composition['switch_available'])
            self.assertFalse(composition['full390_acceptance'])
            self.assertFalse((package / 'publication_manifest.json').exists())
            # Copied inputs and predecessor are sufficient; original Run/data
            # directories need not remain at their preparation locations.
            (root / 'inputs').rename(root / 'inputs-unavailable')
            verified = release.verify(preparation_root=package, expected_preparation_id=prepared['preparation_id'])
            self.assertEqual(prepared, verified)
            for binding in composition['selected_results']:
                for source in binding['source_locations']:
                    self.assertEqual(source['sha256'], sha256_file(path=package / source['package_path']))
            matrix = package / 'metrics_matrix.csv'
            manifest = package / release.MANIFEST
            saved_matrix, saved_manifest = matrix.read_bytes(), manifest.read_bytes()
            rows = list(csv.DictReader(io.StringIO(saved_matrix.decode())))
            changed = next(row for row in rows if row['company'] == 'Pfizer' and row['metric_id'] == 'B01')
            changed['value'] = '999999999999999'
            matrix.write_bytes(release.pub._csv_bytes(rows=rows, fieldnames=release.pub.METRIC_FIELDS))
            forged = json.loads(saved_manifest)
            forged['composition']['matrix_hash'] = content_hash(value=rows)
            files = _tree_files(root=package); files.pop(release.MANIFEST)
            forged['files'] = files
            forged['preparation_id'] = content_hash(value={k: v for k, v in forged.items() if k != 'preparation_id'})
            manifest.write_bytes(release._json(forged))
            with self.assertRaisesRegex(ValueError, 'ORDINARY_RELEASE_NATIVE_COMPOSITION_CHANGED'):
                release.verify(preparation_root=package)
            (root / 'resigned-row-attack.json').write_text(json.dumps({'status': 'REJECTED',
                'reason': 'ORDINARY_RELEASE_NATIVE_COMPOSITION_CHANGED',
                'tampered_matrix_sha256': sha256_file(path=matrix), 'forged_preparation_id': forged['preparation_id']}, indent=2) + '\n')
            matrix.write_bytes(saved_matrix); manifest.write_bytes(saved_manifest)
            # No stale file hash is the reason for rejecting a missing text
            # review: update the outer inventory and let native replay decide.
            records = package / selected['C02']['run_path'] / 'records.jsonl'
            original_records = records.read_bytes()
            values = [json.loads(line) for line in original_records.splitlines() if line]
            review_types = {r['record_type'] for r in values if 'REVIEW' in r['record_type']}
            self.assertTrue(review_types)
            records.write_bytes(b'\n'.join(line for line in original_records.splitlines()
                if line and json.loads(line)['record_type'] not in review_types) + b'\n')
            forged = json.loads(saved_manifest); files = _tree_files(root=package); files.pop(release.MANIFEST)
            forged['files'] = files
            forged['preparation_id'] = content_hash(value={k: v for k, v in forged.items() if k != 'preparation_id'})
            manifest.write_bytes(release._json(forged))
            with self.assertRaises((ValueError, run_store.RunStoreError)) as missing_review:
                release.verify(preparation_root=package)
            self.assertNotIn('empty record', str(missing_review.exception))
            (root / 'removed-review-attack.json').write_text(json.dumps({'status': 'REJECTED',
                'reason': str(missing_review.exception), 'removed_types': sorted(review_types)}, indent=2) + '\n')
            records.write_bytes(original_records); manifest.write_bytes(saved_manifest)
            self.assertEqual(prepared, release.verify(preparation_root=package, expected_preparation_id=prepared['preparation_id']))
        self.assertEqual(original_pointer, pointer.read_bytes())
        (root / 'summary.json').write_text(json.dumps({'status': 'PASS',
            'preparation_id': prepared['preparation_id'], 'selected_results': composition['selected_results'],
            'public_row_count': composition['public_row_count'],
            'inherited_public_row_count': composition['inherited_public_row_count'],
            'source_credit': 'SAVED_SOURCE_NATIVE_REPLAY_NO_NEW_ACQUISITION',
            'reused_completed_native_inputs': bool(os.environ.get('ORDINARY_RELEASE_INPUTS_ROOT')),
            'new_real_source_or_provider_calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'checks': ['numeric-and-text-native-run', 'full-predecessor-preserved',
                'original-input-directories-unavailable', 'all-selected-evidence-resolved',
                'resigned-public-value-rejected', 'review-removal-rejected', 'restored-package-replay', 'actual-pointer-unchanged'],
            'production_authorized': False, 'full390_acceptance': False}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
