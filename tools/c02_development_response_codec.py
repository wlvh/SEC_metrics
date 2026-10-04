"""A reversible C02 development output shape; never repair or accept an answer.

Remove repeated field names and repeated kind/time strings, retaining every
statement, citation and unresolved item. No production reader uses this codec.
"""
import argparse
import json
from pathlib import Path


def compact(answer):
    if set(answer) != {'facts', 'unresolved'}:
        raise ValueError('C02_RESPONSE_FIELDS_INVALID')
    kinds, times, rows = [], [], []
    for fact in answer['facts']:
        if set(fact) != {'kind', 'statement', 'source_blocks', 'stated_time'}:
            raise ValueError('C02_FACT_FIELDS_INVALID')
        for values, field in [(kinds, 'kind'), (times, 'stated_time')]:
            if fact[field] not in values:
                values.append(fact[field])
        rows.append([kinds.index(fact['kind']), fact['statement'],
                     fact['source_blocks'], times.index(fact['stated_time'])])
    result = {'kinds': kinds, 'times': times, 'facts': rows,
              'unresolved': answer['unresolved']}
    if expand(result) != answer:
        raise ValueError('C02_RESPONSE_ROUNDTRIP_DIFFERS')
    return result


def expand(value):
    if set(value) != {'kinds', 'times', 'facts', 'unresolved'}:
        raise ValueError('C02_RESPONSE_FIELDS_INVALID')
    for name in ['kinds', 'times']:
        values = value[name]
        if (type(values) is not list or not all(type(v) is str for v in values)
                or len(set(values)) != len(values)):
            raise ValueError('C02_RESPONSE_DICTIONARY_INVALID')
    if type(value['facts']) is not list or len(value['facts']) > 64:
        raise ValueError('C02_RESPONSE_FACT_LIMIT')
    facts = []
    for row in value['facts']:
        if type(row) is not list or len(row) != 4:
            raise ValueError('C02_RESPONSE_FACT_ROW_INVALID')
        kind, statement, blocks, time = row
        if (type(kind) is not int or not 0 <= kind < len(value['kinds'])
                or type(time) is not int or not 0 <= time < len(value['times'])
                or type(statement) is not str or type(blocks) is not list
                or not blocks or not all(type(n) is int and n >= 0 for n in blocks)):
            raise ValueError('C02_RESPONSE_FACT_REFERENCE_INVALID')
        facts.append({'kind': value['kinds'][kind], 'statement': statement,
                      'source_blocks': blocks, 'stated_time': value['times'][time]})
    if type(value['unresolved']) is not list:
        raise ValueError('C02_RESPONSE_UNRESOLVED_INVALID')
    return {'facts': facts, 'unresolved': value['unresolved']}


def main(answer_path, out):
    if out.exists():
        raise FileExistsError('Preserve original outputs')
    answer = json.loads(answer_path.read_bytes())
    value = compact(answer)
    out.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--answer', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.answer, args.out)
