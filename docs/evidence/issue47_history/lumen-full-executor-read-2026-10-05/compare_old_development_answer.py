"""Bind an unchanged old answer and record manual source comparisons.

This helper does not select facts, judge semantics automatically, repair old
answers, or grant/withdraw accepted Result credit.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ('document', 'answer', 'reference', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    doc = json.loads(args.document.read_text())
    blocks = {b['block_index']: b for b in doc['blocks']}
    answer = json.loads(args.answer.read_text())
    reference = json.loads(args.reference.read_text())
    assert reference['all_5219_supplied_text_blocks_read'] is True
    assert len(answer['facts']) == 34
    bound = []
    for i, fact in enumerate(answer['facts']):
        assert fact['source_blocks']
        assert all(type(index) is int and index in blocks for index in fact['source_blocks'])
        bound.append({'fact_index': i, 'original_fact': fact,
                      'source_blocks': [blocks[index] for index in fact['source_blocks']]})
    findings = [
        {'kind': 'CORE_RELATIONS_ALREADY_PRESENT', 'fact_indexes': list(range(34)),
         'manual_judgment': 'All eleven current nominees/tenures, ten named independent '
             'directors, four standing committees and all nineteen positive member '
             'relations, Audit expert status, three-committee independence, Board '
             'Chair/Vice Chair, Allen/Jones appointments, Boulet departure and NCG '
             'rotation are present. Do not describe these supported relations as missing. '
             'This finding does not waive the separate future-term and source-time limits.'},
        {'kind': 'EXISTING_SUBCOMMITTEE_OMITTED', 'fact_indexes': [22, 28],
         'source_blocks': [957, 967, 972],
         'manual_judgment': 'The source says Risk and Security oversees classified '
             'activities and facilities through a subcommittee. This is an actual '
             'subcommittee relation inside a responsibilities passage, not merely '
             'permission to create one. Neither the old facts nor unresolved entries '
             'retain it. A future complete extraction should preserve existence and '
             'leave its unnamed members/Chair unresolved; do not invent a fifth '
             'standing committee or rewrite the old answer for credit.'},
        {'kind': 'PROSPECTIVE_TERM_AND_COUNT', 'fact_indexes': [0, 1, 2],
         'source_blocks': [259, 452, 453, 2756],
         'manual_judgment': 'Eleven current nominees are supported. Future terms '
             'require election and retain the elected-and-qualified successor '
             'condition; the immediately-following-meeting eleven count is explicitly '
             'prospective. Neither becomes an inferred December 31, 2021 snapshot.'},
        {'kind': 'ISSUER_ASSESSMENTS_POLICY_PENDING', 'fact_indexes': [],
         'source_blocks': [470, 471, 479, 494, 518, 547, 582, 609, 640, 679,
                           712, 748, 777, 805, 840],
         'manual_judgment': 'The source contains named expertise/role assessments '
             'and a skills matrix, beyond the Audit financial-expert determination '
             'already present. The #28 role/qualification evaluation boundary remains '
             'pending; retain their source statements without either automatic '
             'acceptance or counting them as confirmed old defects.'},
        {'kind': 'ACTUAL_STANDARDS_AND_BODY_SCOPE', 'fact_indexes': [16, 24, 26, 29],
         'source_blocks': [259, 427, 888, 891, 922, 976, 1181, 2655, 2870, 4730],
         'manual_judgment': 'Independence standards SEC/NYSE/Corporate Governance '
             'Guidelines are explicit. Audit financial-expert wording is exact '
             'without adding an unstated distinct regulatory attribution. HRCC '
             'non-employee determination also covers subsidiaries; the old shorter '
             'Company-only statement is not the complete clause. Appendix '
             'Compensation Committee naming is observed in equity-plan mechanics, '
             'which the task excludes as composition facts; do not count it as a '
             'second HRCC or automatically as a missing fifth committee. Other '
             'issuer boards, management councils, adviser/auditor independence and '
             'pension qualification remain separate.'},
        {'kind': 'KNOWN_UNRESOLVED_AND_METHOD_LIMITS', 'fact_indexes': [],
         'source_blocks': [471, 1047, 972],
         'manual_judgment': 'The old answer already preserves unnamed retirements '
             'and unidentified NCG rotation predecessors/successors. Keep both. '
             'Two old unresolved entries do not cover the omitted subcommittee '
             'roster, all media or qualification policy. Original complete request '
             'exceeds the fixed context limit; two whole-table responsibility '
             'inputs remain unvalidated independently and unwired.'},
    ]
    receipt = {
        'record_type': 'ISSUE47_LUMEN_FULL_REFERENCE_OLD_DEVELOPMENT_ANSWER_COMPARISON',
        'position': 'lumen_technologies:2021-12-31',
        'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        'old_answer_sha256': hashlib.sha256(args.answer.read_bytes()).hexdigest(),
        'bound_old_facts': bound, 'old_unresolved': answer['unresolved'],
        'manual_findings': findings,
        'citation_location_count': sum(len(f['source_blocks']) for f in answer['facts']),
        'all_old_citation_indexes_present': True, 'old_answer_modified': False,
        'qualification_policy_pending': True,
        'full_metric_acceptance': 'NOT_GRANTED_BY_THIS_COMPARISON',
        'existing_result_acceptance_changed': False,
        'new_model_execution': False, 'new_runs': 0, 'new_acceptances': 0,
        'calls': [0, 0, 0],
    }
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'old_facts': 34, 'citation_locations': receipt['citation_location_count'],
                      'manual_findings': len(findings),
                      'specific_existing_subcommittee_omissions': 1, 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
