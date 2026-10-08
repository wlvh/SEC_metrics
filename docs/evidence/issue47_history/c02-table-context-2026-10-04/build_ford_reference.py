"""Pack the executor's already-read Ford reference, not a semantic extractor.

The fixed statements and block associations below are documentary reading
judgments. Only source identities, referenced bytes and matrix coordinates
are computed. This helper is never used by a business selector or calculator.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(source, request, notes, out):
    if out.exists():
        raise FileExistsError('Use a fresh output file; never replace a saved reference')
    document = json.loads((source / 'document.json').read_bytes())
    grid = json.loads((source / 'table-grid.json').read_bytes())
    blocks = document['blocks']
    read_notes = json.loads(notes.read_bytes())
    assert len(blocks) == 4912 and read_notes['blocks_read'] == [[0, 4911]]
    assert read_notes['all_source_text_read'] is True
    assert sha(request) == '146142032aea59dcc713cd07e6dfd1a44aaa0b8083ce8a5bcbc53115440b9f32'
    assert sha(source / 'document.json') == 'ef62e424de1568a123f2215ba131752c76492ab2593ece3a02e2d3b863c62ad9'
    assert sha(source / 'table-grid.json') == '953dfa4037bb5f309125b59f0b22bae9262d3334b65fa0cb811d4003235d4763'
    facts = []

    def fact(kind, statement, indices, time='CURRENT_IN_FILING'):
        assert all(type(n) is int and 0 <= n < len(blocks) for n in indices)
        facts.append({'reference_id': f'F{len(facts)+1:02}', 'kind': kind,
                      'statement': statement, 'source_blocks': indices,
                      'stated_time': time})

    fact('board_size', 'The Board size was reduced from 15 to 14 when Anthony F. Earley, Jr. retired following the May 2022 shareholder meeting.', [404], 'following May 2022 shareholder meeting')
    fact('board_membership', 'All 14 nominees for the May 11, 2023 election are already Board members; if elected, each serves until the next annual meeting or a qualified elected successor.', [1061,1066], 'CURRENT_IN_FILING; proposed election May 11, 2023')
    fact('board_independence', 'Nine named directors are independent: Casiano, Helman, Kennard, May, Mooney, Vojvodich Radakovich, Thornton, Veihmeyer and Weinberg; 64% of nominees are independent.', [363,775,4562])
    fact('board_leadership', 'William Clay Ford, Jr. is Board Chair and Executive Chair; Chair since January 1999 and elected Executive Chair in September 2006. James D. Farley, Jr. is President/CEO, separate from the Board Chair.', [394,1274,1286], 'CURRENT_IN_FILING; Chair since January 1999; Executive Chair since September 2006')
    fact('board_independence', 'William Clay Ford, Jr., Board Chair, is not independent under Ford Corporate Governance Principles.', [394])
    fact('board_leadership', 'John L. Thornton is Lead Independent Director since 2022.', [394,1337,1346], 'since 2022')
    cards = [
        ('Kimberly A. Casiano',1232,1237,1238,'2003',True),
        ('Alexandra Ford English',1233,1242,1243,'2021',False),
        ('James D. Farley, Jr.',1255,1260,1261,'2020',False),
        ('Henry Ford III',1256,1265,1266,'2021',False),
        ('William Clay Ford, Jr.',1274,1279,1280,'1988',False),
        ('William W. Helman IV',1275,1284,1285,'2011',True),
        ('Jon M. Huntsman, Jr.',1293,1298,1299,'2020; also 2012–2017',False),
        ('William E. Kennard',1294,1303,1304,'2015',True),
        ('John C. May',1315,1320,1321,'2021',True),
        ('Beth E. Mooney',1316,1325,1326,'2019',True),
        ('Lynn Vojvodich Radakovich',1336,1341,1342,'2017',True),
        ('John L. Thornton',1337,1348,1349,'1996',True),
        ('John B. Veihmeyer',1358,1363,1364,'2017',True),
        ('John S. Weinberg',1359,1368,1369,'2016',True),
    ]
    for name, identity, tenure, committee, since, independent in cards:
        assert blocks[identity]['text'] == name
        fact('board_membership', f'{name}: '+('Independent Director' if independent else 'Director')+f' since {since}; '+blocks[committee]['text'], [1066,identity,tenure,committee], f'CURRENT_IN_FILING; tenure since {since}')
    committee_rosters = read_notes['manual_reference_observations']['committees']
    for name, c in committee_rosters.items():
        fact('committee_membership', name+' Committee: chair '+c['chair']+'; members '+', '.join(c['members'])+'.', c['blocks'])
    fact('committee_independence', 'Audit, Compensation/Talent/Culture and Nominating/Governance members are all independent under the NYSE/SEC/company standards stated by Ford.', [473,518,563,652,775,1599])
    fact('member_qualification', 'All Audit members meet NYSE financial-literacy requirements.', [473,520])
    fact('member_qualification', 'The Board determines John B. Veihmeyer an Audit Committee financial expert under SEC regulations/applicable NYSE rules; he is also independent and Audit chair.', [522,722])
    fact('member_qualification', 'Casiano, Mooney, Vojvodich Radakovich and Veihmeyer meet heightened SEC Audit independence standards. This eligibility does not assign Vojvodich Radakovich to Audit.', [473,775])
    fact('member_qualification', 'May, Vojvodich Radakovich, Thornton and Weinberg meet additional NYSE Compensation independence standards.', [473,775])
    fact('board_independence', 'Earley was independent during his service; the source also literally states heightened SEC independence standards for compensation committees.', [775], 'during service; did not stand for re-election at 2022 Annual Meeting')
    fact('membership_change', 'Earley retired from the Board following the May 2022 shareholder meeting; director fees cover service through that meeting.', [404,1538], 'following May 2022 shareholder meeting')
    fact('membership_change', 'Earley served on Compensation/Talent/Culture through May 12, 2022; the other 2022 members were May, Vojvodich Radakovich, Thornton and Weinberg, with none an employee/current or former officer during committee service.', [2528], '2022; Earley until May 12, 2022')
    fact('board_membership', 'Alexandra Ford English continues as a Board director after ending her employee role as Director, Global Brand Merchandising on June 17, 2022; non-employee director fees cover June–December.', [1233,1242,1537,1543], 'employee role ended June 17, 2022; Board service continues CURRENT_IN_FILING')
    fact('board_membership', 'Edsel B. Ford II is a former Ford director; the source does not supply a Board departure date here.', [1013,1015], 'FORMER_IN_FILING; Board departure date not stated')
    qualification_table = next(t for t in grid['tables'] if t['table_id'] == 'table_000103')
    assert (qualification_table['row_count'],qualification_table['column_count']) == (17,31)
    headings = {c['column_index']: c['text'] for c in qualification_table['rows'][0]['cells'] if c['column_index'] >= 4 and c['text'] != '\u200b'}
    matrix = []
    for row in qualification_table['rows'][1:]:
        matrix.append({'row':row['row_index'], 'label':row['cells'][2]['text'],
                       'marked_names_as_printed':[headings[c['column_index']] for c in row['cells'] if c['column_index'] in headings and c['text'] == '◾']})
    policy = {
        'status':'UNRESOLVED_QUALIFICATION_POLICY; retained as issuer statements, not independently verified credentials',
        'scope':'No automatic decision that skill/value assessments without a named standard constitute standalone required C02 qualification facts; no selector or Spec change.',
        'matrix':{'table_id':qualification_table['table_id'],'grid_sha256':qualification_table['grid_sha256'],'shape':[17,31],'basis_blocks':[1065,1066],'rows':matrix},
        'nomination_assessment_blocks':[1245,1248,1268,1271,1287,1289,1306,1310,1328,1331,1351,1354,1371,1374],
        'whole_current_slate_assessment_blocks':[1065,1066],
    }
    required = sorted({n for f in facts for n in f['source_blocks']}|set(policy['nomination_assessment_blocks'])|set(policy['whole_current_slate_assessment_blocks'])|{789,747,968,969,1305,1536,1545,2522,2523,2524,2525,2526,4523,4532,4533,4535,4558,4562,4564,4603})
    result = {
        'record_type':'ISSUE_47_C02_EXECUTOR_PRE_TRIAL_ORIGINAL_REFERENCE',
        'position':'ford_motor_company:2022-12-31',
        'reader':'Codex executor; full supplied visible text and necessary source-derived membership/qualification grids; development reference, not an independent input answer or human acceptance',
        'read_time_utc':'2026-10-04 07:41 UTC',
        'raw_asset_id':document['raw_asset_id'], 'source_reference_id':document['source_reference_id'], 'source_document_id':document['text_document_id'], 'source_filing':document['source_filing'],
        'request_sha256':sha(request), 'document_artifact_sha256':sha(source/'document.json'), 'grid_artifact_sha256':sha(source/'table-grid.json'), 'reader_notes_sha256':sha(notes),
        'pre_trial_state':'NO_NEW_INDEPENDENT_FORD_INPUT_ANSWER; additional child authorization pending',
        'visible_text_block_coverage':{'read':4912,'supplied':4912,'ranges':[[0,4911]],'all_supplied_visible_text_read':True,'all_media_filing_read':False},
        'reference_units':facts, 'reference_unit_count':len(facts),
        'units_are_consolidated_statements_not_atomic_complete_fact_count':True,
        'policy_unresolved_issuer_assessments':policy,
        'limits_and_counterchecks':[
            'Filing date March 31, 2023 and 2023 election/current descriptions are not assigned to December 31, 2022.',
            'B789 describes 14 then-current members attending the last annual meeting; B404 describes 15 to 14 following that meeting. Preserve both time statements, do not force a year-end snapshot.',
            'B747 unnamed Board subcommittees and management committees have no disclosed names/members; do not invent them or combine management membership with Board membership.',
            'B968/B969 24 persons combine directors and executive officers, not Board size.',
            'B1305/B1536 Huntsman Vice Chair, Policy May 2021–December 2022 is an executive role, not Board Vice Chair or a Board departure.',
            'B4523 disclaims shareholder-proposal assertions. B4535 refers to Earley as lead director/management-pay chair in a proposal discussing 2021 votes; preserve attribution, not current issuer determination.',
            'B4603 Responsible Business Alliance board chair is another entity, not a Ford Board appointment.',
            'B1545 specifies a December 31, 2022 director charitable-gift allocation basis; it does not alone identify a complete year-end roster.',
            'Source images are not interpreted. Full raw-HTML/media and complete numeric-context validation are not claimed.',
            'No output under the 4096 generation cap has yet been produced or independently validated for Ford. Consolidation is not permission to drop required facts.',
        ],
        'original_blocks':[dict(blocks[n],text_sha256=hashlib.sha256(blocks[n]['text'].encode()).hexdigest()) for n in required],
        'new_acceptances':0,'new_native_runs':0,'calls':[0,0,0], 'old_answers_runs_snapshots_unchanged':True,'production_authorized':False,
    }
    out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'reference_units':len(facts),'cited_original_blocks':len(required),'full_visible_text_blocks_read':4912,'independent_trial':'NOT_STARTED','calls':[0,0,0]}))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--notes',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); main(a.source,a.request,a.notes,a.out)
