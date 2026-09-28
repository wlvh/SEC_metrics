"""Recorded automatic metadata refresh from derived FY2024 to real FY2025."""
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode=True
REPO=Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0]=[str(REPO),str(REPO/'scripts'),
    str(REPO/'docs/evidence/issue28_continuous/c04-adjacent-year-rehearsal-20260927')]
from rehearse import saved_response,derived_prior_response
from sec_urls import submissions_url
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext import ordinary_refresh_cycle as refresh

ROOT=Path('/private/tmp/issue28-b01-crossyear-auto-20260928')
assert not ROOT.exists(), 'AUTO_ROOT_ALREADY_EXISTS'
ROOT.mkdir()
STATE=ROOT/'state'
URL=submissions_url(cik=1048286)
current,original_row=saved_response(URL)
prior,annual=derived_prior_response(current)
session=recorded_sec_session(root=ROOT/'ledger',response=prior)
started=time.monotonic()

def tree(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

def no_network(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')

out={'record_type':'ISSUE28_MARRIOTT_B01_DERIVED_OLD_METADATA_AUTO_REFRESH',
    'company_id':'marriott_international','metric_id':'B01',
    'original_current_submissions_repo_path':original_row['repo_relative_path'],
    'original_current_submissions_sha256':hashlib.sha256(current).hexdigest(),
    'derived_old_submissions_sha256':hashlib.sha256(prior).hexdigest(),
    'derived_old_metadata_is_authentic_SEC_response':False,
    'real_calls':[0,0,0], 'production_authorized':False}
try:
    with patch.object(socket.socket,'connect',side_effect=no_network), \
         patch.object(socket,'getaddrinfo',side_effect=no_network), \
         patch('sec_http.urlopen',side_effect=no_network):
        old_capture=session.capture(company_id='marriott_international',url=URL,
            refresh_metadata=True)
        first=refresh.refresh_and_process(session=session,state_root=STATE,
            company_ids=['marriott_international'],metric_ids=['B01'],
            max_sec_requests=0)
        company1,=first['companies']; metric1,=company1['updates']['metrics']
        history=STATE/'marriott_international/metrics/B01'
        old_pointer=json.loads((history/'current.json').read_text())
        old_id=old_pointer['successful_attempt']
        old_before=tree(history/'attempts'/old_id)
        out['old_step']={'capture_status':old_capture['status'],
            'report_status':first['status'],'metric_status':metric1['status'],
            'attempt_id':old_id,
            'result_id':metric1['last_verified_candidate']['results']['B01']['result_id']}
        session.response=current
        second=refresh.refresh_and_process(session=session,state_root=STATE,
            company_ids=['marriott_international'],metric_ids=['B01'],
            max_sec_requests=1)
    company2,=second['companies']; metric2,=company2['updates']['metrics']
    new_pointer=json.loads((history/'current.json').read_text())
    new_id=new_pointer['successful_attempt']
    with (history/'attempts'/old_id/'rows/B01/metrics_matrix.csv').open(newline='') as stream:
        old_row,=list(csv.DictReader(stream))
    with (history/'attempts'/new_id/'rows/B01/metrics_matrix.csv').open(newline='') as stream:
        new_row,=list(csv.DictReader(stream))
    out['new_step']={'report_status':second['status'],
        'source_refresh_status':company2['source_refresh']['status'],
        'metric_status':metric2['status'],'attempt_id':new_id,
        'result_id':metric2['last_verified_candidate']['results']['B01']['result_id'],
        'captures':[{'source_url':x['source_url'],'status':x['result']['status']}
            for x in second['captures']]}
    out['old_row']={k:old_row[k] for k in ('company','metric_id','value','unit',
        'status','fiscal_year','period_start','period_end','accession')}
    out['new_row']={k:new_row[k] for k in ('company','metric_id','value','unit',
        'status','fiscal_year','period_start','period_end','accession')}
    out['old_success_package_unchanged']=tree(history/'attempts'/old_id)==old_before
    out['new_intent_predecessor']=json.loads((history/'attempts'/new_id/
        'intent.json').read_text())['previous_successful_attempt']
    with session.ledger.locked():
        out['recorded_ledger_counts']=session.ledger.snapshot()['counts']
    out['recorded_first_body_sha256']=hashlib.sha256((ROOT/
        'ledger/calls/0001/sec-wire/body.bin').read_bytes()).hexdigest()
    out['recorded_second_body_sha256']=hashlib.sha256((ROOT/
        'ledger/calls/0002/sec-wire/body.bin').read_bytes()).hexdigest()
except Exception as error:
    out['exception']={'type':type(error).__name__,'reason':str(error)}
finally:
    out['seconds']=round(time.monotonic()-started,3)
    (ROOT/'result.json').write_text(json.dumps(out,ensure_ascii=False,
        indent=2,default=str)+'\n')
    print(json.dumps({k:out.get(k) for k in ('old_step','new_step','old_row',
        'new_row','old_success_package_unchanged','new_intent_predecessor',
        'recorded_ledger_counts','exception','seconds')},ensure_ascii=False),flush=True)
assert out['old_step']['metric_status']=='CANDIDATE_READY'
assert out['new_step']['metric_status']=='CANDIDATE_READY'
assert out['new_step']['captures']==[{'source_url':URL,'status':'SUCCEEDED'}]
assert out['old_row']['fiscal_year']=='2024' and out['new_row']['fiscal_year']=='2025'
assert out['old_success_package_unchanged']
assert out['new_intent_predecessor']==out['old_step']['attempt_id']
assert out['recorded_first_body_sha256']==out['derived_old_submissions_sha256']
assert out['recorded_second_body_sha256']==out['original_current_submissions_sha256']
assert out['recorded_ledger_counts']==[0,0,2]
