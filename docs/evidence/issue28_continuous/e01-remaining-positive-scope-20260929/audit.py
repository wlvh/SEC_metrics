"""Reprepare current E01 positive claims for three companies from saved #28 originals.

No Run is installed and no network, legacy answer input, #47 source or model is used.
The displayed excerpts are audit aids, not accepted M&A classifications.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.deterministic_router import _visible_text
from vnext.normal_run_v3 import prepare_case


def sha(content):
    return hashlib.sha256(content).hexdigest()


parent_path = ROOT/'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
parent = json.loads(parent_path.read_text())
parent_rows = {row['company_id']: row for row in parent['rows']
               if row['metric_id'] == 'E01'}
companies = ('ford_motor_company', 'lumen_technologies', 'macys')
coordinates = []
for company in companies:
    with original_sources_only():
        case = prepare_case(data_root=ROOT, company_id=company, metric_id='E01')
    selected_ids = case['selection']['matched_verified_claim_ids']
    by_claim = {row['verified_claim_id']: row for row in case['expected_records']
                if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'}
    by_reference = {row['source_reference_id']: row for row in case['source_records']
                    if row['record_type'] == 'SOURCE_REFERENCE'}
    assert len(selected_ids) == len(set(selected_ids))
    assert int(case['results']['E01']['value']) == len(selected_ids)
    assert parent_rows[company]['value'] == case['results']['E01']['value']
    claims = []
    for claim_id in selected_ids:
        claim = by_claim[claim_id]
        attributes = claim['attributes']
        reference = by_reference[attributes['primary_source_reference_id']]
        assert reference['company_id'] == company
        assert reference['accession'] == attributes['accession']
        paths = list((ROOT/'evidence/accession_materials').glob(
            '*_' + reference['accession'].replace('-', '') + '/' +
            reference['document_name']))
        originals = [(path, path.read_bytes()) for path in paths]
        matches = [(path, raw) for path, raw in originals if
                   reference['raw_asset_id'] == 'sha256:' + sha(raw)]
        assert len(matches) == 1, (company, reference['accession'])
        path, raw = matches[0]
        visible = _visible_text(raw_bytes=raw)
        anchor = visible.find('Item ' + attributes['item_code'])
        assert anchor >= 0
        claims.append({
            'claim_id': claim_id,
            'item_code': attributes['item_code'],
            'accession': attributes['accession'],
            'primary_source_reference_id': reference['source_reference_id'],
            'primary_source_url': reference['source_url'],
            'primary_document_path': str(path.relative_to(ROOT)),
            'primary_sha256': sha(raw),
            'primary_bytes': len(raw),
            'item_heading_excerpt': visible[anchor:anchor+1800],
        })
    coordinates.append({
        'company_id': company,
        'historical_index_value_retained': parent_rows[company]['value'],
        'current_prepared_value': case['results']['E01']['value'],
        'current_prepared_result_id_not_installed': case['results']['E01']['result_id'],
        'selected_item_claims': claims,
        'distinct_selected_accessions': sorted({row['accession'] for row in claims}),
    })

body = {
    'record_type': 'ISSUE28_E01_THREE_POSITIVE_COORDINATE_CURRENT_SOURCE_AUDIT',
    'status': 'SOURCE_CONTEXT_ONLY_NO_BUSINESS_RECLASSIFICATION',
    'current_code_root': str(ROOT),
    'parent_index': str(parent_path.relative_to(ROOT)),
    'parent_index_sha256': sha(parent_path.read_bytes()),
    'coordinates': coordinates,
    'historical_run_or_result_modified': False,
    'new_native_run_created': False,
    'current_E01_business_credit_granted': False,
    'new_provider_paid_sec_calls': [0, 0, 0],
    'production_authorized': False,
}
(HERE/'audit.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
delta = {
    'record_type': 'ISSUE28_CURRENT_390_THREE_COORDINATE_E01_DEFINITION_DELTA',
    'parent_index': body['parent_index'],
    'parent_index_sha256': body['parent_index_sha256'],
    'source_audit': str((HERE/'audit.json').relative_to(ROOT)),
    'coordinates': [{
        'coordinate_key': row['company_id'] + ':E01',
        'historical_value_retained': row['historical_index_value_retained'],
        'historical_publication_record_retained': True,
        'current_MA_announcement_credit':
            'UNVERIFIED_PENDING_ITEM_CODE_VS_CONTENT_DEFINITION',
        'current_prepared_selected_item_count': len(row['selected_item_claims']),
        'original_primary_bytes_verified': True,
    } for row in coordinates],
    'new_complete_coordinate_count': 0,
    'other_387_coordinates_revalidated': False,
    'all390_acceptance': False,
    'production_authorized': False,
    'new_provider_paid_sec_calls': [0, 0, 0],
}
(HERE/'delta.json').write_text(json.dumps(delta, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'],
    'companies': [row['company_id'] for row in coordinates],
    'selected_claims': [len(row['selected_item_claims']) for row in coordinates],
    'distinct_filings': [len(row['distinct_selected_accessions']) for row in coordinates]},
    sort_keys=True))
