"""Time the exact existing D03 native material class; never replace checks."""
import json
from pathlib import Path
import sys,time,unittest
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from tests.vnext import test_d03_native_assessment as tests
from vnext import continuous_semantic_calls as calls, native_assessment_replay as replay, d03_native_assessment as native, r6_regulatory_semantics as semantics
from vnext import regulatory_fact_review as review
EVENTS=[]
def wrap(module,name,label,aliases=()):
 old=getattr(module,name)
 def run(*args,**kwargs):
  start=time.perf_counter()
  try:return old(*args,**kwargs)
  finally:EVENTS.append({'label':label,'seconds':round(time.perf_counter()-start,3)})
 setattr(module,name,run)
 for m,n in aliases:setattr(m,n,run)
wrap(semantics,'prepare_regulatory_semantic_source','source_rebuild')
wrap(semantics,'requests_from_source','request_grouping')
wrap(review,'candidate_request','candidate_request')
wrap(calls,'prepare_d03_replay_only_requests','prepare_factory',[(tests,'prepare_d03_replay_only_requests')])
wrap(calls,'execute_d03_recorded_assessment','recorded_execute',[(tests,'execute_d03_recorded_assessment')])
wrap(replay,'replay_native_response','independent_native_replay',[(tests,'replay_native_response')])
wrap(native,'collect_recorded_assessments','collection',[(tests,'collect_recorded_assessments')])
start=time.perf_counter();out=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.D03NativeAssessmentTest))
by={}
for event in EVENTS:
 row=by.setdefault(event['label'],{'count':0,'inclusive_seconds':0.0});row['count']+=1;row['inclusive_seconds']+=event['seconds']
summary={'status':'PASS' if out.wasSuccessful() else 'FAILED','wall_seconds':round(time.perf_counter()-start,3),'tests':out.testsRun,'events':EVENTS,'by_label':by,'inclusive_times_overlap':True,'source':'EXACT_CURRENT_SAVED_MARRIOTT_ORIGINAL','new_business_calls':[0,0,0]}
(HERE/'timing-before.json').write_text(json.dumps(summary,indent=2)+'\n');(HERE/'done-before.json').write_text(json.dumps({'status':summary['status']})+'\n');print(json.dumps({'status':summary['status'],'wall_seconds':summary['wall_seconds'],'by_label':by}));raise SystemExit(0 if out.wasSuccessful() else 1)
