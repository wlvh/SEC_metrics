"""Reproduce a currency-only native fact offered as physical B13 context."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
CALL = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0192')
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import canonical_json_bytes
from vnext.capacity_semantic_review import validate_response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expect', choices=('accepted', 'rejected'), required=True)
    args = parser.parse_args()
    request_bytes = (CALL / 'semantic-request.json').read_bytes()
    source_bytes = (CALL / 'source.json').read_bytes()
    request, source = json.loads(request_bytes), json.loads(source_bytes)
    assert request['source_reference_contract']['version'] == 'B13_REQUIRED_FIRST_RELEVANCE_V4'
    assert request['company_id'] == source['company_id'] == 'enphase_energy'
    native, = [row for unit in source['units'] if unit['kind'] == 'NATIVE_FACTS'
               for row in unit['payload']['facts'] if row['fact']['ordinal'] == 450]
    assert native['fact']['tag'] == 'ix:nonfraction'
    assert native['fact']['unit_ref'] == 'usd'
    books = request['response_protocol']['classification_codebooks']
    answer = {'units': [{'unit_index': i, 'reviewed': True, 'unresolved': [],
                        'calculation_limits': []} for i in range(len(request['units']))],
              'findings': [['physical_capacity_context',
                  books['subject'].index('TARGET_REGISTRANT'),
                  books['timing'].index('CURRENT_REPORT'), ['F450'],
                  'The currency-denominated tax credit is manufacturing capacity context.']]}
    try:
        checked = validate_response(request=request,
            raw_response=canonical_json_bytes(value=answer), source=source)
        verdict = 'accepted'
        detail = {'unresolved': checked['unresolved'],
                  'kind': checked['findings'][0]['kind']}
    except ValueError as error:
        verdict = 'rejected'
        detail = {'error': str(error)}
    assert verdict == args.expect, (verdict, detail)
    print(json.dumps({'request_sha256': hashlib.sha256(request_bytes).hexdigest(),
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'native_fact_ordinal': 450, 'native_fact_unit_ref': native['fact']['unit_ref'],
        'verdict': verdict, 'detail': detail}, sort_keys=True))


if __name__ == '__main__':
    main()
