"""Bind current normal-source excerpts and record explicit manual comparisons.

This is not a replacement selector or a Run/Result acceptance operation.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    for name in ('selector', 'reference', 'document', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    reference = json.loads(args.reference.read_text())
    document = json.loads(args.document.read_text())
    selector = json.loads(args.selector.read_text())
    assert reference['all_6365_supplied_text_blocks_read'] is True
    proposal, = selector['proposals'].values()
    assert proposal['source_reference_id'] == document['source_reference_id']
    assert len(proposal['candidates']) == 81
    selected = {c['block_index']: c for c in proposal['candidates']}
    assert len(selected) == 81
    bound = []
    for index, claim in selected.items():
        b = document['blocks'][index]
        assert claim['text'] == b['text']
        for key in ('raw_start_byte', 'raw_end_byte', 'raw_span_sha256'):
            assert claim[key] == b[key]
        bound.append({'selected_excerpt': claim, 'source_block': b})
    missing_card_fields = [551, 552, 578, 579, 611, 612, 636, 637, 663, 664,
                           697, 698, 719, 720, 747, 748, 771, 772, 794, 795]
    assert not set(missing_card_fields) & set(selected)
    assert 946 not in selected
    assert {876, 877, 878, 886, 1281, 1879} <= set(selected)
    assert set(range(1406, 1413)) <= set(selected)
    assert set(range(2837, 2843)) <= set(selected)
    assert 3663 in selected and 1315 in selected
    findings = [
        {'kind': 'CORE_RELATIONS_ALREADY_SUPPORTED',
         'selected_blocks': [414, 415, 468, 512, 854, 876, 877, 878, 886, 893,
                             905, 1277, 1280, 1281, 1315, 1879, 3663],
         'manual_judgment': 'All ten nominee names and their named positive card '
             'committee relations, Audit/Hanks Chair and HRCC full signed names, '
             'independence conclusions, Hanks current retiring status/since1992, '
             'Glenn leadership, Storey/Johnson November2022 transition, Allen '
             'February25,2021 appointment, Boulet2021 retirement and the actual '
             'four named CEO Succession Committee members are already represented '
             'by selected source text. Do not call the pay-paragraph special '
             'committee omitted: b1281 is selected.'},
        {'kind': 'DIRECTOR_SINCE_FIELDS_OMITTED',
         'source_blocks': missing_card_fields,
         'manual_judgment': 'Both heading and year from each of the ten nominee '
             'cards are omitted. Allen2021 and Johnson2022 membership years are '
             'already supported by dated selected transition/appointment passages; '
             'do not count those redundancies as missed facts. Eight other named '
             'since-years (Bejar2016, Brown2009, Chilton2017, Clontz2017, Glenn2017, '
             'Jones2020, Roberts2011, Siegel2009) are not supplied by the other '
             'selected passages. Jones exact January1,2020 appointment in2784 '
             'is also omitted; Hanks1992 is already selected in876.'},
        {'kind': 'ACTUAL_RISK_SUBCOMMITTEE_OMITTED', 'source_blocks': [937, 938, 946],
         'manual_judgment': 'The actual classified-activities/facilities subcommittee '
             'relation in946 is absent. Preserve existence and unresolved formal '
             'name/members/Chair; do not invent a fifth standing committee.'},
        {'kind': 'NOVEMBER7_DAY_AND_ADVISER_BOUNDARY',
         'source_blocks': [462, 463, 1782, 1809, 1901, 1902, 1903],
         'selected_blocks': [877],
         'manual_judgment': 'The selected November2022 Board departure/join is '
             'supported. The explicit November7 succession day and direct '
             'Board-retirement coupling are outside the selected set. December31 '
             'adviser/employment termination must not substitute for the Board '
             'date. The old selection does not itself assert that wrong day.'},
        {'kind': 'SOURCE_COUNT_LIMIT_RETAINED_NOT_SETTLED',
         'selected_blocks': [468, 876, 1315, 3593, 3663],
         'manual_judgment': 'Current Hanks plus ten nominees do not make the slate '
             'the full Board census. Future FAQ11 and planned immediate-after '
             'retirement are both selected and remain a source timing/consistency '
             'limit. Selecting both does not settle the contradiction or prove '
             'a year-end snapshot.'},
        {'kind': 'POLICY_AND_MEDIA_PENDING', 'source_blocks': [517, 854, 2784, 2785,
                                                                2829, 6186],
         'manual_judgment': 'Selected854 mixes actual independence with issuer '
             'suitability judgments. Other named expertise/stock-policy/hedging '
             'assessments remain qualification-role-policy pending, not new '
             'confirmed defects or automatic credit. Proposed Plan Rule16b3 '
             'requirement is not an actual qualification. Committee/skills '
             'images remain uninterpreted; ordered plain excerpts are not a '
             'validated complete typed person-role-time answer.'},
    ]
    receipt = {
        'record_type': 'ISSUE47_LUMEN_FY2022_FULL_REFERENCE_CURRENT_RULE_COMPARISON',
        'position': 'lumen_technologies:2022-12-31:C02',
        'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        'selector_sha256': hashlib.sha256(args.selector.read_bytes()).hexdigest(),
        'selected_excerpt_count': 81, 'all_selected_text_and_raw_spans_match': True,
        'bound_selected_excerpts': bound,
        'manual_findings': findings,
        'unselected_since_field_source_blocks': [document['blocks'][i] for i in missing_card_fields],
        'unselected_actual_subcommittee_source_block': document['blocks'][946],
        'native_run_or_result_compared': False,
        'current_rule_proposal_only': True, 'rule_selection_modified': False,
        'existing_results_modified': False, 'existing_acceptance_changed': False,
        'complete_metric_acceptance': False, 'new_runs': 0, 'new_acceptances': 0,
        'calls': [0, 0, 0],
    }
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'selected': 81, 'all_text_and_spans_match': True,
                      'manual_findings': len(findings),
                      'complete_metric_acceptance': False, 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
