"""Independent-process actual source read; no provider or semantic credit."""
import hashlib
import json
import socket
import subprocess
import time
from pathlib import Path
from vnext import c02_image_model_processing as m
from vnext.review import _system_approved_claims

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent

def blocked(*a,**k):raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')

def main():
    saved=json.loads((HERE/'actual-save.json').read_text())
    folder=Path(saved['processing_root'])
    before={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}
    socket.socket=blocked;socket.create_connection=blocked;subprocess.Popen=blocked
    started=time.monotonic()
    out=m.read_image_development_assessment(directory=folder,data_root=ROOT,company_id='jpmorgan_chase',
        expected_candidate_hash=saved['candidate_hash'],expected_review_unit_hash=saved['review_unit_hash'])
    elapsed=round(time.monotonic()-started,3)
    after={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in folder.rglob('*') if p.is_file()}
    assert before==after
    assert hashlib.sha256(out['request_body']).hexdigest()==saved['request_sha256']
    assert hashlib.sha256(out['response_body']).hexdigest()==saved['response_sha256']
    assert len(out['processing']['original_image_markup'])==604
    assert out['processing']['model_facts_and_unresolved']==json.loads(out['response_body'])
    context=json.loads(out['review_context_bytes'])
    assert len(context['source_linked_review']['entries'])==53
    assert context['processing']['original_image_markup']==out['processing']['original_image_markup']
    for unit in out['records'][4:]:
        assert unit['status']=='PENDING' and not unit['system_approval_eligible']
        try:_system_approved_claims(review_unit=unit)
        except ValueError:pass
        else:raise AssertionError('SYSTEM_NOT_REFUSED')
    assert not any(out[k] for k in ('native_result_created','native_run_created','provider_attempt_created'))
    record={'action':'ACTUAL_SEPARATE_PROCESS_EMPTY_CWD_NO_NETWORK_NO_SUBPROCESS_READ',
       'code_root':str(ROOT),'source_data_root':str(ROOT),'processing_root':str(folder),
       'read_seconds':elapsed,'candidate_hash':saved['candidate_hash'],
       'review_unit_hash':saved['review_unit_hash'],'saved_files_sha256':after,
       'raw_request_response_preserved':True,'all_model_entries_and_unresolved_preserved':True,
       'images_in_pending_context':604,'records_pending_system_refused':True,
       'new_native_result_run_or_provider':False,'business_calls':[0,0,0]}
    (HERE/'actual-read.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))

if __name__=='__main__':main()
