"""Bind the complete Lumen FY2022 executor reading; no fact selection engine.

Manual statements retain their actual dates, entities and unresolved relations.
Only bytes, original indices and table cells are mechanically checked here.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('input', 'reading-notes', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    doc = json.loads((args.input / 'document.json').read_text())
    grid = json.loads((args.input / 'table-grid.json').read_text())
    metadata = json.loads((args.input / 'metadata.json').read_text())
    notes = json.loads(args.reading_notes.read_text())
    raw = (args.input / 'original-primary.bin').read_bytes()
    assert 'sha256:' + sha(raw) == doc['raw_asset_id']
    assert notes['complete_supplied_visible_text_read'] is True
    assert [i for p in notes['read_packets'] for i in
            range(p['blocks'][0], p['blocks'][1] + 1)] == list(range(6365))
    blocks = {b['block_index']: b for b in doc['blocks']}
    assert set(blocks) == set(range(6365))
    for b in blocks.values():
        assert sha(raw[b['raw_start_byte']:b['raw_end_byte']]) == b['raw_span_sha256']
    for name, digest in metadata['artifacts'].items():
        assert sha((args.input / name).read_bytes()) == digest
    tables = {t['table_id']: t for t in grid['tables']}
    necessary = ['table_000120', 'table_000130', 'table_000292']
    units = []

    def add(statement, indices, kind, scope, cells=()):
        locators = []
        for table_id, row, column in cells:
            cell = tables[table_id]['rows'][row]['cells'][column]
            assert cell['is_origin']
            assert (cell['row_index'], cell['column_index']) == (row, column)
            locators.append({'table_id': table_id, **cell})
        units.append({'reference_unit_id': f'L22-{len(units) + 1:02}',
                      'statement': statement, 'kind': kind, 'time_scope': scope,
                      'source_blocks': [blocks[i] for i in indices],
                      'table_cells': locators,
                      'authority': 'EXECUTOR_MANUAL_DEVELOPMENT_REFERENCE'})

    for note in notes['reference_notes']:
        add(note['statement'], note['blocks'], 'CONSOLIDATED_READ_NOTE',
            'Preserve the time, speaker and entity stated by the original source.')
    current = ('Current April 5, 2023 proxy unless locally stated otherwise; '
               'FY2022 is an annual container, not a Board year-end measurement.')
    roster = [
        ('Quincy L. Allen', 2021, 'independent; Audit and Risk and Security member',
         [551, 552, 553, 555, 556, 557, 558]),
        ('Martha Helena Bejar', 2016, 'independent; HRCC member and NCG Chair',
         [578, 579, 580, 582, 583, 584, 585]),
        ('Peter C. Brown', 2009, 'independent; Audit and Risk and Security member',
         [611, 612, 613, 615, 616, 617, 618]),
        ('Kevin P. Chilton', 2017, 'independent; Audit member and Risk and Security Chair',
         [636, 637, 638, 640, 641, 642, 643]),
        ('Steven T. "Terry" Clontz', 2017, 'independent; HRCC and NCG member',
         [663, 664, 665, 667, 668, 669, 670]),
        ('T. Michael Glenn', 2017, 'independent non-executive Board Chairman; HRCC member',
         [697, 698, 699, 700, 701, 702, 703, 886, 1280, 1950]),
        ('Kate Johnson', 2022, 'President and CEO; card explicitly lists committees None',
         [462, 719, 720, 722, 723, 724, 728]),
        ('Hal Stanley Jones', 2020, 'independent; Audit and Risk and Security member',
         [747, 748, 749, 751, 752, 753, 754]),
        ('Michael J. Roberts', 2011, 'independent; HRCC and NCG member',
         [771, 772, 773, 775, 776, 777, 778, 1306]),
        ('Laurie A. Siegel', 2009, 'independent; HRCC Chair and NCG member',
         [794, 795, 796, 798, 799, 800, 801, 1307]),
    ]
    for name, since, role, indices in roster:
        add(f'{name}: current director nominated for election; director since {since}; {role}.',
            [254, 468, 469] + indices, 'NAMED_CURRENT_NOMINEE', current)
    add('W. Bruce Hanks remains a current director since 1992, non-executive '
        'Vice Chairman and Audit Chair; he is not one of the ten nominees. His '
        'term is planned to end immediately following the 2023 annual meeting.',
        [876, 889, 1280, 1308, 1309, 1315, 1406, 1407, 1408, 3522],
        'CURRENT_RETIRING_DIRECTOR_NOT_NOMINEE', current,
        [('table_000120', 12, 0), ('table_000120', 13, 0),
         ('table_000130', 2, 0), ('table_000292', 19, 0)])
    add('Ten nominees and still-current retiring Hanks supply eleven named '
        'current Board members. Nine of ten nominees are independent and Johnson '
        'is the CEO exception; the source also states all directors other than '
        'the CEO independent. The fifteen-person current executive/director '
        'ownership group is a mixed group, not the Board count.',
        [414, 468, 854, 876, 889, 1315, 1623, 3482] + list(range(3513, 3527)),
        'NAMED_CURRENT_ENUMERATION_AND_FRAME', current,
        [('table_000292', 12, 0), ('table_000292', 23, 0)])
    add('The early-2023 Board independence determination uses SEC/NYSE/Corporate '
        'Governance Guidelines and excludes Johnson. Brown, Roberts and Siegel '
        'receive an explicit long-tenure independence conclusion; suitability '
        'and role assessments in the same paragraph remain policy-pending.',
        [414, 854], 'ACTUAL_INDEPENDENCE_DETERMINATIONS', 'Early 2023/current proxy.')
    add('Glenn is independent non-executive Chairman since May 2020. Hanks is '
        'current Vice Chairman; no successor Vice Chairman is planned when he '
        'retires at the 2023 annual meeting. This is a stated future plan, not '
        'a completed elimination. The supplied FY2022 input does not state May20 '
        'as the day of Glenn appointment, so that day is not imported from an '
        'earlier-year proxy.', [700, 876, 885, 886, 889, 1277, 1280, 1315],
        'CURRENT_LEADERSHIP_AND_PLAN', current)
    add('Johnson joined as CEO and Board member on November 7, 2022; Storey '
        'retired/resigned as CEO and Board member upon her succession. His '
        'special-adviser employment continued through December31, which is '
        'distinct from Board service. Both the actual Board language and the '
        'dated succession clauses are required for this relation.',
        [462, 463, 877, 1138, 1782, 1809, 1901, 1902, 1903, 3353],
        'ACTUAL_DATED_BOARD_TRANSITION', 'November 7, 2022 transition; adviser/employment through December31.')
    add('Boulet retired at the 2021 annual meeting after 26 years service; Allen '
        'joined effective February25,2021. Jones joined January1,2020. These '
        'historical source facts are distinct from current nominees.',
        [878, 2784], 'ACTUAL_HISTORICAL_MEMBERSHIP_CHANGES',
        '2021 annual meeting; February25,2021; January1,2020.')
    add('Four standing committees are Audit, Human Resources and Compensation, '
        'Nominating and Corporate Governance, and Risk and Security; all four '
        'have independent members in this proxy. The named-text positive '
        'relations below are supported without decoding committee-page images; '
        'image-roster exhaustiveness is not inferred from blank cells.',
        [254, 415, 893, 894, 909, 920, 937, 938],
        'EXISTING_STANDING_COMMITTEES', current)
    add('Audit: Hanks Chair, Allen, Brown, Chilton and Jones are named by the '
        'signed report and current cards; each Audit member is an audit committee '
        'financial expert. Retain that exact title without inventing a separate '
        'unstated regulatory attribution.', [415, 556, 616, 641, 752, 894, 905,
         1404, 1406, 1407, 1408, 1409, 1410, 1411, 1412],
        'NAMED_AUDIT_MEMBERS_AND_QUALIFICATION', current,
        [('table_000130', 2, col) for col in (0, 3, 6, 9, 12)])
    add('HRCC: Siegel Chair, Bejar, Clontz, Glenn and Roberts. The signed '
        'report corroborates all five current card relations. FY2022 interlocks '
        'explicitly state none served as a Company/subsidiary officer or employee '
        'before or while serving on HRCC; this is an actual named determination, '
        'not the proposed Plan Rule16b3 requirement.',
        [415, 583, 668, 702, 776, 799, 1253] + list(range(2835, 2843)) + [3544, 3545],
        'NAMED_HRCC_MEMBERS_AND_NONEMPLOYEE_DETERMINATION',
        'Current proxy roster and explicit FY2022 interlocks statement.')
    add('NCG: Bejar Chair, Clontz, Roberts and Siegel are current members '
        'supported by the complete named cards.', [254, 415, 584, 585, 669, 670,
         777, 778, 800, 801, 920], 'NAMED_NCG_POSITIVE_RELATIONS', current)
    add('Risk and Security: Chilton Chair, Allen, Brown and Jones are four '
        'named current positive members supported by their cards. Johnson card '
        'lists None. Committee-page image contents and possible additional '
        'relations are not resolved from their absent rendered text.',
        [415, 557, 558, 617, 618, 642, 643, 723, 724, 753, 754, 937, 938],
        'NAMED_RISK_POSITIVE_RELATIONS', current)
    add('Risk and Security explicitly oversees classified activities/facilities '
        'through a subcommittee; its existence is real, formal name/members/Chair '
        'remain undisclosed in this passage.', [937, 938, 946],
        'ACTUAL_SUBCOMMITTEE_WITH_UNRESOLVED_ROSTER', current)
    add('In early2022 the Board formed a special CEO Succession Committee; '
        'Bejar, Siegel, Glenn and Hanks are explicitly named for service on it. '
        'The role list is Board/Audit/HRCC/NCG Chairs. It evaluated CEO candidates '
        'and is distinct from the general nomination workflow search committee '
        'that includes CEO under its procedural definition.',
        [842, 956, 957, 958, 1281, 1879, 1880, 1897, 1898, 1899],
        'ACTUAL_NAMED_SPECIAL_CEO_COMMITTEE', 'Early2022/CEO succession during2022.')
    add('The FAQ literally says eleven directors immediately following the '
        'meeting. Preserve that prospective count alongside ten proposed '
        'nominees and Hanks planned immediate-after-meeting retirement; the '
        'source consistency/timing is unresolved, not silently repaired to ten '
        'or explained as proven stale boilerplate.', [468, 469, 876, 889, 1315, 3593, 3663],
        'SOURCE_COUNT_CONSISTENCY_UNRESOLVED', 'Proposed 2023 meeting and immediately following.')
    body = {
        'record_type': 'ISSUE47_LUMEN_FY2022_FULL_SUPPLIED_TEXT_EXECUTOR_REFERENCE',
        'position': 'lumen_technologies:2022-12-31',
        'source_filing': doc['source_filing'], 'raw_asset_id': doc['raw_asset_id'],
        'document_id': doc['text_document_id'],
        'request_sha256': sha((args.input / 'request-body.json').read_bytes()),
        'all_6365_supplied_text_blocks_read': True, 'all_6365_raw_spans_verified': True,
        'reading_notes': notes, 'reference_units': units,
        'necessary_full_tables_read_and_preserved': [tables[t] for t in necessary],
        'named_text_standing_committee_positive_relations': 18,
        'named_text_special_ceo_committee_positive_relations': 4,
        'all_511_tables_semantically_read': False, 'all_media_interpreted': False,
        'unresolved': [
            {'kind': 'PROSPECTIVE_COUNT_CONSISTENCY', 'blocks': [468, 1315, 3663],
             'detail': 'Ten nominees and Hanks planned retirement versus literal '
                       'eleven immediately following meeting remain as source statements.'},
            {'kind': 'QUALIFICATION_ROLE_POLICY', 'blocks': [517, 854, 2784, 2785, 2829],
             'detail': 'Named issuer suitability/skills, actual stock/antihedging '
                       'policy compliance assessments retain source identity. No '
                       'independence revocation from six stock-guideline shortfalls; '
                       '#28 role/qualification-policy reply remains pending.'},
            {'kind': 'MEDIA_AND_ROSTER_COMPLETENESS', 'blocks': [894, 909, 920, 937, 938, 946],
             'detail': 'Committee-page image names/skill matrix and other images '
                       'not interpreted. Eighteen standing/four special positive '
                       'relations are supported; no negative inference from blanks '
                       'or whole-media/metric exhaustiveness claim.'},
            {'kind': 'PLAN_RULE_VERSUS_ACTUAL_QUALIFICATION', 'blocks': [1418, 1423, 1482, 6183, 6186],
             'detail': 'Proposed Plan minimumtwo/Rule16b3 shallqualify is a normative '
                       'requirement, not a new actual named qualification or body.'},
            {'kind': 'DISTRIBUTED_CONTEXT_METHOD',
             'detail': 'Original265856 input exceeds200000. Earlier all-text '
                       'responsibilities both exceed; new136262/187133 inputs fit '
                       'with4096 reserves and complete union. No independent '
                       'generation/reconciliation/full-metric method proof or wiring.'},
        ],
        'complete_c02_acceptance': False, 'native_run_created': False,
        'existing_results_modified': False, 'new_acceptances': 0, 'calls': [0, 0, 0],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'blocks': 6365, 'reference_units': len(units),
                      'necessary_tables': len(necessary), 'positive_standing_relations': 18,
                      'positive_special_relations': 4, 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
