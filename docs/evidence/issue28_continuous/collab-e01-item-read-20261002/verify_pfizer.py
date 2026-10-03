"""Read the saved Pfizer 8.01 from its own authenticated primary body."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.e01_item_source import (bound_801_primary_section,
                                   verify_bound_801_primary_section)


def sha(data):
    return hashlib.sha256(data).hexdigest()


run = next(Path('/private/tmp/issue28-pfizer-current-36-cli-20260929/'
                'state/pfizer/metrics/E01/attempts').glob('*/runs/E01'))
rows = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
accession = '0000078003-25-000159'
claim = next(row for row in rows if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'
             and row.get('attributes', {}).get('accession') == accession
             and row['attributes'].get('item_code') == '8.01')
source = next(row for row in rows if row['record_type'] == 'SOURCE_REFERENCE'
              and row['source_reference_id'] == claim['attributes']['primary_source_reference_id'])
blob = next(row for row in rows if row['record_type'] == 'RAW_BLOB'
            and row['raw_asset_id'] == source['raw_asset_id'])
raw = (ROOT / blob['storage_uri']).read_bytes()
assert 'sha256:' + sha(raw) == blob['raw_asset_id'] and len(raw) == blob['byte_length']
ledger = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/claims.jsonl')
source_log = ROOT / 'evidence/requests_log.csv'
before = sha(ledger.read_bytes()), sha(source_log.read_bytes())
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    section = bound_801_primary_section(claim=claim, primary_source_reference=source,
                                        primary_document_bytes=raw)
    assert section == verify_bound_801_primary_section(
        section=section, claim=claim, primary_source_reference=source,
        primary_document_bytes=raw)
    try:
        bound_801_primary_section(claim=claim, primary_source_reference=source,
                                  primary_document_bytes=raw + b'altered')
        raise AssertionError('CHANGED_ORIGINAL_WAS_ACCEPTED')
    except ValueError as error:
        assert 'Adapter bytes differ from SourceReference' in str(error)
    try:
        verify_bound_801_primary_section(
            section={**section, 'section_text': 'another item'}, claim=claim,
            primary_source_reference=source, primary_document_bytes=raw)
        raise AssertionError('CHANGED_SECTION_WAS_ACCEPTED')
    except ValueError as error:
        assert 'E01_ITEM_SOURCE_SECTION_CHANGED' in str(error)
assert before == (sha(ledger.read_bytes()), sha(source_log.read_bytes()))
text = section['section_text']
assert text.startswith('Item 8.01 Results of Other Events')
assert 'completed the previously announced acquisition of Metsera, Inc.' in text
assert 'Agreement and Plan of Merger' in text
assert 'SIGNATURES' not in text
body = {'record_type': 'ISSUE28_E01_SAVED_PFIZER_8_01_SOURCE_READER',
        'status': 'PASS_AUTHENTICATED_PRIMARY_SECTION_AND_REPLAY',
        'company_id': 'pfizer', 'accession': accession,
        'verified_claim_id': claim['verified_claim_id'],
        'primary_source_reference_id': source['source_reference_id'],
        'primary_raw_asset_id': blob['raw_asset_id'],
        'section_id': section['section_id'],
        'section_text_sha256': section['section_text_sha256'],
        'section_length': len(text), 'section_excerpt': text[:450],
        'old_hdr_brief': claim['attributes']['brief'],
        'changed_original_and_changed_section_rejected': True,
        'ledger_and_source_log_unchanged': True,
        'new_real_calls': [0, 0, 0],
        'metric_result_created': False, 'current_390_credit': False,
        'scope_limit': 'One saved positive source section only; not E01 content confirmation or count.'}
(HERE / 'pfizer-section.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'], 'section_id': section['section_id'],
                  'length': len(text), 'new_real_calls': [0, 0, 0]}))
