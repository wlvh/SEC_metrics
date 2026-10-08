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
    assert set(blocks) == set(range(4630))
    read = [i for p in notes['read_packets'] for i in range(p['blocks'][0], p['blocks'][1]+1)]
    assert read == list(range(4630))
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
        units.append({'reference_unit_id': f'J23-{len(units)+1:02}', 'kind': kind,
                      'statement': statement, 'time_scope': scope,
                      'source_blocks': citations, 'table_cells': locators,
                      'authority': 'EXECUTOR_MANUAL_DEVELOPMENT_REFERENCE'})

    current = 'Proxy April 8, 2024; FY2023 is an annual reporting container, not a December 31 board snapshot.'
    for fact in notes['facts_from_this_range']:
        add(fact['statement'], fact['blocks'], 'Time and speaker distinctions stated explicitly in the statement.',
            'CONSOLIDATED_READ_NOTE')
    roster = [
        ('Stephen B. Burke', 2004, 'Lead Independent Director; CMDC Chair and Governance member', 3, [615,617,619,620,621,622]),
        ('Linda B. Bammann', 2013, 'Risk Chair and CMDC member', 6, [644,647,648,649,650]),
        ('Todd A. Combs', 2016, 'Governance Chair and CMDC member', 9, [680,684,685,686,687]),
        ('Alicia Boler Davis', 2023, 'Risk member', 12, [708,711,712,713]),
        ('James Dimon', 2004, 'Chairman and Chief Executive Officer; no principal committee is named in his summary cell', 15, [747,748,750,759]),
        ('Alex Gorsky', 2022, 'Risk member; Audit/PRC membership remains conditional on election', 18, [423,774,777,778,779,1237]),
        ('Mellody Hobson', 2018, 'Public Responsibility Chair and Risk member', 21, [816,819,820,821,822]),
        ('Phebe N. Novakovic', 2020, 'Audit and Public Responsibility member', 24, [843,846,847,848,849]),
        ('Virginia M. Rometty', 2020, 'Governance and CMDC member', 27, [882,885,886,887,888]),
        ('Mark A. Weinberger', 2024, 'Audit member; Audit chair remains conditional on election', 30, [423,914,917,918,919,1239,1240]),
    ]
    for name, since, role, row, indexes in roster:
        add(f'{name} is a current nominee and director since {since}; {role}.', indexes,
            current, 'NAMED_NOMINEE_COMPOSITION',
            [('table_000035', row, 3), ('table_000035', row, 15)])
    add('Timothy P. Flynn remains a current director since2012 and Audit Chair. His retirement takes effect at the term expiration on the eve of the2024 annual meeting; he is not one of the ten nominees.',
        [533,1218,1219,1236,3648], current, 'CURRENT_NON_NOMINEE_DIRECTOR',
        [('table_000122',7,0),('table_000122',7,3)])
    add('Michael A. Neal remains a current director since2014, an Audit/PRC member; retirement occurs at the term expiration on the eve of the2024 annual meeting. He is not one of the ten nominees.',
        [533,1225,1226,1238,3649], current, 'CURRENT_NON_NOMINEE_DIRECTOR',
        [('table_000122',10,0),('table_000122',10,3),('table_000122',10,12)])
    for name, code, row in [('Stephen B. Burke','A',2),('Linda B. Bammann','B',3),
                            ('Todd A. Combs','A',4),('Mellody Hobson','A',9),
                            ('Michael A. Neal','B',10),('Virginia M. Rometty','A',12)]:
        committee = 'Markets Compliance Committee' if code == 'A' else 'Omnibus Committee'
        add(f'{name} carries code {code}, whose legend names {committee}.',
            [1207,1232,1233,1234],
            'Current membership heading and explicit2023 specific-purpose legend are both retained.',
            'POSITIVE_SPECIFIC_PURPOSE_RELATION', [('table_000122',row,0),('table_000122',row,18)])
    add('Gorsky is already an SEC-defined Audit financial expert in anticipation of future Audit service. This is qualification, not current Audit membership. If elected, he would join Audit/PRC and conclude Risk service.',
        [423,1129,1130,1237], 'Present qualification and conditional future membership.',
        'QUALIFICATION_DISTINCT_FROM_MEMBERSHIP')
    add('Weinberger became a Board and Audit member inJanuary2024. If elected atMay2024 meeting he would become Audit Chair; Flynn is the current Chair inMarch18 report.',
        [998,1239,1240,3646,3648,3651], 'Current appointed membership and proposed post-election chair role.',
        'MEMBERSHIP_DISTINCT_FROM_PROPOSED_CHAIR')
    add('James S. Crown served on the Board from2004 until his death inJune2023; historical service is retained without assigning current2024 membership or an exact death day.',
        [59,60,1441,1454], 'Historical2004–June2023.', 'HISTORICAL_DIRECTOR')
    result = {
        'record_type': 'ISSUE47_EXECUTOR_JPM_FY2023_DEVELOPMENT_REFERENCE',
        'position': 'jpmorgan_chase:2023-12-31',
        'source_filing': document['source_filing'],
        'raw_asset_id': document['raw_asset_id'],
        'document_id': document['text_document_id'],
        'request_sha256': sha((args.input / 'request-body.json').read_bytes()),
        'input_files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                        for p in sorted(args.input.iterdir()) if p.is_file()},
        'all_supplied_text_blocks_read': True,
        'all_4630_block_raw_spans_verified': True,
        'reading_notes': notes,
        'reference_units': units,
        'necessary_tables_read_and_preserved': [tables['table_000035'], tables['table_000122']],
        'unresolved': [
            {'kind':'MEDIA', 'detail':'Necessary committee marks in these two tables are supplied text (Chair/Member/A/B) and have been read. Other image/media content and self-reported skill matrix graphics are not interpreted.'},
            {'kind':'POLICY', 'detail':'Issuer skills, demographics and nomination assessments remain outside named-standard qualification acceptance pending #28 owner interpretation.'},
            {'kind':'TIME', 'detail':'Do not silently choose current or year-2023 semantics for the specific-purpose table/legend; both source qualifications remain available.'},
            {'kind':'METHOD', 'detail':'No independent input-only answer has been executed for this exact request; this is executor reference development and cannot serve as a new blind holdout.'}
        ],
        'complete_all_media_acceptance_proven': False,
        'source_count_frame_unresolved': {'blocks':[966,3378], 'detail':'Current eleven named nonmanagement directors versus nine nonemployee Directors in a proposedPlan eligibility description. The proposal may anticipate the ten-nominee post-retirement set, but this is an inference; neither source number is overwritten.'},
        'native_run_created': False, 'new_acceptances': 0, 'calls': [0,0,0]
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1)+'\n')
    print(json.dumps({'units':len(units), 'block_spans':len(blocks), 'tables_preserved':2,
                      'media_interpreted':False, 'calls':[0,0,0]}))


if __name__ == '__main__':
    main()
