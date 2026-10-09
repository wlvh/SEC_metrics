from pathlib import Path
import sys,json,socket
from unittest.mock import patch
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext.normal_governance_input import _Sources
from sec_urls import submissions_url
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.ordinary_source_authority import verify_ordinary_source_proofs
url=submissions_url(cik=19617)
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC_SOCKET')):
 source=_Sources(R,'jpmorgan_chase','19617').read(url,role='sec_submissions_inventory',media_type='application/json')
 session=recorded_sec_session(root=Path('/private/tmp/sec_metrics_issue28_continuous/sec-recorded-first'),response=source['raw_bytes'])
 result=session.capture(company_id='jpmorgan_chase',url=url,refresh_metadata=True)
 proof=result['receipt']['proof'];admission=verify_ordinary_source_proofs(data_root=session.data_root,proofs=[proof])
 assert admission['source_credit']=='RECORDED_TEST_ONLY' and admission['real_sec_credit'] is False
 assert result['calls']==[0,0,0]
 print(json.dumps({'status':result['status'],'source_credit':admission['source_credit'],'checkpoint_id':result['checkpoint_id'],'calls':result['calls']}))
