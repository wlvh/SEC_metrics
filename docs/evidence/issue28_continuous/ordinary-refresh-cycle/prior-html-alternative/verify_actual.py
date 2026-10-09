import hashlib,importlib.util,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
import vnext
root=Path('/Users/lyuhongwang/Developer/SEC_metrics');stage=Path('/tmp/sec_metrics_issue28_continuous/optional-prior-html')
for name in ['normal_source_requirements','ordinary_refresh_cycle']:
 spec=importlib.util.spec_from_file_location('vnext.'+name,stage/'scripts/vnext'/f'{name}.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;setattr(vnext,name,m);spec.loader.exec_module(m)
from vnext.normal_source_requirements import _Requirements,_satisfy_prior_primary_alternatives,_instance_names,source_dependency_satisfied
from vnext.ordinary_refresh_cycle import _pending
from vnext.normal_annual_input import _registry_rows
from sec_urls import accession_directory_url,accession_document_url
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
ev=root/'docs/evidence/issue28_continuous/d04-indexed-unit-response/remaining-call-tail'
prior=json.loads((ev/'prior-html-with-auditor.json').read_text());d=json.loads((ev/'sec-discovery.json').read_text());companies={r['company_id']:r for r in _registry_rows(repo_root=root)};periods={r['company_id']:r['source_period']for r in d['companies']}
watch=d['source_snapshot_before'].keys();before={p:hashlib.sha256((base/p).read_bytes()).hexdigest()for p in watch};rows=[];start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 for row in prior['rows']:
  cid=row['company_id'];company=companies[cid];cik=company['primary_cik'];filing=row['filing'];acc=filing['accessionNumber'];plan=_Requirements(base,company)
  plan.require(row['missing_html_url'],'prior_annual_primary','text/html',acc)
  directory=plan.require(accession_directory_url(cik=int(cik),accession=acc),'annual_accession_index','application/json',acc)
  for name in _instance_names(json.loads(directory['raw_bytes']),company,filing):
   plan.require(accession_document_url(cik=int(cik),accession=acc,document_name=name),'annual_accession_instance','application/xml',acc)
  prepared={'entity':cik,'table_input':{'target_period':periods[cid]}}
  _satisfy_prior_primary_alternatives(plan,prepared,{'prior_filing_chain':[filing]})
  item=plan.requests[row['missing_html_url']]
  assert item['saved_status']=='MISSING_SAVED_SOURCE' and source_dependency_satisfied(item),item
  assert _pending({'requirements':list(plan.requests.values())},set(),set())==[]
  rows.append({'company_id':cid,'requirement':item,'declared_requirements':list(plan.requests.values())})
  print(cid,item['alternative_dependency']['status'],flush=True)
after={p:hashlib.sha256((base/p).read_bytes()).hexdigest()for p in watch};assert before==after
result={'stage_runtime_sha256':{p:hashlib.sha256((stage/p).read_bytes()).hexdigest()for p in ['scripts/vnext/normal_source_requirements.py','scripts/vnext/ordinary_refresh_cycle.py']},'rows':rows,'source_snapshot_before':before,'source_snapshot_after':after,'calls':[0,0,0],'network_forbidden':True,'seconds':time.monotonic()-start,'runtime_patch_applied':False,'all_39_acceptance':False}
(stage/'actual-six.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('PASS',result['seconds'],flush=True)
