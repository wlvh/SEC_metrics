import json,os,pathlib,socket,sys,time
from unittest.mock import patch
program=pathlib.Path(sys.argv[1]); root=pathlib.Path(sys.argv[2]);sys.path[:0]=[str(program),str(program/'scripts')]
os.environ['SEC_METRICS_ACQUISITION_TRUST_ROOT']=str(root/'trust')
from vnext.company_local_acquisition import local_session
from vnext.continuous_sec_acquisition import initialize_source_inputs,validate_acquisition_checkpoint
from vnext.normal_source_authority import ROOT,MANIFEST_PATH
from vnext.canonical import strict_json_file
from sec_http import parse_request_log_rows
response=json.dumps({'cik':'1048286','filings':{'files':[],'recent':{k:[] for k in ['form','reportDate','filingDate','accessionNumber','primaryDocument']}}}).encode()
session=local_session(root=root/'ledger',company_id='marriott_international',allowance=3,response=response)
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
 with session.ledger.locked():
  initialize_source_inputs(root=session.data_root,requirement=session.requirement)
  assert parse_request_log_rows(text=(session.data_root/'evidence/requests_log.csv').read_text())==[]
  assert sorted(p.relative_to(session.data_root/'evidence').as_posix() for p in (session.data_root/'evidence').rglob('*') if p.is_file())==['requests_log.csv','requests_log_manifest.json']
 start=time.monotonic()
 result=session.capture(company_id='marriott_international',url='https://data.sec.gov/submissions/CIK0001048286.json',refresh_metadata=True)
 checkpoint=strict_json_file(path=root/'trust'/(result['receipt']['ledger_after_sha256']+'.json'))
 validate_acquisition_checkpoint(session.data_root,checkpoint,strict_json_file(path=ROOT/MANIFEST_PATH))
 assert result['receipt']['execution_mode']=='RECORDED_TEST_ONLY' and result['calls']==[0,0,0]
 raw=(session.data_root/'evidence/requests_log.csv').read_bytes()
 try: session.capture(company_id='enphase_energy',url='https://data.sec.gov/submissions/CIK0001463101.json')
 except ValueError as err: assert str(err)=='LOCAL_ACQUISITION_COMPANY_OR_HISTORY_SCOPE_CHANGED'
 else: raise AssertionError('wrong company admitted')
 assert raw==(session.data_root/'evidence/requests_log.csv').read_bytes()
 header=session.data_root/result['receipt']['proof']['request_headers_repo_relative_path']
 original=header.read_bytes(); header.write_bytes(b'{}')
 try: validate_acquisition_checkpoint(session.data_root,checkpoint,strict_json_file(path=ROOT/MANIFEST_PATH))
 except Exception as err:
  assert 'Request-ledger locator evidence is invalid' in str(err)
  assert 'headers hash mismatch' in str(err.__cause__)
 else: raise AssertionError('bound header tamper admitted')
 header.write_bytes(original)
 try:
  live=local_session(root=root/'ledger',company_id='marriott_international',allowance=3)
  with live.ledger.locked():pass
 except ValueError as err: assert 'INITIALIZATION_ANCHOR_CHANGED' in str(err)
 else: raise AssertionError('recorded converted to LIVE')
print(json.dumps({'status':'PASS','seconds':round(time.monotonic()-start,3),'calls':[0,0,0],'mode':'RECORDED_TEST_ONLY','empty_financial_sources':True,'wrong_company_rejected':True,'bound_header_rejected':True,'recorded_to_live_rejected':True,'receipt':result['receipt']['receipt_id']}))
