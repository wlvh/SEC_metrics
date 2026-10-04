"""Bind supplied manual judgments to a complete, actually read Item 8 question.

This development helper does not classify text, read model answers, register a
review, or create a Run. The notes supply the executor's IN/OUT judgments. The
quote window only represents those judgments under the unchanged source quote
contract. The reading index is a byte proof; the executor notes attest reading.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--reading', type=Path, required=True)
    p.add_argument('--notes', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--quote-characters', type=int, choices=[32, 24], required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.code_root / 'scripts'))
    from vnext.historical_legal_review import validate_answer
    from vnext.continuous_request_context import _load_tokenizer

    request = json.loads((a.input / 'request.json').read_bytes())
    metadata = json.loads((a.input / 'metadata.json').read_bytes())
    index = json.loads((a.reading / 'index.json').read_bytes())
    notes = json.loads(a.notes.read_bytes())
    scope = metadata['item8_range']
    bounds = [scope['start_block'], scope['end_block_exclusive']]
    assert notes['complete'] is True and notes['read_range'] == bounds
    assert notes['read_parts'] == list(range(len(index['parts'])))
    assert notes['raw_asset_id'] == metadata['raw_asset_id'] == index['source_raw_id']
    assert notes['current_v4_selection_or_independent_answer_read_before_reference'] is False
    assert notes['old_paid_answers_read_or_modified'] is False
    assert digest((a.input / 'request-body.json').read_bytes()) == metadata['request_sha256']
    combined = ''
    start = bounds[0]
    for part in index['parts']:
        raw = (a.reading / part['path']).read_bytes()
        assert digest(raw) == part['sha256'] and part['start_block'] == start
        combined += raw.decode('utf-8')
        start = part['end_block_exclusive']
    assert start == bounds[1]
    expected = ''.join(f"B{b['block_id'][1:]} | {b['text']}\n" for b in request['blocks'])
    assert combined == expected
    positive = notes['positive_blocks']
    assert positive == sorted(set(positive)) and set(positive) <= set(range(*bounds))
    texts = {b['block_id']: b['text'] for b in request['blocks']}
    anchors = notes['manual_quote_anchors']
    terms = re.compile(r'(?i)\b(?:patent|lawsuit|litigation|legal|claims?|suits?|complaint|proceed\w*|settle\w*|subpoena|CID|investigat\w*|defen\w*|plaintif\w*|contingen\w*|liability|insurance|indemnif\w*|accru\w*)\b')

    def quote(identity):
        text = texts[identity]
        # Named anchors express the executor's chosen basis, not a classifier.
        anchor = anchors.get(identity[1:])
        width = max(a.quote_characters, len(anchor or ''))
        if len(text) <= width:
            return text
        if anchor:
            offset = text.index(anchor)
        else:
            match = terms.search(text)
            offset = max(0, match.start() - 5) if match else 0
        offset = min(offset, max(0, len(text) - 20))
        value = text[offset:offset + width]
        trimmed = value.rsplit(' ', 1)[0]
        if len(trimmed) >= 20 and (not anchor or anchor in trimmed):
            value = trimmed
        assert min(20, len(text.strip())) <= len(value) <= 300 and value in text
        return value

    positive_ids = {'b' + str(i) for i in positive}
    must = set(request['must_decide'])
    answer = {
        'decisions': [{'block_id': identity,
                       'decision': 'IN_SCOPE' if identity in positive_ids else 'OUT_OF_SCOPE',
                       'quote': quote(identity) if identity in positive_ids else None}
                      for identity in request['must_decide']],
        'also_in_scope': [{'block_id': 'b' + str(i), 'quote': quote('b' + str(i))}
                         for i in positive if 'b' + str(i) not in must],
    }
    validate_answer(request=request, raw_output=json.dumps(answer, ensure_ascii=False))
    literal = json.dumps(answer, ensure_ascii=False, separators=(',', ':')) + '\n'
    tokenizer, reason = _load_tokenizer()
    assert tokenizer is not None, reason
    tokens = len(tokenizer.encode(literal, add_special_tokens=False).ids)
    reference = {
        'record_type': 'ISSUE47_FULL_ITEM8_EXECUTOR_REFERENCE',
        'position': notes['position'], 'raw_asset_id': metadata['raw_asset_id'],
        'request_sha256': metadata['request_sha256'],
        'reading_notes_sha256': digest(a.notes.read_bytes()),
        'all_item8_blocks_read': len(request['blocks']),
        'positive_blocks': positive, 'contract_answer': answer,
        'original_response_contract_check': 'PASS',
        'compact_reference_tokens': tokens, 'output_limit': 4096,
        'reference_fits_output_limit': tokens <= 4096,
        'quote_window_characters': a.quote_characters,
        'manual_quote_anchors': anchors,
        'method': 'MANUAL_IN_OUT_THEN_NEW_SOURCE_QUOTE_REPRESENTATION',
        'source_media_complete': False, 'independent_generation_tested': False,
        'normal_runtime_pool_same': False, 'runtime_wired': False,
        'old_paid_answers_read_or_modified': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    }
    a.out.mkdir(parents=True, exist_ok=False)
    raw = (json.dumps(reference, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    (a.out / 'executor-reference.json').write_bytes(raw)
    (a.out / 'contract-reference-compact.json').write_text(literal)
    freeze = {'reference_sha256': digest(raw), 'frozen_at': datetime.now(timezone.utc).isoformat(),
              'source_complete_before_reference': True,
              'independent_answer_or_current_v4_selector_read_before_freeze': False,
              'calls': [0, 0, 0]}
    (a.out / 'reference-frozen.json').write_text(json.dumps(freeze, indent=1) + '\n')
    print(json.dumps({'blocks': len(request['blocks']), 'positive': len(positive),
                      'must_decide': len(must), 'also_in_scope': len(answer['also_in_scope']),
                      'output_tokens': tokens, 'fits': tokens <= 4096,
                      'reference_sha256': digest(raw)}))


if __name__ == '__main__':
    main()
