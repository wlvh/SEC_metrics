"""Read-only audit of the two claims behind Southwest's current E01=2."""
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
RUN_ROOT = Path('/private/tmp/issue28-southwest-current-36-cli-20260929/state/'
    'southwest_airlines/metrics/E01')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def item_section(raw):
    visible = html.unescape(re.sub(r'<[^>]+>', ' ', raw.decode('utf-8-sig')))
    visible = re.sub(r'\s+', ' ', visible)
    headings = list(re.finditer(r'\bItem\s+\d+\.\d+\b', visible, re.I))
    selected = [i for i, match in enumerate(headings)
                if re.match(r'Item\s+1\.01\s+Entry into a Material Definitive Agreement\.',
                            visible[match.start():], re.I)]
    assert len(selected) == 1
    i = selected[0]
    end = headings[i+1].start() if i+1 < len(headings) else len(visible)
    return visible[headings[i].start():end].strip()


protected = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {name: digest(path) for name, path in protected.items()}
state = json.loads((RUN_ROOT/'current.json').read_text())
assert state['successful_attempt']
attempt = RUN_ROOT/'attempts'/state['successful_attempt']
records = [json.loads(line) for line in
           (attempt/'runs/E01/records.jsonl').read_text().splitlines()]
result, = [row for row in records if row['record_type'] == 'METRIC_RESULT'
           and row['metric_id'] == 'E01']
observation, = [row for row in records
                if row['record_type'] == 'VERIFIED_OBSERVATION'
                and row['metric_id'] == 'E01']
assert result['value'] == '2' and result['publication'] == 'PUBLISHED'
matched_ids = set(observation['source_binding']['matched_verified_claim_ids'])
assert len(matched_ids) == 2
claims = [row for row in records
          if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'
          and row['verified_claim_id'] in matched_ids]
assert len(claims) == 2
references = {row['source_reference_id']: row for row in records
              if row['record_type'] == 'SOURCE_REFERENCE'}
rows = []
for claim in sorted(claims, key=lambda row: row['attributes']['accession']):
    attrs = claim['attributes']
    assert attrs['item_code'] == '1.01'
    primary = references[attrs['primary_source_reference_id']]
    url_parts = urlparse(primary['source_url']).path.strip('/').split('/')
    assert url_parts[:3] == ['Archives', 'edgar', 'data']
    source = (ACQUIRED/'source-inputs/evidence/accession_materials'/
        ('southwest_airlines_'+url_parts[3]+'_'+primary['accession'].replace('-', ''))/
        primary['document_name'])
    assert source.is_file()
    raw_hash = digest(source)
    assert primary['raw_asset_id'] == 'sha256:' + raw_hash
    section = item_section(source.read_bytes())
    rows.append({'accession': primary['accession'],
        'item_code': attrs['item_code'],
        'verified_claim_id': claim['verified_claim_id'],
        'hdr_brief': attrs['brief'],
        'hdr_brief_source': attrs['brief_source'],
        'primary_source_url': primary['source_url'],
        'primary_source_reference_id': primary['source_reference_id'],
        'primary_sha256': raw_hash,
        'item_1_01_visible_text': section,
        'item_1_01_visible_text_sha256': hashlib.sha256(section.encode()).hexdigest()})
assert 'Amendment to Cooperation Agreement' in rows[0]['item_1_01_visible_text']
assert 'public offering' in rows[1]['item_1_01_visible_text']
assert 'debt securities' in rows[1]['item_1_01_visible_text']
route = json.loads((ROOT/'catalog/event_routes.json').read_text())
rule = route['routes']['E01']
assert '1.01' in rule['direct_item_codes']
synthetic_8_01 = '8-K item 8.01 parsed from hdr.sgml'
aliases = next(row['aliases'] for row in rule['keyword_item_rules']
               if row['item_code'] == '8.01')
assert not any(alias.casefold() in synthetic_8_01.casefold() for alias in aliases)
assert before == {name: digest(path) for name, path in protected.items()}
body = {'record_type': 'ISSUE28_E01_SOUTHWEST_CURRENT_SOURCE_CONFLICT_AUDIT',
    'product_head': '76ebe42ea28eedaac640c70d127475296361d1f3',
    'run_id': json.loads((attempt/'runs/E01/manifest.json').read_text())['run_id'],
    'result_id': result['result_id'],
    'result_value': result['value'],
    'result_publication': result['publication'],
    'matched_claim_count': len(rows), 'matched_item_codes': ['1.01', '1.01'],
    'selected_primary_sections': rows,
    'event_route_catalog_sha256': digest(ROOT/'catalog/event_routes.json'),
    'item_1_01_is_direct_without_body_confirmation': True,
    'hdr_8_01_synthetic_brief_has_no_E01_alias': True,
    'current_business_meaning_requires_decision': True,
    'historical_run_or_result_modified': False,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'other_E01_coordinates_audited': False,
    'all390_acceptance': False}
(HERE/'audit.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'result_value': result['value'],
    'claims': [(row['accession'], row['item_code']) for row in rows],
    'primary_bytes_verified': len(rows), 'real_calls': [0, 0, 0]}, sort_keys=True))
