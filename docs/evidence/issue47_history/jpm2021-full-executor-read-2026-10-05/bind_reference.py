"""Bind the executor's post-trial full-source reading, without reading an answer.

Manual statements and expected relationships below come from the executor's
reading. This helper checks bytes/cell positions; it is not a selector, model
answer or production input. The earlier seven-relation reference is unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(inputs, reading, notes_path):
    expected = {
        'document.json': '5e510d1b5a4ebcacf4833df7a434d1695ce087419c72123b591a669a0e818d39',
        'table-grid.json': '8f958f993e810d57aeab606aea5b4b02299ec066b80fcdd58cd1ec7a94fbcdcd',
        'request-body.json': 'c912d3a8bcd1ab5350eef9c733110e3a9fa9ae6ce7ec4ac1a635dd454835931a',
    }
    for filename, digest in expected.items():
        assert sha((inputs / filename).read_bytes()) == digest, 'ORIGINAL_INPUT_BYTES_CHANGED:' + filename
    doc = json.loads((inputs / 'document.json').read_bytes())
    raw = (inputs / 'original-primary.bin').read_bytes()
    assert sha(raw) == '5ac340fba4dc659432c6d3e01446914c7e18fd6b456a68660f644f071a6744fc'
    assert doc['raw_asset_id'] == 'sha256:' + sha(raw)
    assert len(doc['blocks']) == 4064
    for block in doc['blocks']:
        assert sha(raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256']
    notes = json.loads(notes_path.read_bytes())
    assert notes['complete'] and notes['read_parts'] == list(range(23))
    assert notes['read_blocks'] == [0, 4064]
    index = json.loads((reading / 'index.json').read_bytes())
    assert len(index['unfiltered_parts']) == 23
    for part in index['unfiltered_parts']:
        content = ''.join(f"B{b['block_index']} | {b['text']}\n"
                          for b in doc['blocks'][part['start_block']:part['end_block_exclusive']])
        assert (reading / part['path']).read_text() == content
        assert sha((reading / part['path']).read_bytes()) == part['sha256']
    grid = json.loads((inputs / 'table-grid.json').read_bytes())
    assert len(grid['tables']) == 428
    for table_index in [45, 128]:
        assert json.loads((reading / f'full-table-{table_index}.json').read_bytes()) == grid['tables'][table_index]
    table = grid['tables'][128]
    assert (table['row_count'], table['column_count']) == (12, 21)
    people = [
        ('Stephen B. Burke', 2004, 2, [364, 365, 366, 608, 609, 613, 614]),
        ('Linda B. Bammann', 2013, 3, [372, 373, 633, 634, 638]),
        ('Todd A. Combs', 2016, 4, [380, 381, 664, 665, 669]),
        ('James S. Crown', 2004, 5, [387, 388, 683, 684, 688]),
        ('James Dimon', 2004, 6, [392, 393, 717, 718, 719, 723]),
        ('Timothy P. Flynn', 2012, 7, [395, 396, 738, 739, 742]),
        ('Mellody Hobson', 2018, 8, [398, 399, 771, 772, 776]),
        ('Michael A. Neal', 2014, 9, [402, 403, 795, 796, 800]),
        ('Phebe N. Novakovic', 2020, 10, [407, 408, 822, 823, 826]),
        ('Virginia M. Rometty', 2020, 11, [410, 411, 848, 849, 853]),
    ]
    manual_committees = [
        ('Audit', 3, [(7, 'Chair'), (9, 'Member'), (10, 'Member')]),
        ('CMDC', 6, [(2, 'Chair'), (3, 'Member'), (4, 'Member'), (11, 'Member')]),
        ('Governance', 9, [(2, 'Member'), (4, 'Chair'), (11, 'Member')]),
        ('PRC', 12, [(5, 'Chair'), (8, 'Member'), (9, 'Member')]),
        ('Risk', 15, [(3, 'Chair'), (5, 'Member'), (8, 'Member')]),
    ]
    expected_names = {row: name for name, _, row, _ in people}
    for row, name in expected_names.items():
        printed = name + ('2' if row == 2 else '')
        assert table['rows'][row]['cells'][0]['text'] == printed
    relations = []
    for committee, column, members in manual_committees:
        assert table['rows'][1]['cells'][column]['text'] == committee
        for row, role in members:
            cell = table['rows'][row]['cells'][column]
            assert cell['is_origin'] and cell['text'] == role
            relations.append({'person': expected_names[row], 'committee': committee,
                              'role': role, 'row': row, 'column': column})
    specific = []
    for code, rows in [('A', [2, 4, 8, 11]), ('B', [3, 5, 9])]:
        for row in rows:
            assert table['rows'][row]['cells'][18]['text'] == code
            specific.append({'person': expected_names[row], 'printed_code': code,
                             'row': row, 'column': 18})
    assert len(relations) == 16 and len(specific) == 7
    units = []

    def add(kind, statement, blocks, time='CURRENT_IN_FILING', scope='COMPOSITION_OR_NAMED_STANDARD'):
        units.append({'id': 'R' + str(len(units) + 1).zfill(2), 'kind': kind,
                      'statement': statement, 'source_blocks': blocks,
                      'stated_time': time, 'judgment_scope': scope})

    add('time_boundary', 'The proxy is current April4,2022; ages are as of May17,2022. FY2021 is an annual container, not an automatic December31 board measurement.', [36, 526], scope='REFERENCE_BOUNDARY')
    add('board_size', 'All ten named nominees are actual current Firm directors and have agreed to a proposed one-year term if elected at the2022meeting. The slate is complete as stated, not an already completed2022election.', [357, 477, 527] + [p[3][0] for p in people])
    add('board_size', 'All ten directors serving at the2021annualmeeting attended that meeting; this is its stated2021measurement.', [528], '2021_ANNUAL_MEETING')
    for name, year, _, blocks in people:
        add('board_membership', f'{name} is a current nominee/director, with Firm director tenure since{year}.', [527] + blocks, f'SINCE_{year}; CURRENT_IN_2022_PROXY')
    add('board_independence', 'The Board determined the nine named non-management directors independent under NYSE and Firm standards; CEO James Dimon is the sole exception in the ten nominee slate.', [357, 885, 891])
    add('board_leadership', 'James Dimon is BoardChair andCEO; Firm BoardChair since2006, director since2004 andCEO since2005. BankOne predecessor roles are distinct.', [42, 43, 717, 718, 719, 723, 726], 'CHAIR_SINCE_2006; DIRECTOR_SINCE_2004; CEO_SINCE_2005')
    add('board_leadership', 'Stephen B.Burke has served as LeadIndependentDirector since2021; the independent directors actually reappointed him in March2022.', [57, 58, 613, 614, 617, 969, 970], 'SINCE_2021; REAPPOINTED_MARCH_2022')
    add('committee_structure', 'There are five independent principal standing committees: Audit; Compensation&ManagementDevelopment; CorporateGovernance&Nominating; PublicResponsibility; Risk. Their full names and abbreviations refer to the same named bodies.', [1041, 3887, 3898, 3918])
    for committee, _, members in manual_committees:
        names = ', '.join(expected_names[row] + (' (Chair)' if role == 'Chair' else '') for row, role in members)
        add('committee_membership', f'The current {committee} roster is {names}.', [1041, 1129, 1130] + list(range(1133, 1144)))
    add('committee_structure', 'The Board also has two standing committees named Stock Committee and Executive Committee. Their members/chairs are not named in the supplied current membership table.', [1109, 1110, 1111, 1112, 1129, 1130])
    add('committee_structure', 'Two specific-purpose committees currently exist: MarketsCompliance and Omnibus. Future possible committees and eventual disbandment are policies, not additional actual bodies.', [1114, 1115, 1116, 1117, 1118, 1119])
    add('committee_membership', 'A means MarketsCompliance. Printed A members are Burke,Combs,Hobson,Rometty; the footnote explicitly describes2021 in a current-membership table. Preserve those two time labels rather than invent a December31snapshot.', list(range(1129, 1147)), 'CURRENT_TABLE_WITH_EXPLICIT_2021_SPECIFIC_PURPOSE_FOOTNOTE')
    add('committee_membership', 'B means Omnibus. Printed B members are Bammann,Crown,Neal; same explicit2021/current-table temporal boundary. Neither specific committee chair is stated.', list(range(1129, 1147)), 'CURRENT_TABLE_WITH_EXPLICIT_2021_SPECIFIC_PURPOSE_FOOTNOTE')
    add('member_qualification', 'Every director who served on Audit orCMDC was determined to meet additional NYSE independence and qualitative criteria. This is the Board assessment, not a new independent credential verification.', [892], 'SERVED_AS_STATED_NO_EXACT_DATE')
    add('member_qualification', 'The2021 Audit members Flynn,Neal,Novakovic were determined SEC auditcommittee financialexperts. RiskChair Bammann was determined to have the large-complex-firm riskexperience under FederalReserve rules.', [1052], 'AUDIT_2021; RISK_DETERMINATION_AS_STATED')
    add('member_qualification', 'The March14,2022 Audit report names FlynnChair,Neal,Novakovic; three nonmanagement members with actualNYSE/SEC independence and financiallyliterate/SECexpert determinations.', [3323, 3324, 3356, 3357, 3358, 3359, 3360], 'MARCH_14_2022')
    add('committee_membership', 'The March15,2022 CMDC report names BurkeChair,Bammann,Combs,Rometty as independent directors comprising that committee.', [2677, 2678, 2679, 2680, 2681, 2682, 2683], 'MARCH_15_2022')
    add('member_qualification', 'CMDC employment disclosure has an actual exception: Bammann previously was a JPMofficer,15years before joiningCMDC and8before joiningBoard. The otherCMDC members are stated never to have been Firm officers/employees; this does not revoke affirmed independence.', [417, 1386, 1387, 1388, 891, 892], scope='ACTUAL_EMPLOYMENT_RELATION_WITH_QUALIFICATION_SCOPE_PENDING')
    add('entity_boundary', 'All Firm directors elected in2021 also comprise the full subsidiaryBank andIHC boards; Burke is independentBankChair andIHC has noChair. Do not add duplicateparentmembers or assignBankChair toparentBoard.', [1148, 3870, 3903], scope='SEPARATE_SUBSIDIARY_BOARDS')
    add('tenure_boundary', 'Heritage-company director tenures include BurkeBankOne2003-04,CrownBankOne1996-04/FirstChicago1991-96,DimonBankOneChair2000-04; they do not backdate currentFirm tenures.', [415, 726], scope='REFERENCE_BOUNDARY')
    for name, _, _, block in [('Burke', 0, 0, 616), ('Bammann', 0, 0, 640), ('Combs', 0, 0, 671), ('Crown', 0, 0, 690), ('Dimon', 0, 0, 720), ('Flynn', 0, 0, 744), ('Hobson', 0, 0, 778), ('Neal', 0, 0, 802), ('Novakovic', 0, 0, 828), ('Rometty', 0, 0, 855)]:
        add('issuer_assessment', f'The issuer makes a named skills/experience assessment about{name}; retain its attribution. Scope as a C02qualification/roleevaluation awaits owner clarification.', [block], scope='OWNER_SCOPE_PENDING')
    add('issuer_assessment', 'Issuer says all nominees possess listed attributes; skillmatrix information is nominee-provided. Matriximages are not interpreted here; generic candidatecriteria are not actualcredentials.', [526, 531, 562, 563], scope='OWNER_SCOPE_PENDING')
    add('membership_change', 'Issuer says threefemale directors were elected over thepastfouryears,onepersonofcolor; twohave technologyexperience. It does not give a precise interval or name-gender matrix association in that passage.', [3535, 3545], 'PAST_FOUR_YEARS_AS_STATED_IN_2022_PROXY')
    add('issuer_assessment', 'Eachdirector actually attended75%ormore ofBoard/committee meetings in2021. This remains an attributedperformance fact with policy/role scope pending.', [960, 1039], '2021', scope='OWNER_SCOPE_PENDING')
    add('source_scope_uncertainty', 'Principal-five committee independence is explicit, while a laterBoardresponse says eachCommittee chaired/constituted byindependentdirectors without namingadditionalbody members. Keep literalbroader wording; do not inventStock/Executive rosters.', [1041, 1110, 1111, 1112, 3510], scope='UNRESOLVED_SOURCE_SCOPE')
    add('future_policy_boundary', 'NextCEOtransition separation policy was adopted thisyear subject toBoarddiscretion. Proponent independentChairrequest andfuturetransition are not a currentappointment oractualsplit.', [971, 3481, 3482, 3483, 3484, 3485, 3486, 3498, 3508, 3512], scope='REFERENCE_BOUNDARY')
    add('ownership_boundary', 'February28,2022 ownership combines21directors/currentexecutives,not21directors. Crownattributedshares canbe pledgedunderstatedexception; personalshares remainunpledged. Noautomaticindependencechange.', [1348, 3199, 3231, 3232, 3236], scope='REFERENCE_BOUNDARY')
    cited = sorted({b for unit in units for b in unit['source_blocks']})
    return {
        'record_type': 'ISSUE47_JPM_FY2021_POST_TRIAL_FULL_EXECUTOR_REFERENCE',
        'position': 'jpmorgan_chase:2021-12-31:C02',
        'raw_asset_id': doc['raw_asset_id'], 'source_filing': doc['source_filing'],
        'original_request_sha256': sha((inputs / 'request-body.json').read_bytes()),
        'all_4064_blocks_read': True, 'unfiltered_reading_parts': 23,
        'full_necessary_tables': [{'index': i, 'grid_sha256': grid['tables'][i]['grid_sha256'],
                                  'rows': grid['tables'][i]['row_count'], 'columns': grid['tables'][i]['column_count']}
                                 for i in [45, 128]],
        'reference_units': units, 'standing_positive_member_relations': relations,
        'specific_positive_code_relations': specific,
        'source_excerpts': [doc['blocks'][b] for b in cited],
        'reader_notes_sha256': sha(notes_path.read_bytes()),
        'prior_independent_trial_already_existed': True,
        'pre_original_trial_frozen_reference_claimed': False,
        'earlier_seven_relation_reference_changed': False,
        'old_answer_read_by_binder': False,
        'other_426_tables_or_images_fully_interpreted': False,
        'runtime_wired': False, 'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--reading', type=Path, required=True)
    p.add_argument('--notes', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    result = bind(args.inputs, args.reading, args.notes)
    with args.out.open('x') as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'units': len(result['reference_units']),
                      'cited_blocks': len(result['source_excerpts']),
                      'sha256': sha(args.out.read_bytes()), 'calls': [0, 0, 0]}, indent=1))
