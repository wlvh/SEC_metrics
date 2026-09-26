import importlib.util,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
import vnext
stage=Path('/tmp/sec_metrics_issue28_continuous/optional-prior-html')
for name in ['normal_source_requirements','ordinary_refresh_cycle']:
 spec=importlib.util.spec_from_file_location('vnext.'+name,stage/'scripts/vnext'/f'{name}.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;setattr(vnext,name,m);spec.loader.exec_module(m)
from vnext.normal_source_requirements import discover_saved_source_requirements
from vnext.ordinary_refresh_cycle import _pending
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 d=discover_saved_source_requirements(repo_root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs'),company_id='southwest_airlines')
 assert d['status']=='SAVED_SOURCE_DEPENDENCIES_AVAILABLE',d['status']
 assert len(d['missing_or_failed_source_urls'])==1 and d['unresolved_dependency_urls']==[]
 assert not d['all_39_metric_source_acceptance_proven'] and not d['current_sec_freshness_proven']
 pending=_pending(d,set(),set());assert len(pending)==2 and all(r['refresh_for_new_discovery']for r in pending)
 assert _pending(d,{r['source_url']for r in pending},set())==[]
 result={'discovery':d,'refresh_pending_metadata_urls':[r['source_url']for r in pending],'new_sec_calls':0,'seconds':time.monotonic()-start,'test_scope':'Full current saved-source discovery and refresh selector, not executed SEC refresh or metric Run'}
 (stage/'full-discovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print('PASS',result['seconds'],flush=True)
