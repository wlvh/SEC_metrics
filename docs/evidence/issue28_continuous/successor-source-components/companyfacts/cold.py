import json,sys
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[1]+"/scripts"]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_companyfacts_results import verify_ordinary_companyfacts_metrics
with original_sources_only():
 result=verify_ordinary_companyfacts_metrics(candidate=json.loads(Path(sys.argv[2]).read_text()),repo_root=Path(sys.argv[3]),company_id=sys.argv[4])
 print(json.dumps({"component_id":result["component_id"],"metric_count":len(result["metrics"]),"calls":result["calls"],"status":"REBUILT_FROM_SAVED_SOURCE"}))
