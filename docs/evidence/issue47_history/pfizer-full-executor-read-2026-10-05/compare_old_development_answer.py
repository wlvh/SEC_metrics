"""Bind old development citations and record manually assessed comparison.

Does not judge semantics automatically, edit the answer or create acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    for name in ('document','answer','reference','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    doc=json.loads(args.document.read_text());blocks={b['block_index']:b for b in doc['blocks']}
    answer=json.loads(args.answer.read_text());reference=json.loads(args.reference.read_text())
    assert reference['all_3511_supplied_text_blocks_read'] is True
    assert len(answer['facts'])==34
    bound=[]
    for i,fact in enumerate(answer['facts']):
        assert fact['source_blocks'] and all(type(index) is int and index in blocks for index in fact['source_blocks'])
        bound.append({'fact_index':i,'original_fact':fact,'source_blocks':[blocks[index] for index in fact['source_blocks']]})
    findings=[
        {'kind':'CORE_RELATIONS_ALREADY_PRESENT','fact_indexes':[0,1,2,3,6,7,8,9,10,11,12,13,14,15,16,19,20,21]+list(range(22,34)),
         'manual_judgment':'The old answer contains all12named director tenure entries, both leadership roles,11named independent directors, five principal committee rosters (21positive member relations), their independence, Audit financial-expert/literacy and Rule16b3 qualifications, and explicit2022/no-change and since2018 aggregates. Do not call these already supported core facts missing.'},
        {'kind':'FOUR_ISSUER_ASSESSMENTS_POLICY_PENDING','fact_indexes':[4,5,17,18],
         'manual_judgment':'Narayen role suitability, Bourla leadership/industry knowledge, criteria satisfaction/nominee skills, and Directors time/energy/Principles compliance have real source statements. Qualification acceptance remains unresolved under the #28 owner boundary; no automatic false classification or credit.'},
        {'kind':'CONDITIONAL_FUTURE_TERM','fact_indexes':[0],
         'source_blocks':[234,355],
         'manual_judgment':'The current twelve/standing-for-re-election facts are supported. The future-term shorthand should preserve if elected, successor qualification and earlier departure conditions from355. No election outcome is inferred or old answer corrected.'},
        {'kind':'NAMED_STANDARD_ATTRIBUTION','fact_indexes':[1,15,16],
         'manual_judgment':'The independence determination cites Pfizer Standards, whose401definition meets/exceedsNYSE. Audit821uses the exact AuditCommitteeFinancialExperts title; do not add an unstated separate SEC attribution merely from convention. Rule16b3 attribution is explicit838.'},
        {'kind':'SOURCE_TIME_AND_BODY_SCOPE','fact_indexes':[0,6,12,19,20,21],
         'source_blocks':[46,355,373,799,995,1000,1493,3123,3126,3140,3445,3510],
         'manual_judgment':'December31summary date is local, currentproxy roles differ from explicit2022historical statements. Five described principal Board committees are distinct from employee PAC/PCPC, managementSteering, congressional bodies and shareholder ProxyCommittee. Named proxies are not additional Board appointees.'},
        {'kind':'NO_ALL_MEDIA_OR_INDEPENDENT_METHOD_CREDIT','fact_indexes':[],
         'manual_judgment':'The old unresolved[] is not proof of complete skill/symbol/media understanding, qualification policy or independent input-only validity. This is an old development answer compared after a new complete executor reading, not a new model execution/holdout/accepted metric.'},
    ]
    receipt={'record_type':'ISSUE47_PFIZER_FULL_REFERENCE_OLD_DEVELOPMENT_ANSWER_COMPARISON',
             'position':'pfizer:2022-12-31',
             'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest(),
             'old_answer_sha256':hashlib.sha256(args.answer.read_bytes()).hexdigest(),
             'bound_old_facts':bound,'manual_findings':findings,
             'citation_location_count':sum(len(f['source_blocks']) for f in answer['facts']),
             'all_old_citation_indexes_present':True,'old_answer_modified':False,
             'qualification_policy_pending':True,'full_metric_acceptance':'NOT_GRANTED_BY_THIS_COMPARISON',
             'existing_result_acceptance_changed':False,
             'new_model_execution':False,'new_runs':0,'new_acceptances':0,'calls':[0,0,0]}
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'old_facts':34,'citation_locations':receipt['citation_location_count'],
                      'manual_findings':len(findings),'policy_pending_old_facts':4,'calls':[0,0,0]}))


if __name__=='__main__':main()
