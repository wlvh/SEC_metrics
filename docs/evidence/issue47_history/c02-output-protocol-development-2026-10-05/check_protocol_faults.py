"""Synthetic protocol negatives; these are not original-source answer trials."""
import argparse
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch

from prepare_output_protocol import NEW_OUTPUT, build, wire, strict_load
from check_development_output import decode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--original-request', type=Path, required=True)
    parser.add_argument('--proposal-request', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    sys.path.insert(0, str(args.code_root / 'scripts'))
    from tools.c02_development_response_codec import expand
    from vnext.continuous_request_context import _load_tokenizer
    original_raw = args.original_request.read_bytes()
    proposal_raw = args.proposal_request.read_bytes()
    # Exact rebuilding of the actual question; no old answer or reference input.
    with patch('socket.socket', side_effect=AssertionError('NO_NETWORK')):
        rebuilt, _ = build(original_raw)
        assert rebuilt == proposal_raw
        # Synthetic source indices and people are independent of the issuer.
        body = {'messages': [{'role': 'system', 'content': NEW_OUTPUT},
                {'role': 'user', 'content': json.dumps({'block_count': 3})}]}
        answer = {'kinds': ['board_membership'], 'times': ['CURRENT_IN_FILING'],
                  'facts': [[0, '  A synthetic person is a director.\n', [0, 2], 0]],
                  'unresolved': [{'source_blocks': [1], 'reason': 'Unstated departure date.'}]}
        expanded = decode(wire(body), wire(answer), expand)
        assert expanded['facts'][0]['statement'] == '  A synthetic person is a director.\n'
        assert expanded['facts'][0]['source_blocks'] == [0, 2]
        assert expanded['unresolved'] == answer['unresolved']
        negatives = []
        for case in ('kind_index', 'time_index', 'boolean_index', 'duplicate_dictionary',
                     'source_dictionary_index', 'boolean_source', 'unknown_kind',
                     'empty_time', 'empty_statement', 'extra_fact_field', 'more_than_64',
                     'missing_unresolved_reason', 'extra_unresolved_field',
                     'empty_unresolved_reason', 'unresolved_source_outside_text'):
            value = copy.deepcopy(answer)
            if case == 'kind_index': value['facts'][0][0] = 1
            elif case == 'time_index': value['facts'][0][3] = -1
            elif case == 'boolean_index': value['facts'][0][0] = True
            elif case == 'duplicate_dictionary': value['kinds'].append(value['kinds'][0])
            elif case == 'source_dictionary_index': value['facts'][0][2] = [3]
            elif case == 'boolean_source': value['facts'][0][2] = [True]
            elif case == 'unknown_kind': value['kinds'][0] = 'unapproved_fact_kind'
            elif case == 'empty_time': value['times'][0] = ' \n'
            elif case == 'empty_statement': value['facts'][0][1] = ' \n'
            elif case == 'extra_fact_field': value['facts'][0].append('not permitted')
            elif case == 'more_than_64': value['facts'] *= 65
            elif case == 'missing_unresolved_reason': value['unresolved'][0].pop('reason')
            elif case == 'extra_unresolved_field': value['unresolved'][0]['new'] = 1
            elif case == 'empty_unresolved_reason': value['unresolved'][0]['reason'] = ''
            else: value['unresolved'][0]['source_blocks'] = [-1]
            try:
                decode(wire(body), wire(value), expand)
            except (AssertionError, ValueError):
                negatives.append(case)
            else:
                raise AssertionError('INVALID_OUTPUT_ACCEPTED:' + case)
        for label, raw in [('duplicate_json_key', b'{"facts":[],"facts":[]}'),
                           ('non_json_number', b'{"x":NaN}'),
                           ('incomplete_json', b'{"kinds":[')]:
            try:
                strict_load(raw)
            except (ValueError, json.JSONDecodeError):
                negatives.append(label)
            else:
                raise AssertionError('INVALID_JSON_ACCEPTED:' + label)
        tokenizer, fallback = _load_tokenizer()
        assert tokenizer is not None, fallback
        oversized = copy.deepcopy(answer)
        oversized['facts'][0][1] = ' '.join(str(n) for n in range(8000))
        oversized_raw = wire(oversized)
        # It is valid syntax, so size must be checked separately before saving.
        decode(wire(body), oversized_raw, expand)
        oversized_tokens = len(tokenizer.encode(oversized_raw.decode(), add_special_tokens=False).ids)
        assert oversized_tokens > 4096
    print(json.dumps({
        'actual_question_rebuild_byte_equal': True,
        'synthetic_whitespace_sources_and_uncertainty_preserved': True,
        'rejected_shape_or_json_faults': negatives,
        'oversized_syntactically_valid_output_tokens': oversized_tokens,
        'oversized_output_fails_separate_limit': True,
        'original_source_answer_or_generation_tested': False,
        'network_socket_forbidden': True, 'calls': [0, 0, 0],
    }, indent=1))


if __name__ == '__main__':
    main()
