from pathlib import Path
from copy import deepcopy
import json,socket
from unittest.mock import patch
from vnext.normal_source_authority import ROOT
from vnext.canonical import canonical_json_bytes,strict_json_loads
from vnext.continuous_sec_acquisition import recorded_sec_session
root=Path('/tmp/sec_metrics_issue28_continuous/native-refresh-execution/material-current-d04-fy2026').resolve()
old=json.loads(Path('/tmp/sec_metrics_issue28_continuous/b13-scope-native-current/ledger/calls/0001/source.json').read_text());p=next(p for p in old['source_proofs']if '/companyfacts/'in p['source_url']);facts=strict_json_loads(text=(ROOT/p['request_repo_relative_path']).read_text())
rows=facts['facts']['us-gaap']['Assets']['units']['USD'];row=deepcopy(rows[-1]);row.update(accn='0001463101-27-900001',fy=2026,fp='FY',form='10-K',filed='2027-02-17',end='2026-12-31',val=100);row.pop('frame',None);row.pop('start',None);rows.append(row)
(root/'synthetic-companyfacts.json').write_bytes(canonical_json_bytes(value=facts))
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 session=recorded_sec_session(root=root/'ledger',response=canonical_json_bytes(value=facts));r=session.capture(company_id='enphase_energy',url=p['source_url'],refresh_metadata=True);assert r['status']=='SUCCEEDED';(root/'companyfacts-capture.json').write_text(json.dumps(r,indent=2)+'\n');print('SYNTHETIC_SAME_ACCESSION_FACTS_ADMITTED',flush=True)
