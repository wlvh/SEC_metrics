import sys,json
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[1]+"/scripts"]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_accession_results import verify_ordinary_accession_metrics
with original_sources_only():
 r=verify_ordinary_accession_metrics(candidate=json.loads(Path(sys.argv[2]).read_text()),repo_root=Path(sys.argv[3]),company_id=sys.argv[4])
 print(json.dumps({"component_id":r["component_id"],"metric_count":len(r["metrics"]),"calls":r["calls"],"status":"REBUILT_FROM_SAVED_SOURCE"}))
