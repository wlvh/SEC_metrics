"""Reproduce the 8.01 body/keyword disconnect in the existing test fixture."""
import hashlib
import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from tests.vnext.test_deterministic_router import fixture_sources
from vnext.deterministic_router import (adapt_8k_item_index,
    load_event_route_catalog, matched_event_key_set)

with tempfile.TemporaryDirectory(prefix='issue28-e01-801-') as directory:
    fixture = fixture_sources(root=Path(directory))
    primary = fixture['bytes']['primary']
    assert b'Item 8.01 The company announced an acquisition transaction' in primary
    claims = adapt_8k_item_index(
        filing_documents=[{
            'hdr_bytes': fixture['bytes']['hdr'],
            'hdr_source_reference': fixture['references']['hdr'],
            'primary_document_bytes': primary,
            'primary_source_reference': fixture['references']['primary'],
        }],
        source_set_manifest=fixture['manifests']['fy_8k_item_inventory'],
        inventory_source_reference=fixture['references']['inventory'],
        inventory_bytes=fixture['bytes']['inventory'])
    catalog = load_event_route_catalog(repo_root=ROOT)
    matched = matched_event_key_set(metric_id='E01', claims=claims,
                                    catalog=catalog)
    all_codes = [claim['attributes']['item_code'] for claim in claims]
    selected_codes = [row['item_code'] for row in matched]
    brief_8_01, = [claim['attributes']['brief'] for claim in claims
                   if claim['attributes']['item_code'] == '8.01']
    assert '8.01' in all_codes
    assert '8.01' not in selected_codes
    assert brief_8_01 == '8-K item 8.01 parsed from hdr.sgml'
    result = {'record_type': 'ISSUE28_E01_801_BODY_KEYWORD_DISCONNECT',
        'fixture_origin': 'tests/vnext/test_deterministic_router.py:fixture_sources',
        'primary_sha256': hashlib.sha256(primary).hexdigest(),
        'primary_contains_acquisition_transaction': True,
        'adapted_item_codes': all_codes,
        'item_8_01_saved_brief': brief_8_01,
        'matched_E01_item_codes': selected_codes,
        'body_alias_missed_with_hdr_items': True,
        'new_real_calls': [0, 0, 0],
        'business_definition_decided': False}
    (HERE/'eight01.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'all': all_codes, 'matched': selected_codes,
        'body_alias_missed': True}, sort_keys=True))
