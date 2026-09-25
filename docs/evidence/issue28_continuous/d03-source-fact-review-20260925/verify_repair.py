"""Recheck the old positive identity and the scoped post-action negatives."""
import json
from pathlib import Path

from vnext.regulatory_statement_facts import aggregate_involvement_facts, check_aggregate_classification


root = Path(__file__).resolve().parents[1]
saved = json.loads((root/'resume-2026-09-14/d03-source-fact-final.json').read_text())['source_fact']
statement = saved['statement_text']
positive = aggregate_involvement_facts(text=statement,
    aliases=[saved['subject_binding']])
assert len(positive) == 1 and positive[0]['status'] == 'SOURCE_REPORTED_FACT'
assert positive[0]['fact_id'] == saved['fact_id']
base = 'We are involved in various legal matters, including investigations by governmental authorities'
aliases = [{'text':'We','basis':'SOURCE_AUTHOR_FIRST_PERSON','support':None}]
endings = [', all of which were completed in 2020',
           ', all of which have concluded', ' that can arise in the future',
           ' that are hypothetical', ', none of which involve us']
rows = []
for ending in endings:
    facts = aggregate_involvement_facts(text=base+ending+'.', aliases=aliases)
    assert len(facts) == 1 and facts[0]['status'] == 'SEMANTIC_REVIEW_REQUIRED'
    assert 'ACTION_SCOPE_REQUIRES_INTERPRETATION' in facts[0]['reason_codes']
    assert check_aggregate_classification(facts=facts,
        kind='HISTORICAL_STATEMENT', reported_status='UNRESOLVED') == []
    rows.append({'ending':ending,'status':facts[0]['status'],
                 'reason_codes':facts[0]['reason_codes']})
summary = {'record_type':'ISSUE28_D03_POST_ACTION_SCOPE_REPAIR_CHECK',
    'jpm_existing_positive_fact_id':saved['fact_id'],
    'jpm_positive_identity_unchanged':True, 'negative_post_action_cases':rows,
    'model_or_sec_calls':[0,0,0], 'source_fact_is_not_native_result':True}
(Path(__file__).with_name('repair-boundary.json')).write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'jpm_positive_identity_unchanged':True,
                  'negative_cases':len(rows),'new_calls':[0,0,0]}))
