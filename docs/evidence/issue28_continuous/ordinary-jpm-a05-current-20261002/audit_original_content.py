"""Compare A05's three selected values with two authenticated annual originals."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.deterministic_router import parse_accession_xbrl_source

first = json.loads((HERE/'result.json').read_text())
attempt = (Path('/private/tmp/issue28-jpm-a05-current-20261002/state') /
           'jpmorgan_chase/metrics/A05/attempts' / first['attempt_id'])
data = attempt/'data'
rows = [json.loads(line) for line in
        (attempt/'runs/A05/records.jsonl').read_bytes().splitlines()]
references = [row for row in rows if row['record_type'] == 'SOURCE_REFERENCE'
              and row['source_role'] == 'target_primary']
assert len(references) == 2
blobs = {row['raw_asset_id']: row for row in rows
         if row['record_type'] == 'RAW_BLOB'}
selected = [row for row in rows
            if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM']
assert len(selected) == 3
result = next(row for row in rows if row['record_type'] == 'METRIC_RESULT'
              and row['metric_id'] == 'A05')
assert result['result_id'] == first['result_id']
route = json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())['metrics']['A05']
assert route['branches'][0]['branch_id'] == 'average_assets'
assert route['branches'][0]['formula_id'] == 'average_denominator_ratio'


def number(fact):
    value = Decimal(fact['text'].replace(',', '')) * (Decimal(10) ** int(fact['scale']))
    return -value if fact['sign'] == '-' else value


sources = {}
for ref in references:
    blob = blobs[ref['raw_asset_id']]
    raw = (data/blob['storage_uri']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ref['raw_asset_id'][7:]
    assert len(raw) == blob['byte_length']
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    observations = {}
    for fact in parsed.facts:
        if fact['qualified_name'] not in ('us-gaap:Assets',
                                          'us-gaap:NetIncomeLoss'):
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['entity_identifier'] != '0000019617'
                or context['dimensions'] or context['typed_dimension_count']
                or fact['unit_ref'].lower() != 'usd'):
            continue
        key = (fact['qualified_name'], context['period_start'],
               context['period_end'])
        observations.setdefault(key, []).append({'value': str(number(fact)),
            'context_ref': fact['context_ref'], 'ordinal': fact['ordinal'],
            'source_text': fact['text'], 'scale': fact['scale']})
    sources[ref['accession']] = {'raw_asset_id': ref['raw_asset_id'],
        'source_reference_id': ref['source_reference_id'],
        'parse_id': parsed.parsed_source_id,
        'observations': observations}

expected = {
    '0001628280-26-008131': {
        ('us-gaap:NetIncomeLoss', '2025-01-01', '2025-12-31'):
            '57048000000',
        ('us-gaap:Assets', '2025-12-31', '2025-12-31'):
            '4424900000000',
        ('us-gaap:Assets', '2024-12-31', '2024-12-31'):
            '4002814000000'},
    '0000019617-25-000270': {
        ('us-gaap:Assets', '2024-12-31', '2024-12-31'):
            '4002814000000'}}
assert set(sources) == set(expected)
proofs = []
for accession, entries in expected.items():
    for key, value in entries.items():
        actual = sources[accession]['observations'][key]
        assert {row['value'] for row in actual} == {value}
        proofs.append({'accession': accession, 'qualified_name': key[0],
                       'period_start': key[1], 'period_end': key[2],
                       'value_usd': value, 'original_occurrences': len(actual),
                       'contexts': sorted({row['context_ref'] for row in actual}),
                       'original_lexical_values': sorted({row['source_text']
                                                          for row in actual})})
selected_values = {(row['attributes']['accession'], row['locator']['concept'],
                    row['locator']['period_start'], row['locator']['period_end']):
                   str(row['value']) for row in selected}
for row in proofs:
    if row['accession'] == '0001628280-26-008131' and row['period_end'] == '2024-12-31':
        continue
    key = (row['accession'], row['qualified_name'].split(':')[1],
           row['period_start'], row['period_end'])
    assert Decimal(selected_values[key]) == Decimal(row['value_usd'])
value = Decimal('57048000000') / ((Decimal('4424900000000') +
                                    Decimal('4002814000000')) / 2)
assert value == Decimal(result['value'])
body = {'record_type': 'ISSUE28_JPMORGAN_2025_A05_ORIGINAL_CONTENT_CHECK',
        'source_ref_and_raw_sha256_verified': True,
        'current_and_prior_annual_originals': [
            {'accession': accession,
             'source_reference_id': source['source_reference_id'],
             'raw_asset_id': source['raw_asset_id'],
             'native_parse_id': source['parse_id']}
            for accession, source in sorted(sources.items())],
        'facts': proofs,
        'approved_formula_id': 'average_denominator_ratio',
        'computed_ratio': str(value),
        'private_result_id': result['result_id'],
        'content_scope': 'Three selected A05 values, same-concept FY2024 comparator, entity/period/unit/no-dimensions. Not all statement facts or full 390 acceptance.',
        'new_real_calls': [0, 0, 0],
        'production_authorized': False}
(HERE/'original-content.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'original_facts_checked': len(proofs),
                  'computed_ratio': str(value),
                  'matches_private_result': True,
                  'new_real_calls': [0, 0, 0]}))
