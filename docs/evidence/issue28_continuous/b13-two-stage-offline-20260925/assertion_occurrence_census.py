"""Read-only census of exact physical-capacity phrases in saved B13 sources."""
import argparse
import json
from pathlib import Path
import re

from vnext.canonical import sha256_bytes, strict_json_file


PHRASE = re.compile(r'\b(?:manufacturing|production)\s+'
                    r'(?:capacity|capabilities)\b', re.I)


def run(ledger_root):
    results = []
    for ordinal in (190, 171):
        source = strict_json_file(path=ledger_root / 'calls' /
            f'{ordinal:04d}' / 'source.json')
        units = [unit for unit in source['units']
                 if unit['kind'] == 'VISIBLE_TEXT']
        blocks = [block for unit in units for block in unit['payload']['blocks']]
        counts = [len(PHRASE.findall(block['text'])) for block in blocks]
        results.append({'company_id': source['company_id'],
            'saved_ordinal': ordinal,
            'source_id': source['semantic_source_id'],
            'visible_unit_count': len(units),
            'visible_block_count': len(blocks),
            'matched_block_count': sum(count > 0 for count in counts),
            'multi_phrase_block_count': sum(count > 1 for count in counts),
            'max_phrase_count_in_block': max(counts, default=0),
            'multi_phrase_blocks': [
                {'block_index': block['block_index'], 'phrase_count': count,
                 'text_sha256': sha256_bytes(content=block['text'].encode('utf-8'))}
                for block, count in zip(blocks, counts) if count > 1]})
    return {'record_type': 'B13_SAVED_SOURCE_PHYSICAL_PHRASE_CENSUS',
        'regex': PHRASE.pattern,
        'read_only': True, 'new_calls': [0, 0, 0],
        'interpretation_boundary': ('Counts exact phrase occurrences only. '
            'Does not identify assertion spans, subjects, timing, scan selections, '
            'model accuracy, or absence of other capacity meanings.'),
        'companies': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(args.ledger_root)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({row['company_id']: row['multi_phrase_block_count']
        for row in value['companies']}))
