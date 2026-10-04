"""A bounded source-responsibility proposal distributing text and whole tables.

Unlike the earlier proposal, every packet does not repeat all primary text.
This only proves byte-level union and request size. Cross-packet interpretation,
reconciliation, source completeness and generation remain unvalidated/unwired.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'scripts'))
from tools.prepare_c02_table_context import assert_matches, wire
from vnext.continuous_request_context import measure_request


def packets(view):
    block_split = (view['block_count'] + 1) // 2
    table_split = (len(view['tables']) + 1) // 2
    index = [{k: v for k, v in t.items() if k != 'x'} for t in view['tables']]
    result = []
    for ordinal, (lo, hi, tables) in enumerate([
            (0, block_split, view['tables'][:table_split]),
            (block_split, view['block_count'], view['tables'][table_split:])], 1):
        required = set(range(lo, hi)) | {t['c'] for t in index}
        required.update(x[2] for t in tables for x in t['x'])
        result.append({
            'representation': 'C02_DISTRIBUTED_TEXT_AND_WHOLE_TABLE_RESPONSIBILITY_V1',
            'packet_ordinal': ordinal, 'packet_count': 2,
            'dictionary': [[i, view['strings'][i]] for i in sorted(required)],
            'block_count': view['block_count'], 'geometry': view['geometry'],
            'all_table_descriptors': index, 'owned_tables': tables,
            'owned_text_block_range': [lo, hi],
            'full_source_view_sha256': hashlib.sha256(wire(view)).hexdigest(),
            'full_primary_text_present_in_this_packet': False,
            'all_table_layouts_present_in_this_packet': False,
            'absence_or_complete_metric_claim_allowed': False})
    assert_union(view, result)
    return result


def assert_union(view, parts):
    if len(parts) != 2 or [p['packet_ordinal'] for p in parts] != [1, 2]:
        raise ValueError('DISTRIBUTED_PACKET_SET_CHANGED')
    index = [{k: v for k, v in t.items() if k != 'x'} for t in view['tables']]
    full_sha = hashlib.sha256(wire(view)).hexdigest()
    dictionaries = {}
    for p in parts:
        lo, hi = p['owned_text_block_range']
        if not (type(lo) is int and type(hi) is int and 0 <= lo <= hi <= view['block_count']):
            raise ValueError('DISTRIBUTED_BLOCK_RANGE_INVALID')
        required = set(range(lo, hi)) | {t['c'] for t in index}
        required.update(x[2] for t in p['owned_tables'] for x in t['x'])
        expected = [[i, view['strings'][i]] for i in sorted(required)]
        if p['dictionary'] != expected:
            raise ValueError('DISTRIBUTED_DICTIONARY_CHANGED')
        if (p['all_table_descriptors'] != index or p['geometry'] != view['geometry']
                or p['block_count'] != view['block_count']
                or p['full_source_view_sha256'] != full_sha
                or p['absence_or_complete_metric_claim_allowed'] is not False):
            raise ValueError('DISTRIBUTED_COMMON_AUTHORITY_CHANGED')
        for i, text in p['dictionary']:
            if i in dictionaries and dictionaries[i] != text:
                raise ValueError('DISTRIBUTED_SHARED_STRING_CONFLICT')
            dictionaries[i] = text
    bounds = [p['owned_text_block_range'] for p in parts]
    if not (bounds[0][0] == 0 and bounds[0][1] == bounds[1][0]
            and bounds[1][1] == view['block_count']):
        raise ValueError('DISTRIBUTED_BLOCK_UNION_CHANGED')
    if [t for p in parts for t in p['owned_tables']] != view['tables']:
        raise ValueError('DISTRIBUTED_TABLE_UNION_CHANGED')
    if dictionaries != dict(enumerate(view['strings'])):
        raise ValueError('DISTRIBUTED_COMPLETE_STRING_UNION_CHANGED')


FORMAT = """
Distributed responsibility decoder (all indices remain original and zero-based):
dictionary entries are [original_string_index,text]. Indices below block_count
are original B blocks; larger indices are extra table/caption strings, never B
blocks. owned_text_block_range=[start,end) assigns text responsibilities exactly
once across two packets. Every owned B block is present; additional B text needed
by an owned table is also present, with its original ID. An absent B string is
unknown here, never empty. All table descriptors retain original i,s,c,g in source
order. owned_tables holds complete x layouts for assigned whole tables, never
pieces of a table. x=[row,column,string_index,(geometry_override)] and geometry
entries [rowspan,colspan,header] decode exactly as specified; blank coordinates
in an owned table are blank/unheaded. Every referenced string is in dictionary.
An unowned table's absent x layout is unknown here, never a blank table. Original
table IDs, block IDs and dictionary IDs are not renumbered or interchangeable.
This packet does not contain the entire source. Read every assigned B text and
whole table, including later passages. Extract facts for owned_text_block_range
or owned_tables; additional supplied text can support identity/time/context.
Do not invent a document-wide current date or absent member from this partial
context. Retain any dependency that cannot be settled here as unresolved with
exact B/table IDs and the missing relation. Source images are not interpreted.
No packet can establish global absence, whole-metric completeness or acceptance.
A later separate reconciliation must use both complete answer/evidence unions,
settle cross-packet dependencies, distinguish dates and entities, deduplicate
without merging different facts, and check omissions against the pre-read
executor source reference. That reconciliation is not implemented or validated
by this preparation. Preserve the original facts/unresolved output contract and
the 4096 output reserve; report output-limit uncertainty rather than dropping
facts. The shared annual container and filing identity are not a year-end Board
snapshot. Do not infer image contents or independent verification of credentials.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Preserve previous proposals'
    original = json.loads((args.inputs / 'request-body.json').read_bytes())
    view = json.loads(original['messages'][1]['content'])
    document = json.loads((args.inputs / 'document.json').read_bytes())
    grid = json.loads((args.inputs / 'table-grid.json').read_bytes())
    assert_matches(view, document, grid)
    parts = packets(view)
    boundary = '\nSource representation (zero-based indices):'
    task, _ = original['messages'][0]['content'].split(boundary, 1)
    task = task.replace('You receive all visible blocks and all HTML tables of ',
                        'You receive assigned original text and whole-table responsibilities from ')
    task = task.replace('Scan the complete supplied source, including later reports and tables.',
                        'Scan all source supplied for this responsibility, including later reports and tables.')
    args.out.mkdir(parents=True)
    rows = []
    for part in parts:
        body = wire({**original, 'messages': [
            {'role': 'system', 'content': task + FORMAT},
            {'role': 'user', 'content': wire(part).decode()}]})
        measurement = measure_request(body, require_reference=True)
        destination = args.out / ('packet-' + str(part['packet_ordinal']))
        destination.mkdir()
        (destination / 'request-body.json').write_bytes(body)
        (destination / 'source-view.json').write_bytes(wire(part))
        (destination / 'context-measurement.json').write_bytes(wire(measurement))
        rows.append({'ordinal': part['packet_ordinal'],
                     'request_sha256': measurement['request_sha256'],
                     'input_tokens': measurement['input_tokens'], 'fits': measurement['fits'],
                     'owned_text_block_range': part['owned_text_block_range'],
                     'owned_table_ids': [t['i'] for t in part['owned_tables']]})
    # Changes are process-local copies of this actual source proposal.
    injections = []
    for name, change in [
        ('drop_owned_text_dictionary_entry', lambda p: p[0]['dictionary'].pop(1)),
        ('change_original_text', lambda p: p[0]['dictionary'][0].__setitem__(1, 'changed')),
        ('drop_complete_table', lambda p: p[1]['owned_tables'].pop()),
        ('gap_in_text_responsibility', lambda p: p[1]['owned_text_block_range'].__setitem__(0,
                                                 p[1]['owned_text_block_range'][0] + 1)),
        ('permit_global_absence', lambda p: p[0].__setitem__('absence_or_complete_metric_claim_allowed', True)),
    ]:
        altered = copy.deepcopy(parts)
        change(altered)
        try:
            assert_union(view, altered)
        except (ValueError, IndexError) as error:
            injections.append({'name': name, 'caught': True, 'reason': str(error)})
        else:
            raise AssertionError('Source union fault was not caught: ' + name)
    receipt = {
        'record_type': 'ISSUE47_DISTRIBUTED_C02_CONTEXT_RESOURCE_PROPOSAL',
        'original_request_sha256': hashlib.sha256((args.inputs / 'request-body.json').read_bytes()).hexdigest(),
        'complete_original_blocks': view['block_count'], 'complete_original_tables': len(view['tables']),
        'full_text_and_table_union_verified': True,
        'original_primary_text_expanded_table_text_headers_and_ids_changed': False,
        'nonempty_table_span_geometry_changed': False,
        'raw_cell_html_and_blank_span_geometry_in_provider_rendition': False,
        'original_request_changed': False,
        'fixed_source_order_boundaries_tested': 1, 'whole_table_balance_trials': [],
        'packets': rows, 'all_packets_fit': all(r['fits'] for r in rows),
        'total_reference_input_tokens': sum(r['input_tokens'] for r in rows),
        'memory_source_union_injections': injections,
        'executor_complete_source_reference_available': False,
        'semantic_reconciliation_tested': False, 'output_cap_generation_tested': False,
        'independent_exact_input_method_answer': False, 'runtime_wired': False,
        'new_runs': 0, 'new_acceptances': 0, 'calls': [0, 0, 0],
    }
    (args.out / 'manifest.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({'input_tokens': [r['input_tokens'] for r in rows],
                      'all_packets_fit': receipt['all_packets_fit'],
                      'source_union_faults_caught': len(injections), 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
