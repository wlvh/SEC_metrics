"""Read two existing positive E01 coordinates and their original 8-K bodies.

This is a bounded source audit, not a route revision, count, or native Run.
Only #28 repository/cumulative sources and existing archived Runs are read.
"""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.deterministic_router import _visible_text


ARCHIVES = (
    ('salesforce', 'ordinary-document-identity',
     'live-restored-salesforce-native/', 'salesforce'),
    ('paramount_skydance_paramount_global', 'ordinary-registered-event-runs',
     'registered-event-native-second/', 'paramount_skydance_paramount_global'),
)


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _archived_bytes(archive, index, name):
    descriptor = index['files'][name]
    content = archive.extractfile(descriptor['archive_member']).read()
    assert _sha(content) == descriptor['sha256']
    assert len(content) == descriptor['size']
    return content


def _original(reference):
    accession = reference['accession'].replace('-', '')
    name = reference['document_name']
    candidates = list((ROOT/'evidence/accession_materials').glob(
        '*_' + accession + '/' + name))
    candidates += list((ACQUIRED/'source-inputs/evidence/continuous-acquisition').glob(
        '*/' + name))
    matches = [path for path in candidates if
        'sha256:' + _sha(path.read_bytes()) == reference['raw_asset_id']]
    assert matches, (accession, name, reference['raw_asset_id'])
    path = matches[0]
    content = path.read_bytes()
    assert _sha(content) == reference['raw_asset_id'][7:]
    return path, content


def _read_coordinate(company, directory, prefix, run_company):
    root = ROOT/'docs/evidence/issue28_continuous'/directory
    index = json.loads((root/'material-index.json').read_text())
    assert _sha((root/'material.tar.gz').read_bytes()) == index['archive_binding']['sha256']
    with tarfile.open(root/'material.tar.gz', 'r:gz') as archive:
        selection = json.loads(_archived_bytes(archive, index,
            prefix + 'selections/' + run_company + '-E01.json'))
        records = [json.loads(line) for line in _archived_bytes(archive, index,
            prefix + 'runs/' + run_company + '/E01/records.jsonl').splitlines()]
    selected_ids = selection['matched_verified_claim_ids']
    assert len(selected_ids) == len(set(selected_ids))
    by_claim = {row['verified_claim_id']: row for row in records
                if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'}
    by_reference = {row['source_reference_id']: row for row in records
                    if row['record_type'] == 'SOURCE_REFERENCE'}
    result, = [row for row in records if row['record_type'] == 'METRIC_RESULT']
    assert int(result['value']) == len(selected_ids)
    claims = []
    for claim_id in selected_ids:
        claim = by_claim[claim_id]
        attributes = claim['attributes']
        reference = by_reference[attributes['primary_source_reference_id']]
        assert reference['accession'] == attributes['accession']
        assert reference['company_id'] == company
        path, content = _original(reference)
        visible = _visible_text(raw_bytes=content)
        marker = 'Item ' + attributes['item_code']
        start = visible.find(marker)
        assert start >= 0
        explanatory = visible.find('Explanatory Note')
        claims.append({
            'claim_id': claim_id,
            'item_code': attributes['item_code'],
            'accession': attributes['accession'],
            'primary_source_reference_id': reference['source_reference_id'],
            'primary_source_url': reference['source_url'],
            'primary_document_path': str(path),
            'primary_sha256': _sha(content),
            'primary_bytes': len(content),
            'item_heading_excerpt': visible[start:start+1200],
            'explanatory_note_excerpt': (visible[explanatory:explanatory+1000]
                                         if explanatory >= 0 else None),
        })
    return {'company_id': company, 'archived_result_id': result['result_id'],
            'archived_value': result['value'],
            'archive_path': str(root/'material.tar.gz'),
            'archive_sha256': index['archive_binding']['sha256'],
            'selected_item_claims': claims,
            'distinct_selected_accessions': sorted({row['accession'] for row in claims})}


body = {'record_type': 'ISSUE28_E01_TWO_POSITIVE_COORDINATE_SOURCE_AUDIT',
        'status': 'SOURCE_CONTEXT_ONLY_NO_BUSINESS_RECLASSIFICATION',
        'coordinates': [_read_coordinate(*args) for args in ARCHIVES],
        'new_provider_paid_sec_calls': [0, 0, 0],
        'historical_run_or_result_modified': False,
        'current_E01_business_credit_granted': False,
        'production_authorized': False}
(HERE/'audit.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
parent_path = ROOT/'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
parent = json.loads(parent_path.read_text())
parent_rows = {row['company_id']: row for row in parent['rows']
               if row['metric_id'] == 'E01'}
for coordinate in body['coordinates']:
    assert parent_rows[coordinate['company_id']]['value'] == coordinate['archived_value']
delta = {
    'record_type': 'ISSUE28_CURRENT_390_TWO_COORDINATE_E01_DEFINITION_DELTA',
    'parent_index': str(parent_path.relative_to(ROOT)),
    'parent_index_sha256': _sha(parent_path.read_bytes()),
    'source_audit': str((HERE/'audit.json').relative_to(ROOT)),
    'coordinates': [{
        'coordinate_key': row['company_id'] + ':E01',
        'historical_result_id_retained': row['archived_result_id'],
        'historical_value_retained': row['archived_value'],
        'historical_publication_record_retained': True,
        'current_MA_announcement_credit':
            'UNVERIFIED_PENDING_ITEM_CODE_VS_CONTENT_AND_COUNTING_DEFINITION',
        'original_primary_bytes_verified': True,
        'selected_claim_count': len(row['selected_item_claims']),
        'distinct_selected_accession_count': len(row['distinct_selected_accessions']),
    } for row in body['coordinates']],
    'new_complete_coordinate_count': 0,
    'other_388_coordinates_revalidated': False,
    'all390_acceptance': False,
    'production_authorized': False,
    'new_provider_paid_sec_calls': [0, 0, 0],
}
(HERE/'delta.json').write_text(json.dumps(delta, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'],
    'companies': [row['company_id'] for row in body['coordinates']],
    'claim_counts': [len(row['selected_item_claims']) for row in body['coordinates']],
    'distinct_accessions': [len(row['distinct_selected_accessions']) for row in body['coordinates']]},
    sort_keys=True))
