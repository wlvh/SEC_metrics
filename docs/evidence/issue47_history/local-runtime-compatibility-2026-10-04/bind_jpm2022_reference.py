"""Bind manually read FY2022 statements to original supplied bytes.

This helper verifies locators, not business meaning or acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('input', 'raw', 'reading-notes', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    document = json.loads((args.input / 'document.json').read_text())
    grid = json.loads((args.input / 'table-grid.json').read_text())
    metadata = json.loads((args.input / 'metadata.json').read_text())
    notes = json.loads(args.reading_notes.read_text())
    raw = args.raw.read_bytes()
    assert sha(raw) == document['raw_asset_id'][7:]
    blocks = {b['block_index']: b for b in document['blocks']}
    assert set(blocks) == set(range(4413))
    for b in blocks.values():
        assert sha(raw[b['raw_start_byte']:b['raw_end_byte']]) == b['raw_span_sha256']
    assert [i for p in notes['read_packets'] for i in range(p['blocks'][0], p['blocks'][1]+1)] == list(range(4413))
    assert notes['complete_supplied_visible_text_read'] is True
    for name, digest in metadata['artifacts'].items():
        assert sha((args.input / name).read_bytes()) == digest
    tables = {t['table_id']: t for t in grid['tables']}
    # The displayed every-third-cell reading represents these replicated spans.
    # Check that no omitted replica carries a different raw text.
    for name in ('table_000042', 'table_000133'):
        for row in tables[name]['rows']:
            for column in range(0, len(row['cells']), 3):
                assert len({c['raw_text'] for c in row['cells'][column:column+3]}) == 1
    units = []

    def add(statement, indexes, scope, kind, cells=()):
        citations = [{key: blocks[i][key] for key in ('block_index', 'text', 'raw_start_byte', 'raw_end_byte', 'raw_span_sha256')} for i in indexes]
        locators = []
        for table_id, row, column in cells:
            cell = tables[table_id]['rows'][row]['cells'][column]
            assert (cell['row_index'], cell['column_index']) == (row, column)
            locators.append({'table_id': table_id, **cell})
        units.append({'reference_unit_id': f'J22-{len(units)+1:02}', 'kind': kind,
                      'statement': statement, 'time_scope': scope,
                      'source_blocks': citations, 'table_cells': locators,
                      'authority': 'EXECUTOR_MANUAL_DEVELOPMENT_REFERENCE'})

    current = 'Proxy April 4, 2023; FY2022 is an annual reporting container, not a December 31 board snapshot.'
    for fact in notes['facts_from_this_range']:
        add(fact['statement'], fact['blocks'], 'Time and speaker distinctions stated in the statement.', 'CONSOLIDATED_READ_NOTE')
    roster = [
        ('Stephen B. Burke', 2004, 'Lead Independent Director since2021; CMDC Chair and Governance member', 3, [666,668,669,670,671,674]),
        ('Linda B. Bammann', 2013, 'Risk Chair and CMDC member', 6, [691,693,694,695]),
        ('Todd A. Combs', 2016, 'Governance Chair and CMDC member', 9, [723,725,726,727]),
        ('James S. Crown', 2004, 'Public Responsibility Chair and Risk member', 12, [746,748,749,750]),
        ('Alicia Boler Davis', 2023, 'Committees explicitly Not yet assigned', 15, [779,780,781,1052]),
        ('James Dimon', 2004, 'Chair since2006 and Chief Executive Officer since2005; no principal committee named in his summary cell', 18, [804,805,806,810]),
        ('Timothy P. Flynn', 2012, 'Audit Chair', 21, [835,837,838]),
        ('Alex Gorsky', 2022, 'Risk member', 24, [860,862,863,1052]),
        ('Mellody Hobson', 2018, 'Public Responsibility and Risk member; not PRC Chair at this date', 27, [900,902,903,904]),
        ('Michael A. Neal', 2014, 'Audit and Public Responsibility member', 30, [924,926,927,928]),
        ('Phebe N. Novakovic', 2020, 'Audit member', 33, [951,953,954]),
        ('Virginia M. Rometty', 2020, 'Governance and CMDC member', 36, [977,979,980,981]),
    ]
    for name, since, role, row, indexes in roster:
        add(f'{name} is a current nominee and director since{since}; {role}.', indexes,
            current, 'NAMED_NOMINEE_COMPOSITION',
            [('table_000042',row,3), ('table_000042',row,15)])
    for name, code, row in [('Stephen B. Burke','A',2),('Linda B. Bammann','B',3),('Todd A. Combs','A',4),
                            ('James S. Crown','B',5),('Mellody Hobson','A',10),('Michael A. Neal','B',11),('Virginia M. Rometty','A',13)]:
        committee = 'Markets Compliance Committee' if code == 'A' else 'Omnibus Committee'
        add(f'{name} carries code{code}, whose legend names {committee}.', [1262,1279,1280,1281],
            'Current membership heading and explicit2022 specific-purpose legend both retained.',
            'POSITIVE_SPECIFIC_PURPOSE_RELATION', [('table_000133',row,0),('table_000133',row,18)])
    add('Gorsky Board appointment is effectiveJuly2022; Davis is effectiveMarch2023 and has no assigned committees at proxy date. Neither is assigned an inferred common appointment year from the letter.',
        [60,779,780,781,1052,1283], 'Actual appointment months versus current proxy date.', 'APPOINTMENT_TIME_AND_ASSIGNMENT')
    add('Audit2022 members Flynn/Neal/Novakovic meet SEC and NYSE financial-expert definitions. Bammann as Risk Chair meets Federal Reserve risk-experience rule. March21,2023 signed Audit report separately confirms independence, financial literacy and SEC expertise for the three members.',
        [1185,3504,3532,3536,3537,3538,3539,3540], 'Explicit2022 qualification and current signed report.', 'NAMED_STANDARD_QUALIFICATION')
    result = {'record_type':'ISSUE47_EXECUTOR_JPM_FY2022_DEVELOPMENT_REFERENCE',
              'position':'jpmorgan_chase:2022-12-31', 'source_filing':document['source_filing'],
              'raw_asset_id':document['raw_asset_id'], 'document_id':document['text_document_id'],
              'request_sha256':sha((args.input/'request-body.json').read_bytes()),
              'input_files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(args.input.iterdir()) if p.is_file()},
              'all_supplied_text_blocks_read':True, 'all_4413_block_raw_spans_verified':True,
              'reading_notes':notes, 'reference_units':units,
              'necessary_tables_read_and_preserved':[tables['table_000042'],tables['table_000133']],
              'unresolved':[
                  {'kind':'MEDIA','detail':'These two member tables use supplied text; all their unique nonempty cells and blank assignments were read and replicated spans checked. Other image/media and self-reported skills graphics remain uninterpreted.'},
                  {'kind':'POLICY','detail':'Issuer skills, demographics and nomination assessment are not accepted named-standard qualifications pending #28 interpretation.'},
                  {'kind':'TIME','detail':'Both current-member heading and explicit2022 A/B legend retained; annual container is not a year-end snapshot.'},
                  {'kind':'METHOD','detail':'No independent input-only answer for this exact request; executor reference cannot be a new blind holdout.'}],
              'complete_all_media_acceptance_proven':False, 'native_run_created':False,
              'new_acceptances':0, 'calls':[0,0,0]}
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'units':len(units),'block_spans':len(blocks),'tables_preserved':2,'calls':[0,0,0]}))


if __name__ == '__main__':
    main()
