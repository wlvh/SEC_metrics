"""Bind the executor's manually read statements to supplied original bytes.

This helper checks locators and hashes. It does not judge statement meaning,
discover facts, interpret images, or create an accepted metric or Run.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--reading-notes', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    document = json.loads((args.input / 'document.json').read_text())
    grid = json.loads((args.input / 'table-grid.json').read_text())
    metadata = json.loads((args.input / 'metadata.json').read_text())
    notes = json.loads(args.reading_notes.read_text())
    raw = args.raw.read_bytes()
    assert sha(raw) == document['raw_asset_id'][7:]
    blocks = {b['block_index']: b for b in document['blocks']}
    for block in blocks.values():
        assert sha(raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256']
    assert set(blocks) == set(range(3993))
    read = [i for p in notes['read_packets'] for i in range(p['blocks'][0], p['blocks'][1]+1)]
    assert read == list(range(3993))
    for name, digest in metadata['artifacts'].items():
        assert sha((args.input / name).read_bytes()) == digest
    tables = {t['table_id']: t for t in grid['tables']}
    units = []

    def add(statement, indexes, scope, kind, cells=()):
        citations = [{key: blocks[i][key] for key in ('block_index', 'text',
                     'raw_start_byte', 'raw_end_byte', 'raw_span_sha256')} for i in indexes]
        locators = []
        for table_id, row, column in cells:
            table = tables[table_id]
            cell = table['rows'][row]['cells'][column]
            assert cell['row_index'] == row and cell['column_index'] == column
            locators.append({'table_id': table_id, **cell})
        units.append({'reference_unit_id': f'J24-{len(units)+1:02}', 'kind': kind,
                      'statement': statement, 'time_scope': scope,
                      'source_blocks': citations, 'table_cells': locators,
                      'authority': 'EXECUTOR_MANUAL_DEVELOPMENT_REFERENCE'})

    current = 'Proxy April 7, 2025; FY2024 is an annual reporting container, not a December 31 board snapshot.'
    for fact in notes['facts_from_this_range']:
        add(fact['statement'], fact['blocks'], 'Time and speaker distinctions stated explicitly in the statement.',
            'CONSOLIDATED_READ_NOTE')
    roster = [
        ('Stephen B. Burke', 2004, 'Lead Independent Director; CMDC Chair and Governance member', 3, [610,612,614,615,616,617]),
        ('Linda B. Bammann', 2013, 'Risk Chair and CMDC member', 4, [638,641,642,643,644]),
        ('Michele G. Buck', 2025, 'Audit member', 5, [676,679,680,681]),
        ('Todd A. Combs', 2016, 'Governance Chair and CMDC member', 6, [702,703,706,707,708,709]),
        ('Alicia Boler Davis', 2023, 'Risk member', 7, [742,745,746,747]),
        ('James Dimon', 2004, 'Chairman and Chief Executive Officer; no principal committee is named in his summary cell', 8, [756,771,772,774]),
        ('Alex Gorsky', 2022, 'Audit and Public Responsibility member', 9, [810,813,814,815,816]),
        ('Mellody Hobson', 2018, 'Public Responsibility Chair and Risk member', 10, [837,840,841,842,843]),
        ('Phebe N. Novakovic', 2020, 'Audit and Public Responsibility member', 11, [875,878,879,880,881]),
        ('Virginia M. Rometty', 2020, 'Governance and CMDC member', 12, [907,910,911,912,913]),
        ('Brad D. Smith', 2025, 'Risk member', 13, [945,948,949,950]),
        ('Mark A. Weinberger', 2024, 'Audit Chair', 14, [981,984,985,986]),
    ]
    for name, since, role, row, indexes in roster:
        add(f'{name} is a current nominee and director since {since}; {role}.', indexes,
            current, 'NAMED_DIRECTOR_COMPOSITION',
            [('table_000022', row, 3), ('table_000022', row, 15)])
    for name, code, row in [('Stephen B. Burke','A',2),('Linda B. Bammann','B',3),
                            ('Todd A. Combs','A',5),('Mellody Hobson','A',8),('Virginia M. Rometty','A',11)]:
        committee = 'Markets Compliance Committee' if code == 'A' else 'Omnibus Committee'
        add(f'{name} carries code {code}, whose legend names {committee}.',
            [1239,1268,1269,1270],
            'The heading says current board committee membership; the legend explicitly says specific purpose committees in 2024. Both qualifications are retained.',
            'POSITIVE_SPECIFIC_PURPOSE_RELATION', [('table_000117',row,0),('table_000117',row,18)])
    add('Brad D. Smith was elected in October 2024, with service effective January 21, 2025. Michele G. Buck was elected in December 2024, with service effective March 17, 2025. Election decision, effective service and current proxy status are distinct times.',
        [1040,1272], '2024 election decisions; 2025 service effective dates and proxy current roster.',
        'EXPLICIT_DECISION_AND_EFFECTIVE_DATES')
    add('Timothy P. Flynn and Michael A. Neal retired from the Board in May 2024 on the eve of the annual meeting when their terms expired. Their stated independence and past service do not assign current 2025 membership.',
        [1003,1491,1492], 'Historical 2024 service and retirement, distinct from 2025 current nominees.',
        'HISTORICAL_RETIREMENT')
    result = {
        'record_type': 'ISSUE47_EXECUTOR_JPM_FY2024_DEVELOPMENT_REFERENCE',
        'position': 'jpmorgan_chase:2024-12-31',
        'source_filing': document['source_filing'],
        'raw_asset_id': document['raw_asset_id'],
        'document_id': document['text_document_id'],
        'request_sha256': sha((args.input / 'request-body.json').read_bytes()),
        'input_files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                        for p in sorted(args.input.iterdir()) if p.is_file()},
        'all_supplied_text_blocks_read': True,
        'all_3993_block_raw_spans_verified': True,
        'reading_notes': notes,
        'reference_units': units,
        'necessary_tables_read_and_preserved': [tables['table_000022'], tables['table_000117']],
        'unresolved': [
            {'kind':'MEDIA', 'detail':'Blank-looking member cells contain unexamined image marks. Textual roster supports named principal committees; blank cells are not interpreted as absence.'},
            {'kind':'POLICY', 'detail':'Issuer skills, demographics and nomination assessments remain outside named-standard qualification acceptance pending #28 owner interpretation.'},
            {'kind':'TIME', 'detail':'Do not silently choose current or year-2024 semantics for the specific-purpose table/legend; both source qualifications remain available.'},
            {'kind':'METHOD', 'detail':'No independent input-only answer has been executed for this exact request; this is executor reference development and cannot serve as a new blind holdout.'}
        ],
        'complete_all_media_acceptance_proven': False,
        'native_run_created': False, 'new_acceptances': 0, 'calls': [0,0,0]
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1)+'\n')
    print(json.dumps({'units':len(units), 'block_spans':len(blocks), 'tables_preserved':2,
                      'media_interpreted':False, 'calls':[0,0,0]}))


if __name__ == '__main__':
    main()
