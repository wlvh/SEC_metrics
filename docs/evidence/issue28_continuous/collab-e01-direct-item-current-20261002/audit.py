"""Inspect exact #28 E01 claims against four saved primary 8-K originals.

This is a bounded source audit, not a replacement E01 matcher or Result.
"""
import hashlib
from html.parser import HTMLParser
import html
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CASES = {
    'ford_motor_company': ('ford', '0000037996-25-000067',
                           'Twenty-Second Amendment', 'Credit Agreement'),
    'lumen_technologies': ('lumen', '0000018926-25-000039',
                           'refinanced all of the outstanding secured term B-1 loan facilities',
                           'First Amendment'),
    'macys': ('macys', '0000794367-25-000087',
             'Refinancing and Extension of Existing Asset-Based Credit Facility',
             'Credit Facility'),
    'southwest_airlines': ('southwest', '0001193125-25-262544',
                           'public offering of $1,500,000,000 aggregate principal amount of debt securities',
                           'Notes'),
}


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def source_bytes(records_path, records, accession, role):
    reference = next(row for row in records if row['record_type'] == 'SOURCE_REFERENCE'
                     and row['accession'] == accession and row['source_role'] == role)
    blob = next(row for row in records if row['record_type'] == 'RAW_BLOB'
                and row['raw_asset_id'] == reference['raw_asset_id'])
    path = ROOT / blob['storage_uri']
    if not path.exists():
        path = records_path.parents[2] / 'data' / blob['storage_uri']
    raw = path.read_bytes()
    assert len(raw) == blob['byte_length']
    assert 'sha256:' + hashlib.sha256(raw).hexdigest() == blob['raw_asset_id']
    return reference, raw


rows = []
for company, (short, accession, anchor, second) in CASES.items():
    paths = list(Path('/private/tmp').glob(
        'issue28-' + ('southwest' if company == 'southwest_airlines' else company) +
        '-current-36-cli-20260929/state/' + company +
        '/metrics/E01/attempts/*/runs/E01/records.jsonl'))
    assert len(paths) == 1, (company, paths)
    records_path = paths[0]
    records = [json.loads(line) for line in records_path.read_bytes().splitlines()]
    result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
                  and row['metric_id'] == 'E01')
    observation = next(row for row in records if row['record_type'] == 'VERIFIED_OBSERVATION'
                       and row['metric_id'] == 'E01')
    selected = set(observation['source_binding']['matched_verified_claim_ids'])
    claim = next(row for row in records if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'
                 and row['attributes']['accession'] == accession
                 and row['attributes']['item_code'] == '1.01')
    assert claim['verified_claim_id'] in selected
    assert claim['attributes']['brief_source'] == 'HDR_SGML_ITEM_CODE'
    primary, raw = source_bytes(records_path, records, accession, 'fy_8k_primary')
    header, header_bytes = source_bytes(records_path, records, accession, 'fy_8k_header')
    assert accession.encode() in header_bytes and b'1.01' in header_bytes
    parser = Visible()
    parser.feed(raw.decode('utf-8', errors='replace'))
    visible = ' '.join(html.unescape(' '.join(parser.parts)).split())
    assert re.search(r'Item\s+1\.01\b', visible, re.I)
    assert anchor in visible and second in visible
    # These complete originals have no M&A assertion even outside Item 1.01.
    assert not re.search(r'\b(?:merger|acquisition|acquire|acquired|business combination|asset sale)\b',
                         visible, re.I), (company, accession)
    anchor_at = visible.index(anchor)
    comparison_path = ROOT / ('docs/evidence/issue28_continuous/ordinary-' + short +
                              '-current-36-cli-20260929/comparison.json')
    comparison = json.loads(comparison_path.read_text())
    compared = next(row for row in comparison['rows'] if row['metric_id'] == 'E01')
    assert compared['historical_result_id'] == compared['current_result_id'] == result['result_id']
    assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
    manifest = json.loads((records_path.parent / 'manifest.json').read_text())
    rows.append({'company_id': company, 'period_end': result['period_end'],
                 'old_result_id': result['result_id'], 'old_run_id': manifest['run_id'],
                 'old_value': result['value'], 'selected_claim_id': claim['verified_claim_id'],
                 'claim_item_code': '1.01', 'accession': accession,
                 'primary_source_reference_id': primary['source_reference_id'],
                 'header_source_reference_id': header['source_reference_id'],
                 'primary_raw_asset_id': primary['raw_asset_id'],
                 'header_raw_asset_id': header['raw_asset_id'],
                 'visible_anchor': anchor,
                 'source_excerpt': visible[max(0, anchor_at-180):anchor_at+700],
                 'old_390_same_result_id': True,
                 'scope_conclusion': 'ONE_SELECTED_FINANCING_ITEM_IS_NOT_CONTENT_CONFIRMED_M_AND_A'})

output = {'record_type': 'ISSUE28_E01_CURRENT_DIRECT_ITEM_SOURCE_AUDIT',
          'fixed_own_head_before_audit': '0ef64f9cc5ef7bab52668ca2c64e94eeee0ffb4d',
          'peer_fixed_read': '488a61734978adaa57e82ec0654e75a0af284cfb',
          'approved_target': 'CONTENT_CONFIRMED_M_AND_A_ANNOUNCEMENTS',
          'scope': 'Four exact old current Results; one authenticated false-positive claim in each',
          'results': rows, 'new_real_calls': [0, 0, 0],
          'old_runs_and_results_preserved': True, 'new_result_created': False,
          'unexamined_selected_claims_not_certified': True,
          'paramount_and_salesforce_not_classified_by_this_audit': True}
(HERE / 'audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'confirmed_current_result_ids': len(rows),
                  'companies': [row['company_id'] for row in rows],
                  'new_real_calls': [0, 0, 0]}))
