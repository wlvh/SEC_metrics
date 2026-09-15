import json,hashlib,socket
from pathlib import Path
from unittest.mock import patch
from vnext.normal_source_authority import ROOT
from vnext.normal_governance_input import _Sources,_filings
from vnext.normal_annual_input import _registry_rows,annual_period
from vnext.canonical import strict_json_loads
from sec_urls import submissions_url
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs');out=Path('/tmp/sec_metrics_issue28_continuous/remaining-call-tail')
d=json.loads((out/'sec-discovery.json').read_text());registry={r['company_id']:r for r in _registry_rows(repo_root=ROOT)}
rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 for company in d['companies']:
  missing=[r for r in company['requirements']if r['bucket']=='KNOWN_MISSING_DECLARED_DEPENDENCY']
  for need in missing:
   cid=company['company_id'];cik=registry[cid]['primary_cik'];reader=_Sources(base,cid,cik)
   try:
    assert need['roles']==['prior_annual_primary']
    inv=reader.read(submissions_url(cik=int(cik)),role='sec_submissions_inventory',media_type='application/json')
    filings=_filings(strict_json_loads(text=inv['raw_bytes'].decode()),inventory_name=inv['source_reference']['document_name'])
    chosen=[f for f in filings if f['accessionNumber']==need['accession']]
    assert len(chosen)==1
    native=reader.auditor_filing(chosen[0])
    periods=[annual_period(raw=s['raw_bytes'],cik=cik,filing=chosen[0])for s in native]
    assert periods and all(p==periods[0]for p in periods)
    from datetime import date,timedelta
    assert date.fromisoformat(periods[0]['period_end'])+timedelta(days=1)==date.fromisoformat(company['source_period']['period_start'])
    assert reader.file_sets[-1]['primary_saved'] is False
    from vnext.governance_signals import _auditor_filing
    auditor=_auditor_filing(sources=native,company_id=cid,cik=cik,period_end=periods[0]['period_end'])
    assert auditor['status']=='FOUND'
    rows.append({'company_id':cid,'missing_html_url':need['source_url'],'classification':'OPTIONAL_PRIOR_HTML_WITH_VERIFIED_NATIVE_INSTANCE_ALTERNATIVE',
     'existing_route':'normal_governance_input._Sources.auditor_filing; normal_companyfacts_results prior-period fallback',
     'source_period':periods[0],'filing':chosen[0],'prior_auditor_fact_status':auditor['status'],'prior_auditor_fact_count':len(auditor['facts']),
     'verified_native_sources':[{'source_reference_id':s['source_reference']['source_reference_id'],'source_url':s['source_reference']['source_url'],'raw_sha256':hashlib.sha256(s['raw_bytes']).hexdigest()}for s in native],
     'file_set':reader.file_sets[-1],'scope':'Native accession identity/annual period, actual prior auditor DEI facts and optional-HTML branch; not a new metric Run','new_sec_calls_required_for_this_alternative':0})
   except Exception as e:rows.append({'company_id':cid,'missing_html_url':need['source_url'],'classification':'ALTERNATIVE_NOT_ESTABLISHED','error_type':type(e).__name__,'reason':str(e)})
   print(cid,rows[-1]['classification'],rows[-1].get('reason',''),flush=True)
assert all(hashlib.sha256((base/p).read_bytes()).hexdigest()==sha for p,sha in d['source_snapshot_before'].items())
(out/'prior-html-alternatives.json').write_text(json.dumps({'rows':rows,'source_snapshot_unchanged':True,'no_network':True,'calls':[0,0,0]},ensure_ascii=False,indent=2)+'\n')
