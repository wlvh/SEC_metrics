"""Bind the Pfizer Metsera 8.01 body to #28's exact old zero Result."""
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.deterministic_router import match_event_claims


def sha(data):
    return hashlib.sha256(data).hexdigest()


accession = '0000078003-25-000159'
run = next(Path('/private/tmp/issue28-pfizer-current-36-cli-20260929/'
                'state/pfizer/metrics/E01/attempts').glob('*/runs/E01'))
records = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
              and row['metric_id'] == 'E01')
assert result['value'] == '0' and result['period_end'] == '2025-12-31'
comparison = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                         'ordinary-pfizer-current-36-cli-20260929/comparison.json').read_text())
prior = next(row for row in comparison['rows'] if row['metric_id'] == 'E01')
assert prior['historical_result_id'] == prior['current_result_id'] == result['result_id']
sources = {row['source_role']: row for row in records
           if row['record_type'] == 'SOURCE_REFERENCE'
           and row['accession'] == accession}
assert {'fy_8k_primary', 'fy_8k_header'} <= set(sources)
raw_records = {row['raw_asset_id']: row for row in records if row['record_type'] == 'RAW_BLOB'}
originals = {}
for role in ('fy_8k_primary', 'fy_8k_header'):
    ref = sources[role]
    blob = raw_records[ref['raw_asset_id']]
    raw = (ROOT / blob['storage_uri']).read_bytes()
    assert len(raw) == blob['byte_length'] and 'sha256:' + sha(raw) == blob['raw_asset_id']
    originals[role] = raw
header = originals['fy_8k_header'].decode('utf-8', errors='strict')
assert '<ACCESSION-NUMBER>' + accession in header and '<ITEMS>8.01' in header
primary = originals['fy_8k_primary'].decode('utf-8', errors='strict')
needle = 'Item 8.01 Results of Other Events'
assert primary.count(needle) == 1
index = primary.index(needle)
visible = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', primary[index:index + 2200])).split())
assert 'Pfizer Inc.' in visible
assert 'completed the previously announced acquisition of Metsera, Inc.' in visible
assert 'Agreement and Plan of Merger' in visible
claim = next(row for row in records if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'
             and row.get('attributes', {}).get('accession') == accession
             and row['attributes'].get('item_code') == '8.01')
assert claim['attributes']['brief'] == '8-K item 8.01 parsed from hdr.sgml'
assert claim['attributes']['brief_source'] == 'HDR_SGML_ITEM_CODE'
catalog = json.loads((ROOT / 'catalog/event_routes.json').read_text())
assert {'acquisition', 'merger'} <= set(catalog['routes']['E01']['keyword_item_rules'][0]['aliases'])
assert match_event_claims(metric_id='E01', claims=[claim], catalog=catalog) == []
body = {'record_type': 'ISSUE28_E01_PFIZER_2025_EXACT_ZERO_SOURCE_CONFLICT',
        'status': 'CONFIRMED_OLD_ZERO_EXCLUDES_RELEVANT_8_01_BODY',
        'company_id': 'pfizer', 'metric_id': 'E01', 'period_end': result['period_end'],
        'old_result_id': result['result_id'],
        'old_run_id': json.loads((run / 'manifest.json').read_text())['run_id'],
        'historical_390_same_old_result_id': True,
        'accession': accession,
        'source_references': {role: sources[role]['source_reference_id']
                              for role in originals},
        'raw_assets': {role: sources[role]['raw_asset_id'] for role in originals},
        'visible_item_excerpt': visible[:1000],
        'old_hdr_generated_brief': claim['attributes']['brief'],
        'old_matcher_returns_empty_for_this_8_01': True,
        'peer_fixed_read': 'bc0a2ac7ed1c89ac5d3c309d52f4519898ba6ee7',
        'peer_defect_id': 'E01_PFIZER_2025_EIGHT_O_ONE_BRANCH_NEVER_READS_THE_ITEM',
        'peer_result_credit_not_copied': True,
        'old_run_result_sources_preserved': True,
        'new_real_calls': [0, 0, 0],
        'scope_limit': 'One exact old #28 Result and one saved 8.01 body; no new E01 value, de-duplication or complete company result.'}
(HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'], 'old_result_id': result['result_id'],
                  'accession': accession, 'new_real_calls': [0, 0, 0]}))
