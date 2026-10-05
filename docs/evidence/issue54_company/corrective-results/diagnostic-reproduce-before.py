import json, sys, tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=['/workspace/work/sec-company-compute','/workspace/work/sec-company-compute/scripts']
from scripts.vnext import company_compute as c
@contextmanager
def locked(root):
 yield root
with tempfile.TemporaryDirectory() as d:
 r=Path(d)
 def run(**kw):return {'metrics':[{'metric_id':m,'status':'CANDIDATE_READY'} for m in kw['metric_ids']]}
 with patch.object(c,'locked_company',locked),patch.object(c,'recover_import',return_value={'company_id':'test'}),patch.object(c,'require_company',return_value={'checkpoint_id':'source-v1','metric_ids':['B01','D01']}),patch('scripts.vnext.ordinary_d02_category_update_v2.run_company',side_effect=run):
  c.compute_company(state_root=r,company_id='test',metric_ids=['B01','D01'])
  first=json.loads((r/'company-results.json').read_text())
  c.compute_company(state_root=r,company_id='test',metric_ids=['B01'])
  second=json.loads((r/'company-results.json').read_text())
 print(json.dumps({'scope':'ORCHESTRATION_MOCK_ONLY','first':[m['metric_id'] for m in first['metrics']],'partial_update':[m['metric_id'] for m in second['metrics']],'new_business_calls':[0,0,0]},indent=2))
 assert {m['metric_id'] for m in second['metrics']}=={'B01','D01'},'PARTIAL_UPDATE_DROPS_PREVIOUS_METRIC'
