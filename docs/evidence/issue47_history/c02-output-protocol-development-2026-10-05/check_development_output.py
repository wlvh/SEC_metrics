"""Check a development output's shape, source-index range and literal token size.

This cannot establish source support, completeness, model generation, temporal
correctness, an Evidence verdict or acceptance. It never truncates an answer.
"""
import argparse
import json
import sys
from pathlib import Path

from prepare_output_protocol import KINDS, NEW_OUTPUT, strict_load, sha


def decode(body_raw, response_raw, expand):
    body = strict_load(body_raw)
    assert NEW_OUTPUT in body['messages'][0]['content'], 'PROTOCOL_NOT_THIS_PROPOSAL'
    block_count = strict_load(body['messages'][1]['content'])['block_count']
    value = strict_load(response_raw)
    result = expand(value)
    assert set(value['kinds']) <= set(KINDS), 'UNKNOWN_KIND'
    assert all(time.strip() for time in value['times']), 'EMPTY_TIME'

    def blocks_ok(blocks):
        return (type(blocks) is list and bool(blocks)
                and all(type(b) is int and 0 <= b < block_count for b in blocks))

    for fact in result['facts']:
        assert fact['statement'].strip(), 'EMPTY_STATEMENT'
        assert blocks_ok(fact['source_blocks']), 'SOURCE_BLOCK_OUTSIDE_SUPPLIED_TEXT'
    for item in result['unresolved']:
        assert type(item) is dict and set(item) == {'source_blocks', 'reason'}, 'UNRESOLVED_FIELDS'
        assert blocks_ok(item['source_blocks']), 'UNRESOLVED_SOURCE_OUTSIDE_SUPPLIED_TEXT'
        assert type(item['reason']) is str and item['reason'].strip(), 'EMPTY_UNRESOLVED_REASON'
    # Return the original strings and object order; whitespace is not repaired.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--response', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    sys.path.insert(0, str(args.code_root / 'scripts'))
    from tools.c02_development_response_codec import expand
    from vnext.continuous_request_context import _load_tokenizer
    body_raw, response_raw = args.request.read_bytes(), args.response.read_bytes()
    result = decode(body_raw, response_raw, expand)
    tokenizer, fallback = _load_tokenizer()
    assert tokenizer is not None, fallback
    tokens = len(tokenizer.encode(response_raw.decode(), add_special_tokens=False).ids)
    assert tokens <= 4096, 'LITERAL_OUTPUT_EXCEEDS_4096'
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'expanded-development-answer.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    receipt = {
        'record_type': 'ISSUE47_C02_DEVELOPMENT_OUTPUT_SYNTAX_AND_SIZE_ONLY',
        'request_sha256': sha(body_raw), 'response_sha256': sha(response_raw),
        'literal_output_tokens': tokens, 'output_limit': 4096,
        'facts': len(result['facts']), 'unresolved': len(result['unresolved']),
        'source_support_or_completeness_checked': False,
        'generation_or_acceptance_credit': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    }
    (args.out / 'syntax-and-size.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(receipt, indent=1))


if __name__ == '__main__':
    main()
