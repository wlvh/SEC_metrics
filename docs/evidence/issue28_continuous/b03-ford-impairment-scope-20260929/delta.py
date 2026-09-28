"""Record one Ford B03 current-credit correction without rewriting 390 history."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.b03_depreciation_scope import assess_direct_depreciation_scope
from vnext.normal_run_v3 import prepare_case

parent = 'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
index = json.loads((ROOT/parent).read_text())
rows = [row for row in index['rows'] if row['company_id'] ==
        'ford_motor_company' and row['metric_id'] == 'B03']
assert len(rows) == 1
row = rows[0]
case = prepare_case(data_root=ROOT, company_id='ford_motor_company',
                    metric_id='B03')
result = case['results']['B03']
assert row['implementation_identity']['result_id'] == result['result_id']
assert row['value'] == result['value'] and result['publication'] == 'PUBLISHED'
scope = assess_direct_depreciation_scope(case=case, data_root=ROOT)
assert scope['blocked'] and scope['status'] == \
    'SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT'
body = {'record_type':'ISSUE28_CURRENT_390_ONE_COORDINATE_SCOPE_DELTA',
    'parent_index':parent,
    'preceding_distinct_coordinate_delta':
        'docs/evidence/issue28_continuous/b03-current-scope-20260928/delta.json',
    'coordinate_key':'ford_motor_company:B03',
    'historical_result_id_retained':result['result_id'],
    'historical_value_retained':result['value'],
    'historical_publication_record_retained':True,
    'current_business_credit':'REVOKED_PENDING_IMPAIRMENT_FREE_DEPRECIATION_SCOPE',
    'source_scope':scope,
    'approximate_8_1_billion_subtraction_used':False,
    'new_complete_coordinate_count':0,
    'other_389_revalidated':False,
    'all390_acceptance':False,
    'production_authorized':False,
    'new_provider_paid_sec_calls':[0,0,0]}
path = Path(__file__).with_name('delta.json')
path.write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'coordinate':body['coordinate_key'],
                  'result_id':result['result_id'],
                  'old_value':result['value'],
                  'scope_status':scope['status'],
                  'footnote_sha256':scope['impairment_inclusion_proof'][
                      'footnote']['span_sha256'],
                  'new_real_calls':[0,0,0]},sort_keys=True))
