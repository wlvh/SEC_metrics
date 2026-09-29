"""Check the opt-in 8.01 source connector on a saved Southwest 8-K."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
RUN_ROOT = Path('/private/tmp/issue28-southwest-current-36-cli-20260929/state/'
    'southwest_airlines/metrics/E01')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.e01_item_source import (bound_801_primary_section,
                                   verify_bound_801_primary_section)

state = json.loads((RUN_ROOT/'current.json').read_text())
attempt = RUN_ROOT/'attempts'/state['successful_attempt']
records = [json.loads(line) for line in
    (attempt/'runs/E01/records.jsonl').read_text().splitlines()]
claim, = [row for row in records
    if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'
    and row['attributes']['accession'] == '0001193125-25-262544'
    and row['attributes']['item_code'] == '8.01']
reference, = [row for row in records if row['record_type'] == 'SOURCE_REFERENCE'
    and row['source_reference_id'] == claim['attributes']['primary_source_reference_id']]
primary = (ACQUIRED/'source-inputs/evidence/accession_materials/'
    'southwest_airlines_92380_000119312525262544/d83756d8k.htm')
raw = primary.read_bytes()
assert reference['raw_asset_id'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
old_claim_id = claim['verified_claim_id']
section = bound_801_primary_section(claim=claim,
    primary_source_reference=reference, primary_document_bytes=raw)
assert verify_bound_801_primary_section(section=section, claim=claim,
    primary_source_reference=reference, primary_document_bytes=raw) == section
assert claim['verified_claim_id'] == old_claim_id
assert section['verified_claim_id'] == old_claim_id
assert section['section_text'].startswith('Item 8.01 Other Events')
assert 'public offering of the Notes' in section['section_text']
assert 'Item 9.01' not in section['section_text']
assert not section['metric_result_created']
assert not section['source_acquisition_credit']
body = {'record_type': 'ISSUE28_E01_SOUTHWEST_801_SOURCE_BOUND_PROBE',
    'product_head_before_new_module': '76ebe42ea28eedaac640c70d127475296361d1f3',
    'new_module_sha256': hashlib.sha256((ROOT/'scripts/vnext/e01_item_source.py').read_bytes()).hexdigest(),
    'accession': reference['accession'],
    'verified_claim_id_retained': old_claim_id,
    'primary_source_reference_id': reference['source_reference_id'],
    'primary_raw_asset_id': reference['raw_asset_id'],
    'section_id': section['section_id'],
    'section_text_sha256': section['section_text_sha256'],
    'section_visible_chars': len(section['section_text']),
    'section_starts_at_item_8_01': True,
    'section_excludes_item_9_01': True,
    'business_classification_or_metric_result_created': False,
    'source_acquisition_credit': False,
    'new_real_calls': [0, 0, 0]}
(HERE/'item-source.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'accession': body['accession'],
    'section_visible_chars': body['section_visible_chars'],
    'claim_id_retained': True, 'result_created': False}, sort_keys=True))
