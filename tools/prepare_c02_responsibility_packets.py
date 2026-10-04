"""Two bounded C02 development responsibilities with exact source union.

Each receives every source text and the global table index. Complete table
layouts and output responsibility are assigned once in source order. This
proves input coverage/size only, not cross-packet semantic reconciliation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from tools.prepare_c02_table_context import assert_matches, wire
from vnext.continuous_request_context import measure_request


def packets(view, dictionary_mode='full', table_split=None):
    """Keep every text; distribute complete original tables, never their cells."""
    table_middle = (len(view['tables']) + 1) // 2 if table_split is None else table_split
    if type(table_middle) is not int or not 0 <= table_middle <= len(view['tables']):
        raise ValueError('C02_RESPONSIBILITY_TABLE_SPLIT_INVALID')
    block_middle = (view['block_count'] + 1) // 2
    table_index = [{k: v for k, v in t.items() if k != 'x'} for t in view['tables']]
    result = []
    for ordinal, (lo, hi, tables) in enumerate([
            (0, block_middle, view['tables'][:table_middle]),
            (block_middle, view['block_count'], view['tables'][table_middle:])], 1):
        part = {'representation': 'C02_TWO_RESPONSIBILITY_DEVELOPMENT_V1',
            'packet_ordinal': ordinal, 'packet_count': 2, 'strings': view['strings'],
            'block_count': view['block_count'], 'geometry': view['geometry'],
            'all_table_descriptors': table_index, 'owned_tables': tables,
            'owned_text_block_range': [lo, hi],
            'full_source_view_sha256': hashlib.sha256(wire(view)).hexdigest(),
            'all_source_text_present': True, 'all_table_layouts_present_in_this_packet': False}
        if dictionary_mode == 'owned':
            required = {t['c'] for t in table_index}
            required.update(x[2] for t in tables for x in t['x'])
            part['strings'] = view['strings'][:view['block_count']]
            part['cell_strings'] = [[i, view['strings'][i]] for i in sorted(required)
                                    if i >= view['block_count']]
            part['all_source_text_present'] = False
            part['all_primary_block_text_present'] = True
            part['representation'] = 'C02_TWO_RESPONSIBILITY_DEVELOPMENT_V2'
        elif dictionary_mode != 'full':
            raise ValueError('C02_RESPONSIBILITY_DICTIONARY_MODE_INVALID')
        result.append(part)
    assert_union(view, result)
    return result


def assert_union(view, parts):
    """Check the entire original text/grid and exactly-once responsibilities."""
    if len(parts) != 2 or [p['packet_ordinal'] for p in parts] != [1, 2]:
        raise ValueError('C02_RESPONSIBILITY_PACKET_SET_CHANGED')
    identity = hashlib.sha256(wire(view)).hexdigest()
    index = [{k: v for k, v in t.items() if k != 'x'} for t in view['tables']]
    for p in parts:
        owned = 'cell_strings' in p
        expected_strings = view['strings'][:view['block_count']] if owned else view['strings']
        if (p['full_source_view_sha256'] != identity or p['strings'] != expected_strings
                or p['geometry'] != view['geometry'] or p['block_count'] != view['block_count']
                or p['all_table_descriptors'] != index):
            raise ValueError('C02_RESPONSIBILITY_COMMON_SOURCE_CHANGED')
        if owned:
            required = {t['c'] for t in index}
            required.update(x[2] for t in p['owned_tables'] for x in t['x'])
            expected = [[i, view['strings'][i]] for i in sorted(required) if i >= view['block_count']]
            if p['cell_strings'] != expected:
                raise ValueError('C02_RESPONSIBILITY_CELL_DICTIONARY_CHANGED')
    if [t for p in parts for t in p['owned_tables']] != view['tables']:
        raise ValueError('C02_RESPONSIBILITY_TABLE_UNION_CHANGED')
    bounds = [p['owned_text_block_range'] for p in parts]
    if (not all(type(n) is int for b in bounds for n in b)
            or bounds[0][0] != 0 or bounds[0][1] != bounds[1][0]
            or bounds[1][1] != view['block_count']
            or not 0 <= bounds[0][1] <= view['block_count']):
        raise ValueError('C02_RESPONSIBILITY_BLOCK_UNION_CHANGED')
    if all('cell_strings' in p for p in parts):
        union = {i: text for p in parts for i, text in p['cell_strings']}
        if union != {i: text for i, text in enumerate(view['strings']) if i >= view['block_count']}:
            raise ValueError('C02_RESPONSIBILITY_DICTIONARY_UNION_CHANGED')


FORMAT = """
Responsibility decoder: strings and geometry retain the full original dictionary.
strings[0:block_count] are exactly B0..B<block_count-1>, all supplied here.
The complete global table descriptors identify every original i,s,c,g. Only
owned_tables carries x cells and complete layout; an unowned table's missing
layout is NOT a blank table. Decode owned x=[row,column,string_index,(geometry)]
and spans as usual; other coordinates in an owned table are blank/unheaded.
Original table IDs remain global, without renumbering. Extra dictionary strings
are table/caption text, never B blocks. This is a partial layout responsibility,
not a complete independent C02 answer or an annual-end composition snapshot.
Report source-supported facts within owned_text_block_range [start,end) or from
owned_tables. Other source text may support their identity/time/context. Preserve
cross-packet dependencies as unresolved with exact B/table IDs; do not guess from
a flattened row or an unowned layout. Do not infer image contents. No packet can
establish the global absence/completeness result. A later separate reconciliation
must combine the entire evidence union, identify duplicates, settle dependencies
and check omissions before any complete metric credit. That stage is not tested
or wired by this preparation. Keep the original facts/unresolved output contract.
"""

OWNED_FORMAT = FORMAT.replace(
    'strings and geometry retain the full original dictionary.',
    'geometry retains the full original span dictionary. strings holds every original B text; '
    'cell_strings=[original_dictionary_index,text] holds each assigned extra cell/caption string. '
    'Look up a string below block_count in strings, and any larger index in cell_strings. '
    'Indices are global and never renumbered; the complete extra-string union is checked.')


def prepare(inputs, out, dictionary_mode='full', balance=False):
    if out.exists():
        raise FileExistsError('Preserve previous packets')
    original = json.loads((inputs / 'request-body.json').read_bytes())
    view = json.loads(original['messages'][1]['content'])
    document = json.loads((inputs / 'document.json').read_bytes())
    grid = json.loads((inputs / 'table-grid.json').read_bytes())
    assert_matches(view, document, grid)
    old_prompt = original['messages'][0]['content']
    boundary = '\nSource representation (zero-based indices):'
    if boundary not in old_prompt:
        raise ValueError('C02_RESPONSIBILITY_ORIGINAL_FORMAT_REQUIRED')
    task = old_prompt.split(boundary)[0].replace('all HTML tables',
        'all primary text and table descriptors, with complete layouts only for assigned tables')
    def measured(part):
        request = {**original, 'messages': [
            {'role': 'system', 'content': task + (OWNED_FORMAT if dictionary_mode == 'owned' else FORMAT)},
            {'role': 'user', 'content': wire(part).decode()}]}
        body = wire(request)
        return body, measure_request(body, require_reference=True)

    trials = []
    parts = packets(view, dictionary_mode)
    if balance:
        # At most ten offline comparisons of whole-table ownership boundaries;
        # no compression, dropped source, provider call or raised context limit.
        low, high = 0, len(view['tables'])
        best = None
        for _ in range(10):
            if low > high:
                break
            split = (low + high) // 2
            candidate = packets(view, dictionary_mode, split)
            counts = [measured(p)[1]['input_tokens'] for p in candidate]
            trials.append({'table_split': split, 'input_tokens': counts})
            if best is None or max(counts) < best[0]:
                best = (max(counts), candidate)
            if counts[0] < counts[1]: low = split + 1
            else: high = split - 1
        parts = best[1]
    out.mkdir(parents=True)
    rows = []
    for part in parts:
        body, measurement = measured(part)
        destination = out / ('packet-' + str(part['packet_ordinal']))
        destination.mkdir()
        (destination / 'request-body.json').write_bytes(body)
        (destination / 'source-view.json').write_bytes(wire(part))
        (destination / 'context-measurement.json').write_bytes(wire(measurement))
        rows.append({'ordinal': part['packet_ordinal'], 'request_sha256': measurement['request_sha256'],
            'input_tokens': measurement['input_tokens'], 'fits': measurement['fits'],
            'owned_text_block_range': part['owned_text_block_range'],
            'owned_table_ids': [t['i'] for t in part['owned_tables']]})
    receipt = {'record_type': 'ISSUE47_C02_TWO_RESPONSIBILITY_RESOURCE_PROBE',
        'original_request_sha256': hashlib.sha256((inputs / 'request-body.json').read_bytes()).hexdigest(),
        'original_full_request_measurement': measure_request(wire(original), require_reference=True),
        'full_source_view_sha256': hashlib.sha256(wire(view)).hexdigest(),
        'full_text_and_table_union_verified': True, 'renumbered_or_filtered_source': False,
        'packets': rows, 'total_reference_input_tokens': sum(r['input_tokens'] for r in rows),
        'all_packets_fit': all(r['fits'] for r in rows), 'fixed_attempt_count': 2,
        'dictionary_mode': dictionary_mode,
        'whole_table_balance_trials': trials,
        'semantic_reconciliation_tested': False, 'output_cap_generation_tested': False,
        'model_answer_tested': False, 'runtime_wired': False,
        'new_runs': 0, 'new_acceptances': 0, 'calls': [0, 0, 0]}
    (out / 'manifest.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ['all_packets_fit', 'total_reference_input_tokens', 'calls']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dictionary-mode', choices=['full', 'owned'], default='full')
    parser.add_argument('--balance', action='store_true')
    args = parser.parse_args()
    prepare(args.inputs, args.out, args.dictionary_mode, args.balance)
