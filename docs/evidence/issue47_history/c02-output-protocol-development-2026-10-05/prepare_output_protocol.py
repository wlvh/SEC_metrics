"""Prepare one new C02 output protocol without reading an answer or reference.

This is an offline development proposal. All supplied source text, tables,
request settings and the task outside its output representation stay identical.
No normal request builder or response consumer imports this helper.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


KINDS = (
    'board_size', 'board_membership', 'board_independence', 'board_leadership',
    'committee_structure', 'committee_membership', 'committee_independence',
    'member_qualification', 'membership_change',
)
OLD_START = 'Return exactly one JSON object:\n'
OLD_END = '\n\nMaximum 64 facts, complete JSON within 4096 output tokens.'
NEW_OUTPUT = '''Return exactly one JSON object with these four keys:
{"kinds":["board_size"],"times":["CURRENT_IN_FILING"],"facts":[[0,"...",[0],0]],"unresolved":[{"source_blocks":[0],"reason":"..."}]}

This changes only the output spelling; the extraction task above is unchanged.
kinds is a unique list of the kind strings actually used, each drawn from:
board_size, board_membership, board_independence, board_leadership,
committee_structure, committee_membership, committee_independence,
member_qualification, membership_change.
times is a unique list of the actual stated-time strings used; preserve dates,
years, proposed/current/former status and uncertainty. Do not substitute the
annual container or filing date for a fact's stated time.
Each facts row is [kind_index, statement, source_blocks, time_index]. The first
and last entries are zero-based integer indices into kinds and times. statement
is the same concise, complete fact statement requested above. source_blocks is
a nonempty list of original B indices supporting its identity, role and time.
Rows decode exactly to {kind:kinds[kind_index], statement:statement,
source_blocks:source_blocks, stated_time:times[time_index]}.
unresolved retains the original objects with source_blocks and reason; it is
not a facts row. Do not abbreviate away a statement, source, date, role,
condition or unresolved relation to save tokens. Empty facts is [] (with empty
dictionaries if unused). Return complete valid JSON, not JSON inside a string.
The displayed ellipsis is a shape illustration, not a source fact.'''


def strict_load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY:' + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('NON_JSON_CONSTANT:' + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def wire(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(original_raw):
    original = strict_load(original_raw)
    assert len(original['messages']) == 2
    assert [m['role'] for m in original['messages']] == ['system', 'user']
    system = original['messages'][0]['content']
    assert system.count(OLD_START) == system.count(OLD_END) == 1
    start = system.index(OLD_START)
    end = system.index(OLD_END, start)
    expected = '{"facts":[{"kind":"' + '|'.join(KINDS) + (
        '","statement":"...","source_blocks":[0],"stated_time":"..."}],'
        '"unresolved":[{"source_blocks":[0],"reason":"..."}]}')
    assert system[start + len(OLD_START):end] == expected
    result = strict_load(original_raw)
    result['messages'][0]['content'] = system[:start] + NEW_OUTPUT + system[end:]
    assert result['messages'][1] == original['messages'][1]
    assert {k: v for k, v in result.items() if k != 'messages'} == {
        k: v for k, v in original.items() if k != 'messages'}
    assert result['max_tokens'] == 4096
    proof = {
        'original_request_sha256': sha(original_raw),
        'new_request_sha256': sha(wire(result)),
        'whole_user_content_sha256': sha(original['messages'][1]['content'].encode()),
        'unchanged_task_prefix_sha256': sha(system[:start].encode()),
        'unchanged_limit_and_source_decoder_suffix_sha256': sha(system[end:].encode()),
        'replaced_output_text_sha256': sha(system[start:end].encode()),
        'new_output_text_sha256': sha(NEW_OUTPUT.encode()),
        'every_user_content_byte_unchanged': True,
        'all_non_message_request_fields_unchanged': True,
        'task_prefix_and_source_decoder_suffix_unchanged': True,
    }
    return wire(result), proof


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--original-request', type=Path, required=True)
    parser.add_argument('--original-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root / 'scripts'))
    from vnext.continuous_request_context import measure_request
    raw = args.original_request.read_bytes()
    assert sha(raw) == args.original_sha256
    body, proof = build(raw)
    original_measurement = measure_request(raw, require_reference=True)
    measurement = measure_request(body, require_reference=True)
    assert measurement['fits']
    source = strict_load(strict_load(raw)['messages'][1]['content'])
    proof.update({
        'record_type': 'ISSUE47_C02_NEW_GENERATION_OUTPUT_PROTOCOL_PROPOSAL',
        'block_count': source['block_count'],
        'tables': len(source['tables']),
        'string_count': len(source['strings']),
        'original_input_tokens': original_measurement['input_tokens'],
        'new_input_tokens': measurement['input_tokens'],
        'output_reserve_tokens': 4096,
        'maximum_context_tokens': 200000,
        'output_codec': 'tools/c02_development_response_codec.py::expand',
        'answer_or_executor_reference_read_by_builder': False,
        'fresh_generation_tested': False,
        'production_request_or_decoder_wired': False,
        'old_response_or_request_changed': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    })
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'request-body.json').write_bytes(body)
    (args.out / 'prompt.txt').write_text(strict_load(body)['messages'][0]['content'])
    for name, value in [('proposal.json', proof), ('context-measurement.json', measurement)]:
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(proof, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
