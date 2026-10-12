import contextlib,io,json,socket
from pathlib import Path
from unittest.mock import patch
from tests.vnext.test_company_fiscal_range import CompanyFiscalRangeTest,COMPANY,CIK
from tools.vnext_company import main
from sec_urls import companyfacts_url
out=Path('work/history-source-continuation')
for kind in ('latest503','missing-primary','missing-companyfacts'):
 fixture=CompanyFiscalRangeTest();fixture.setUp()
 try:
  url=companyfacts_url(cik=CIK) if kind=='missing-companyfacts' else fixture.fixture.urls[2024]
  if kind=='latest503':fixture.fixture.record(url,b'Unavailable',status=503,error='constructed HTTP503')
  else:fixture.fixture.remove_get(url)
  before=fixture.fixture.digest_tree()
  with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_REAL_NETWORK')),contextlib.redirect_stdout(io.StringIO()) as stream:
   code=main(['sources','--company',COMPANY,'--source-root',str(fixture.source),'--fiscal-year-start','2024','--fiscal-year-end','2025','--metric','B01'])
  assert before==fixture.fixture.digest_tree();data=json.loads(stream.getvalue());assert code==2 and data['status']=='FISCAL_RANGE_UNRESOLVED'
  record={'kind':kind,'fixture':'explicit constructed saved HTTP/ledger in isolated temporary test root','expected_pending_url':url,'output_exposes_pending_url':url in stream.getvalue(),'exit_code':code,'result':data,'real_calls':[0,0,0]}
  (out/(kind+'.json')).write_text(json.dumps(record,indent=2)+'\n')
  print(kind,code,record['output_exposes_pending_url'],flush=True)
 finally:fixture.doCleanups()
# Reuse the already executed real noncalendar source/package consumer; no original rereading.
source=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/salesforce-history-export-consumer-20261013/summary.json')
d=json.loads(source.read_text());row=d['row']
assert d['export']['fiscal_years']==[2022,2023,2024,2025,2026]
assert (row['fiscal_year'],row['period_start'],row['period_end'])==('2026','2025-02-01','2026-01-31')
positive={'kind':'existing real noncalendar source positive','existing_record':'13fb333b4412cc9664d423403a5fdd538e1d3f95','fiscal_years':d['export']['fiscal_years'],'actual_period':[row['period_start'],row['period_end']],'issuer_fiscal_year':2026,'original_dei_label':2025,'replayed':False,'old_result_id':row['result_id'],'real_calls':[0,0,0]}
(out/'noncalendar-existing-positive.json').write_text(json.dumps(positive,indent=2)+'\n')
print('noncalendar existing positive reused',flush=True)
