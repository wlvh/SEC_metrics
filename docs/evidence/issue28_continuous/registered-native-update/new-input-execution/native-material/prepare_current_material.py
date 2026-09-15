"""Synthetic FY2026 material through real recorded SEC acquisition; no network."""
from pathlib import Path
from copy import deepcopy
import json,socket,time
from unittest.mock import patch
from vnext.canonical import canonical_json_bytes,sha256_file
from vnext.normal_source_authority import ROOT
from vnext.continuous_sec_acquisition import recorded_sec_session
from tests.vnext.test_text_coverage import annual
root=Path('/tmp/sec_metrics_issue28_continuous/native-refresh-execution/material-current-d04-fy2026').resolve();root.mkdir(exist_ok=False)
old=json.loads(Path('/tmp/sec_metrics_issue28_continuous/b13-scope-native-current/ledger/calls/0001/source.json').read_text())
p=next(p for p in old['source_proofs']if '/submissions/'in p['source_url']);metadata=json.loads((ROOT/p['request_repo_relative_path']).read_text());block=metadata['filings']['recent'];i=block['accessionNumber'].index(old['prepared_annual_input']['filing']['accessionNumber'])
filing={k:v[i]for k,v in block.items()};filing.update(accessionNumber='0001463101-27-900001',primaryDocument='synthetic-enph-20261231.htm',reportDate='2026-12-31',filingDate='2027-02-17',acceptanceDateTime='2027-02-17T18:00:00.000Z')
for k,v in block.items():v.insert(0,filing[k])
raw=annual('<h2>Item 1. Business</h2><p>This entire document is a synthetic annual report used only for a recorded software test.</p><h2>Item 8. Financial Statements</h2><p>Revenue is recognized when services are delivered.</p><h2>Item 9. Changes in Accountants</h2><p>There were no changes.</p>',cik='1463101',period='2026-12-31').replace(b'2025-01-01',b'2026-01-01').replace(b'2025-12-31',b'2026-12-31')
extra=''.join('<ix:nonNumeric name="dei:'+k+'" contextRef="annual">'+v+'</ix:nonNumeric>'for k,v in [('DocumentFiscalYearFocus','2026'),('DocumentFiscalPeriodFocus','FY'),('AmendmentFlag','false'),('EntityRegistrantName','Enphase Energy, Inc.')]).encode();raw=raw.replace(b'</ix:hidden>',extra+b'</ix:hidden>')
url='https://www.sec.gov/Archives/edgar/data/1463101/'+filing['accessionNumber'].replace('-','')+'/'+filing['primaryDocument']
(root/'synthetic-metadata.json').write_bytes(canonical_json_bytes(value=metadata));(root/'synthetic-annual.htm').write_bytes(raw)
report={'company_id':'enphase_energy','synthetic_fiscal_year':2026,'filing':filing,'synthetic_primary_url':url,'provider_paid_sec_real_calls':[0,0,0],'original_source_packet_sha256':sha256_file(path=Path('/tmp/sec_metrics_issue28_continuous/b13-scope-native-current/ledger/calls/0001/source.json')),'source_scope':'Explicit complete tiny synthetic annual document; original full FY2025 filing and saved metadata retained in baseline, not shortened or replaced as real evidence'}
started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 session=recorded_sec_session(root=root/'ledger',response=canonical_json_bytes(value=metadata))
 r=session.capture(company_id='enphase_energy',url=p['source_url'],refresh_metadata=True);report['metadata_capture']=r;assert r['status']=='SUCCEEDED';print('METADATA_SUCCEEDED',flush=True)
 session.response=raw;r=session.capture(company_id='enphase_energy',url=url);report['annual_capture']=r;assert r['status']=='SUCCEEDED';print('ANNUAL_SUCCEEDED',flush=True)
 with session.ledger.locked():report['recorded_ledger_counts']=session.ledger.snapshot()['counts']
report['seconds']=time.monotonic()-started;(root/'prepared.json').write_text(json.dumps(report,indent=2)+'\n');print('PREPARED',report['seconds'],flush=True)
