"""Bind manually read Lumen statements to unchanged supplied source bytes.

This development helper checks bytes and locators. It does not decide business
meaning, build a Run, select production facts, or confer accepted coverage.
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
    assert sha(raw) == doc['raw_asset_id'][7:]
    blocks = {b['block_index']: b for b in doc['blocks']}
    assert set(blocks) == set(range(5219))
    assert notes['complete_supplied_visible_text_read'] is True
    assert [i for p in notes['read_packets']
            for i in range(p['blocks'][0], p['blocks'][1] + 1)] == list(range(5219))
    for block in blocks.values():
        assert sha(raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256']
    for name, digest in metadata['artifacts'].items():
        assert sha((args.input / name).read_bytes()) == digest
    tables = {t['table_id']: t for t in grid['tables']}
    necessary_ids = ('table_000087', 'table_000090', 'table_000116', 'table_000255')
    units = []

    def add(statement, indexes, kind, scope, cells=()):
        locators = []
        for table_id, row, column in cells:
            cell = tables[table_id]['rows'][row]['cells'][column]
            assert (cell['row_index'], cell['column_index']) == (row, column)
            assert cell['is_origin']
            locators.append({'table_id': table_id, **cell})
        units.append({'reference_unit_id': f'L21-{len(units) + 1:02}',
                      'kind': kind, 'statement': statement, 'time_scope': scope,
                      'source_blocks': [blocks[i] for i in indexes],
                      'table_cells': locators,
                      'authority': 'EXECUTOR_MANUAL_DEVELOPMENT_REFERENCE'})

    for note in notes['reference_notes']:
        add(note['statement'], note['blocks'], 'CONSOLIDATED_READ_NOTE',
            'Preserve the source time, speaker and entity stated in each note.')
    current = ('Proxy April 7, 2022, filed April 8; information defaults to proxy date '
               'unless otherwise stated. FY2021 is an annual container, not a '
               'December 31 Board measurement.')
    roster = [
        ('Quincy L. Allen', 2021, 'Audit and Risk and Security member',
         [516, 518, 529, 530, 532, 533, 534]),
        ('Martha Helena Bejar', 2016, 'HRCC member and NCG Chair',
         [544, 545, 547, 563, 564, 566, 567, 568]),
        ('Peter C. Brown', 2009, 'Audit and Risk and Security member',
         [580, 582, 592, 593, 595, 596, 597]),
        ('Kevin P. Chilton', 2017, 'Audit member and Risk and Security Chair',
         [607, 609, 617, 618, 620, 621, 622, 623]),
        ('Steven T. "Terry" Clontz', 2017, 'HRCC and NCG member',
         [637, 638, 640, 659, 660, 662, 663, 664, 665]),
        ('T. Michael Glenn', 2017, 'independent non-executive Board Chair and HRCC member',
         [676, 677, 679, 692, 693, 695, 696, 697, 698]),
        ('W. Bruce Hanks', 1992, 'Board Vice Chair and Audit Chair',
         [710, 712, 729, 730, 732, 733, 734]),
        ('Hal Stanley Jones', 2020, 'Audit and Risk and Security member',
         [745, 746, 748, 756, 757, 759, 760, 761]),
        ('Michael J. Roberts', 2011, 'HRCC and NCG member',
         [775, 777, 787, 788, 790, 791, 792, 793, 794, 1202]),
        ('Laurie A. Siegel', 2009, 'HRCC Chair and NCG member',
         [803, 805, 818, 819, 821, 822, 823, 824, 825, 826, 1203]),
        ('Jeffrey K. Storey', 2017, 'Risk and Security member; President and CEO since 2018',
         [837, 838, 840, 842, 858, 860, 861, 862, 976]),
    ]
    for name, since, role, indexes in roster:
        add(f'{name}: one of eleven current directors nominated for re-election; '
            f'director since {since}; {role}.', [259, 452, 515] + indexes,
            'NAMED_CURRENT_COMPOSITION', current)
    add('The early-2022 Board determination finds all ten non-Storey nominees '
        'independent. SEC/NYSE/Corporate Governance Guidelines are the disclosed '
        'standards. The source separately states ten of eleven nominees independent; '
        'this is the nominee/current disclosure frame, not an invented year-end census.',
        [259, 425, 426, 888, 891, 976], 'NAMED_INDEPENDENCE_STANDARD', current)
    add('Glenn became independent, non-executive Board Chairman effective May 20, '
        '2020; Hanks continued as Vice Chairman. Their current roles and service '
        'during 2021 are separately stated.', [695, 732, 896, 897, 1222, 1223],
        'LEADERSHIP_AND_DATED_CHANGE', 'May 20, 2020; during 2021; current proxy roles.')
    committees = [
        ('Audit', 'W. Bruce Hanks', ['Quincy L. Allen', 'Peter C. Brown',
                                  'Kevin P. Chilton', 'Hal Stanley Jones'],
         list(range(905, 912)) + [1288, 1289, 1290, 1291, 1292, 1293],
         [('table_000087', 2, 0), ('table_000087', 2, 9), ('table_000087', 2, 12)]),
        ('Human Resources and Compensation', 'Laurie A. Siegel',
         ['T. Michael Glenn', 'Steven T. "Terry" Clontz', 'Michael J. Roberts',
          'Martha Helena Bejar'], [259, 923, 925, 926, 927, 928, 929, 930] + list(range(2180, 2186)),
         [('table_000087', 11, 0), ('table_000087', 11, 9), ('table_000087', 11, 12)]),
        ('Nominating and Corporate Governance', 'Martha Helena Bejar',
         ['Michael J. Roberts', 'Steven T. "Terry" Clontz', 'Laurie A. Siegel'],
         [259] + list(range(940, 947)),
         [('table_000090', 4, 0), ('table_000090', 4, 9), ('table_000090', 4, 12)]),
        ('Risk and Security', 'Kevin P. Chilton',
         ['Quincy L. Allen', 'Peter C. Brown', 'Jeffrey K. Storey', 'Hal Stanley Jones'],
         list(range(957, 965)) + [976],
         [('table_000090', 12, 0), ('table_000090', 12, 9), ('table_000090', 12, 12)]),
    ]
    for title, chair, members, indexes, cells in committees:
        add(f'{title} Committee: Chair {chair}; other members {", ".join(members)}.',
            [904] + indexes, 'COMPLETE_NAMED_COMMITTEE_ROSTER', current, cells)
    add('Each of the five Audit members is an "audit committee financial expert". '
        'Audit, HRCC and NCG members are all independent. Risk includes Storey, '
        'the only non-independent director, so the three-committee independence '
        'statement cannot be extended to all four.',
        [427, 904, 905, 906, 907, 908, 909, 910, 911, 922, 976, 1181],
        'NAMED_COMMITTEE_QUALIFICATIONS', current,
        [('table_000087', 9, 0), ('table_000090', 18, 0)])
    add('Risk and Security explicitly oversees classified activities and facilities '
        'through a subcommittee. Its actual existence is supported; this passage '
        'does not disclose its formal name, members or Chair.', [957, 967, 972],
        'EXISTING_SUBCOMMITTEE_WITH_UNRESOLVED_ROSTER', current,
        [('table_000090', 17, 6)])
    add('Allen joined the Board effective February 25, 2021. Jones was added '
        'effective January 1, 2020. Virginia Boulet is explicitly a former director '
        'whose term ended at the 2021 annual shareholders meeting; no exact day '
        'is assigned by interpreting unrelated equity grant dates.',
        [470, 471, 1204, 1205, 1210, 1211], 'DATED_MEMBERSHIP_CHANGES',
        'February 25, 2021; January 1, 2020; the 2021 annual meeting.',
        [('table_000116', 14, 0), ('table_000116', 15, 0)])
    add('During the last fiscal year HRCC had Siegel, Bejar, Clontz, Glenn and '
        'Roberts; none served as a Company/subsidiary officer or employee before '
        'or while serving on HRCC. Preserve this actual non-employee determination '
        'without adding a regulatory designation absent from the passage.',
        [2654, 2655], 'NAMED_COMPENSATION_NONEMPLOYEE_DETERMINATION', 'FY2021.')
    add('Eleven nominees are proposed for a one-year term through the 2023 '
        'annual meeting or until a successor is elected and qualified; each still '
        'requires election. The separate eleven-director count immediately '
        'following the 2022 meeting is prospective, not a completed vote or '
        'December 31, 2021 measurement.', [452, 453, 515, 2700, 2756],
        'PROSPECTIVE_SLATE_AND_COUNT', 'Proposed May 18, 2022 meeting and future term.')
    body = {
        'record_type': 'ISSUE47_LUMEN_FY2021_FULL_SUPPLIED_TEXT_EXECUTOR_REFERENCE',
        'position': 'lumen_technologies:2021-12-31',
        'source_filing': doc['source_filing'], 'raw_asset_id': doc['raw_asset_id'],
        'document_id': doc['text_document_id'],
        'request_sha256': sha((args.input / 'request-body.json').read_bytes()),
        'all_5219_supplied_text_blocks_read': True, 'all_5219_raw_spans_verified': True,
        'reading_notes': notes, 'reference_units': units,
        'necessary_full_tables_read_and_preserved': [tables[i] for i in necessary_ids],
        'positive_standing_committee_relations_supported_by_named_text': 19,
        'all_629_tables_read': False, 'all_media_interpreted': False,
        'unresolved': [
            {'kind': 'QUALIFICATION_POLICY', 'blocks': [470, 471, 479, 494, 518,
             547, 582, 609, 640, 679, 712, 748, 777, 805, 840],
             'detail': 'Actual issuer assessments of named nominees and skills remain '
                       'preserved; #28 role/qualification evaluation reply is pending. '
                       'Career credentials alone are not newly determined regulatory status.'},
            {'kind': 'SUBCOMMITTEE_ROSTER', 'blocks': [972],
             'detail': 'Existing classified-activities subcommittee has no named '
                       'roster/Chair in the relevant passage; no assumed absences.'},
            {'kind': 'TIME_AND_ENTITY', 'blocks': [259, 2756, 2870],
             'detail': 'Current April 2022 proxy, FY2021 excerpts unupdated since '
                       'February 24, 2022, future slate and historical changes remain distinct. '
                       'Other issuers, management councils and mixed ownership groups '
                       'do not become additional parent Board members.'},
            {'kind': 'COMMITTEE_NAME', 'blocks': [259, 2870, 4730],
             'detail': 'Annual appendix Compensation Committee naming is retained '
                       'alongside proxy HRCC; no fifth committee or delegated officer '
                       'membership is invented from equity-plan mechanics.'},
            {'kind': 'MEDIA_AND_CONTEXT_METHOD',
             'detail': 'All supplied text read; four necessary full grids read, '
                       'other graphics/media not semantically interpreted. Original '
                       'single request exceeds 200000; two whole-table responsibility '
                       'prototypes fit separately but have no independent method validation.'},
        ],
        'complete_c02_acceptance': False, 'native_run_created': False,
        'existing_results_modified': False, 'new_acceptances': 0, 'calls': [0, 0, 0],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'blocks': 5219, 'reference_units': len(units),
                      'necessary_tables': len(necessary_ids),
                      'named_text_committee_relations': 19, 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
