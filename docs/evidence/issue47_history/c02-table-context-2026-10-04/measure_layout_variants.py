"""Three bounded representation experiments, offline and without source cuts.

Numbers retain the old V2 prompt to compare payload size. They are optimistic
lower bounds, not sendable requests: each new layout would need correct new
instructions and independent interpretation. None makes Lumen fit even here.
"""
import argparse
import bisect
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]
from tools.prepare_c02_table_context import expanded_view, wire
from vnext.continuous_request_context import _load_tokenizer, measure_request


def main(inputs, out):
    tokenizer, fallback = _load_tokenizer(); assert tokenizer is not None, fallback
    reports = []
    for p in sorted(inputs.glob('*/request-body.json')):
        request = json.loads(p.read_bytes())
        old = json.loads(request['messages'][1]['content'])
        expected = expanded_view(old)
        strings, ids, mapping = [], {}, []
        for s in old['strings']:
            if s not in ids:
                ids[s] = len(strings); strings.append(s)
            mapping.append(ids[s])
        grouped = {'strings': strings, 'blocks': mapping[:old['block_count']],
                   'geometry': old['geometry'], 'tables': []}
        linear = {**old, 'tables': []}
        for t in old['tables']:
            rows = defaultdict(list); defaults, exceptions = [], []
            for x in t['x']:
                rows[x[0]].append([x[1], mapping[x[2]], *x[3:]])
                at = x[0] * t['s'][1] + x[1]
                (exceptions if len(x) == 4 else defaults).extend([at, *x[2:]])
            grouped['tables'].append({k: t[k] for k in ('i', 's', 'g')}
                                     | {'c': mapping[t['c']], 'r': [[r, cells] for r, cells in rows.items()]})
            linear['tables'].append({k: t[k] for k in ('i', 's', 'c', 'g')}
                                    | {'x': defaults, 'e': exceptions})
        sliced = {**linear, 'strings': list(old['strings'])}
        blocks = old['strings'][:old['block_count']]
        assert not any('\x00' in b for b in blocks)
        joined, starts, at = '\x00'.join(blocks), [], 0
        for b in blocks:
            starts.append(at); at += len(b) + 1
        substitutions = 0
        for i, s in enumerate(old['strings'][old['block_count']:], old['block_count']):
            at = joined.find(s) if s else -1
            if at < 0:
                continue
            b = bisect.bisect_right(starts, at) - 1
            ref = [b, at - starts[b], at - starts[b] + len(s)]
            assert blocks[b][ref[1]:ref[2]] == s
            if len(tokenizer.encode(wire(ref).decode()).ids) < len(tokenizer.encode(wire(s).decode()).ids):
                sliced['strings'][i] = ref; substitutions += 1
        measurements = []
        for name, v in [('deduplicated_strings_and_grouped_rows', grouped),
                        ('linear_positions_and_flat_cell_arrays', linear),
                        ('linear_positions_and_exact_block_substrings', sliced)]:
            # Reconstruct the V2 decoder input to compare every text/header cell.
            if v is grouped:
                recovered = {'strings': [strings[i] for i in v['blocks']] + strings,
                             'block_count': len(v['blocks']), 'geometry': v['geometry'], 'tables': []}
                offset = len(v['blocks'])
                for t in v['tables']:
                    recovered['tables'].append({k: t[k] for k in ('i', 's', 'g')}
                                               | {'c': t['c'] + offset,
                                                  'x': [[r, x[0], x[1] + offset, *x[2:]] for r, cells in t['r'] for x in cells]})
            else:
                ss = [s if isinstance(s, str) else blocks[s[0]][s[1]:s[2]] for s in v['strings']]
                recovered = {**v, 'strings': ss, 'tables': []}
                for t in v['tables']:
                    cells = []
                    for key, width in [('x', 2), ('e', 3)]:
                        a = t[key]
                        for n in range(0, len(a), width):
                            row, col = divmod(a[n], t['s'][1]); cells.append([row, col, *a[n+1:n+width]])
                    recovered['tables'].append({k: t[k] for k in ('i', 's', 'c', 'g')} | {'x': cells})
            assert expanded_view(recovered) == expected
            measured_request = {**request, 'messages': [request['messages'][0],
                {'role': 'user', 'content': wire(v).decode()}]}
            m = measure_request(wire(measured_request), require_reference=True)
            measurements.append({'variant': name, 'payload_sha256': hashlib.sha256(wire(v)).hexdigest(),
                                 'all_blocks_and_expanded_text_header_grids_equal': True,
                                 'input_token_lower_bound': m['input_tokens'],
                                 'fits_with_old_prompt_lower_bound': m['fits'],
                                 'valid_new_layout_prompt_or_independent_read': False})
        reports.append({'position': p.parent.name, 'original_request_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                        'block_count': old['block_count'], 'table_count': len(old['tables']),
                        'literal_substrings_reused': substitutions, 'variants': measurements})
    report = {'record_type': 'ISSUE_47_C02_BOUNDED_COMPLETE_LAYOUT_SIZE_EXPERIMENTS',
              'experiments_per_source': 3, 'sources': reports,
              'limits_unchanged': {'context': 200000, 'output_reserve': 4096},
              'next_constraint': 'Lumen remains outside even optimistic single-request bounds. Complete responsibility/context grouping needs a separately justified contract; source cuts or cap increases are not used.',
              'current_prepare_tool_changed': False, 'provider_requests_sent': 0, 'calls': [0, 0, 0]}
    out.write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps([{'position': r['position'], 'lower_bounds': [m['input_token_lower_bound'] for m in r['variants']]} for r in reports]))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--inputs', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); main(a.inputs, a.out)
