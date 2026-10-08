"""Two bounded source-only proposals retaining every parsed current instant.

This replaces no original artifact and never reads a reference or response.
It retains the whole primary text/table representation and all original native
candidate objects. The new population contains nonnumeric and non-money facts;
monetary-converter diagnostics do not classify those sources as invalid debt.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


FIELDS = ['ordinal', 'concept_qname', 'source_text', 'context_ref', 'context',
          'declared_unit', 'numeric_attributes', 'normalized_source_value',
          'format_qname', 'nil_attributes', 'normalization_issue', 'semantic_role_assigned']


def encode(records):
    values, indices, sources = [], {}, {}
    for kind in ['primary', 'xml']:
        rows = []
        for record in records[kind]:
            assert list(record) == FIELDS
            row = []
            for field in FIELDS:
                value = record[field]
                key = canonical(value)
                if key not in indices:
                    indices[key] = len(values)
                    values.append(value)
                row.append(indices[key])
            rows.append(row)
        sources[kind] = rows
    return {'fields': FIELDS, 'values': values, 'sources': sources}


def decode(encoded):
    assert encoded['fields'] == FIELDS
    records = {}
    for kind in ['primary', 'xml']:
        rows = []
        for row in encoded['sources'][kind]:
            assert len(row) == len(FIELDS)
            assert all(type(i) is int and 0 <= i < len(encoded['values']) for i in row)
            rows.append({field: copy.deepcopy(encoded['values'][i]) for field, i in zip(FIELDS, row)})
        records[kind] = rows
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--original-request', type=Path, required=True)
    p.add_argument('--all-current', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.code_root / 'scripts'))
    from vnext.continuous_request_context import measure_request
    original_bytes = a.original_request.read_bytes()
    original = json.loads(original_bytes)
    user = json.loads(original['messages'][1]['content'])
    old_native = user['current_potential_financing_native_facts']
    census = json.loads(a.all_current.read_bytes())
    records, old_ordinals = {}, {}
    for kind in ['primary', 'xml']:
        records[kind] = []
        for row in census[kind]:
            assert row['source_kind'] == kind
            assert row['context']['period_fields'] == [
                {'kind': 'instant', 'value': user['target_period']['period_end']}]
            assert row['context']['identifiers'] == [
                {'value': str(user['entity']).zfill(10), 'scheme': 'http://www.sec.gov/CIK'}]
            records[kind].append({
                field: row['context']['context_ref'] if field == 'context_ref'
                else False if field == 'semantic_role_assigned'
                else row[field] for field in FIELDS})
        assert len(records[kind]) == 336
        lookup = {r['ordinal']: r for r in records[kind]}
        assert len(lookup) == len(records[kind])
        assert all(lookup[r['ordinal']] == r for r in old_native[kind])
        old_ordinals[kind] = [r['ordinal'] for r in old_native[kind]]
        assert len(old_ordinals[kind]) == 153
    encoded = encode(records)
    assert decode(encoded) == records
    common = copy.deepcopy(user)
    del common['current_potential_financing_native_facts']
    common['record_type'] = 'B06_FULL_PRIMARY_AND_ALL_PARSED_CURRENT_INSTANT_DEVELOPMENT'
    common['original_native_candidate_ordinals'] = old_ordinals
    common['native_census_scope'] = {
        'report_end': user['target_period']['period_end'],
        'all_parsed_current_instant_per_source': 336,
        'current_USD_monetary_per_source': 258,
        'original_candidate_per_source': 153,
        'all_raw_native_universe_claimed': False,
        'debt_completeness_proven': False,
    }
    diagnostic = (
        '\nNative population: all 336 current instant facts recognized by the existing parser '
        'per source are supplied, not only the original 153 potential financing candidates. '
        'The 153 original candidates are preserved; their ordinal lists record membership, '
        'not a debt judgment. The 336 include 258 USD monetary facts, other units and '
        'nonnumeric facts. normalized_source_value and normalization_issue are observations '
        'of the existing monetary converter: a null/error on a duration, enumeration URI '
        'or other nonnumeric value is not a conclusion that the filing or that nonnumeric '
        'source is invalid. Read its source_text, context and declared_unit. Do not turn '
        'shares, rates, asset lives, pointers or an empty enumeration into a monetary '
        'liability or confirmed zero. This parsed population does not claim all raw native '
        'facts, full media interpretation or financing completeness. Original source '
        'ordinals are retained for output native_facts.\n')
    a.out.mkdir(parents=True, exist_ok=False)
    measurements = {}
    for name, native, decoder in [
        ('literal', records, ''),
        ('shared-values', encoded,
         '\nNative representation: fields lists the original field names in order. '
         'values holds complete JSON field values, including full context/unit/attribute '
         'objects and literal source strings; null and false retain their JSON types. '
         'sources.primary and sources.xml are source-order rows of indices into values. '
         'For each row, original_record[fields[j]]=values[row[j]] for every j. '
         'A values index is not a fact ordinal. For output, use the decoded ordinal and '
         'the source kind. Reused field values do not merge distinct facts or assert '
         'economic identity. No fields are omitted.\n')]:
        candidate_user = {**common, 'parsed_current_instant_native_facts': native}
        assert candidate_user['primary_text_and_table_layout'] == user['primary_text_and_table_layout']
        assert candidate_user['sources'] == user['sources']
        candidate = copy.deepcopy(original)
        candidate['messages'][0]['content'] += diagnostic + decoder
        candidate['messages'][1]['content'] = canonical(candidate_user)
        assert {k: v for k, v in candidate.items() if k != 'messages'} == {k: v for k, v in original.items() if k != 'messages'}
        body = (canonical(candidate) + '\n').encode('utf-8')
        measurement = measure_request(body, require_reference=True)
        root = a.out / name
        root.mkdir()
        (root / 'request-body.json').write_bytes(body)
        (root / 'context-measurement.json').write_text(json.dumps(measurement, indent=1) + '\n')
        measurements[name] = {'request_sha256': measurement['request_sha256'],
                              'input_tokens': measurement['input_tokens'],
                              'context_tokens': measurement['context_tokens'],
                              'fits': measurement['fits']}
    receipt = {'record_type': 'ISSUE47_TWO_BOUNDED_B06_CURRENT_NATIVE_INPUT_PROPOSALS',
               'original_request_sha256': hashlib.sha256(original_bytes).hexdigest(),
               'all_current_input_sha256': hashlib.sha256(a.all_current.read_bytes()).hexdigest(),
               'original_native_objects_retained': [153, 153],
               'new_parsed_current_instants_retained': [336, 336],
               'same_complete_primary_text_and_all_table_layout': True,
               'same_original_task_definition_and_output_contract': True,
               'full_records_round_trip_exact': True,
               'representation_attempts': measurements,
               'new_model_or_independent_answer': False, 'runtime_wired': False,
               'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0}
    (a.out / 'proposal.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(receipt, indent=1))


if __name__ == '__main__':
    main()
