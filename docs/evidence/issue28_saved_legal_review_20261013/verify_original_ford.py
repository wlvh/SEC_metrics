"""Actual retained answer and a request rebuilt from original SEC bytes."""
import argparse
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import tarfile
import tempfile
import time
from unittest.mock import patch

from vnext import d02_text_results_v3 as core
from vnext.canonical import content_hash
from vnext.legal_review_contract import review_request
from vnext.saved_legal_review import read_saved_legal_review
from vnext.text_business_candidates import _substantive

OLD='bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786'
ARCHIVE='evidence/issue47_model_calls/9a368413797ddef1/model-ledger.tar.gz'
RECORD='docs/evidence/issue47_history/model-live-round-9a368413/d02/ford_motor_company-d02-2025-12-31/run-ford_motor_company-d02-2025-12-31-D02/records.jsonl'


def git_bytes(path):return subprocess.check_output(['git','show',OLD+':'+path])
def digest(raw):return hashlib.sha256(raw).hexdigest()


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();assert not args.receipt.exists()
    # Only source/blob metadata is used; no saved metric value is an operand.
    metadata=[]
    for line in git_bytes(RECORD).splitlines():
        row=json.loads(line)
        if row['record_type'] in ('SOURCE_REFERENCE','RAW_BLOB'):metadata.append(row)
    ref=next(r for r in metadata if r['record_type']=='SOURCE_REFERENCE' and r['source_role']=='target_primary')
    blob=next(r for r in metadata if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==ref['raw_asset_id'])
    raw_sha=blob['raw_asset_id'].split(':')[1]
    raw_path=args.source_root/'evidence/request_attempts'/raw_sha[:2]/raw_sha/ref['document_name']
    raw=raw_path.read_bytes();assert digest(raw)==raw_sha
    inventory_path=args.source_root/'evidence/request_attempts/2e/2e312b9a7c22fc6b22a4c68dc2b2924274426be1e672178d40428ff655fcae53/CIK0000037996.json'
    inventory=json.loads(inventory_path.read_bytes());recent=inventory['filings']['recent']
    index=recent['accessionNumber'].index(ref['accession']);filing={k:v[index] for k,v in recent.items()}
    protected=[raw_path,inventory_path,*[args.source_root/p for p in (
        'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')]]
    before={str(p):digest(p.read_bytes()) for p in protected}
    target={'company_id':'ford_motor_company','entity':'37996','accession':ref['accession'],
        'period_start':'2025-01-01','period_end':'2025-12-31','scope':core.SCOPES['D02']}
    target['scope_key']=content_hash(value=target['scope'])
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')))
        started=time.perf_counter()
        prepared=core.prepare_business_text_sources(metric_id='D02',target=target,
            source_references=[ref],raw_blobs={blob['raw_asset_id']:blob},
            raw_bytes_by_id={blob['raw_asset_id']:raw},source_filings={ref['source_reference_id']:filing})
        document=prepared['documents'][ref['source_reference_id']]
        proposal=prepared['proposals'][ref['source_reference_id']]
        scope=next(s for s in proposal['checked_ranges'] if s['section_id']=='ITEM_8')
        # This actual fixture is one block. It does not implement or prove a
        # general multi-block note/auditor exclusion pool.
        assert scope['end_block_exclusive']-scope['start_block']==1
        pool=[i for i in range(scope['start_block'],scope['end_block_exclusive'])
              if _substantive(document,document['blocks'][i])]
        keywords=[r['block_index'] for r in proposal['D02']['candidates'] if r['section_id']=='ITEM_8']
        request=review_request(company_id=target['company_id'],target_cik=target['entity'],
            period_end=target['period_end'],document=document,pool=pool,keyword_admitted=keywords)
        prepare_seconds=time.perf_counter()-started
        archive=git_bytes(ARCHIVE)
        with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar, tempfile.TemporaryDirectory() as tmp:
            call=Path(tmp)/'call0009';members={}
            terminal=json.load(tar.extractfile('root/calls/0009/terminal.json'))
            provider=[p for p in terminal['evidence'] if p.startswith('invocation_control/requests/') and p.endswith('.bin')]
            assert len(provider)==1
            names=['semantic-request.json','source.json','terminal.json','wire/journal.json',
                   'wire/raw-response.bin','wire/assistant-output.bin',provider[0]]
            for name in names:
                value=tar.extractfile('root/calls/0009/'+name).read()
                path=call/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
                members[name]={'bytes':len(value),'sha256':digest(value)}
            first={p.relative_to(call).as_posix():digest(p.read_bytes()) for p in call.rglob('*') if p.is_file()}
            started=time.perf_counter();review=read_saved_legal_review(call_root=call,request=request)
            read_seconds=time.perf_counter()-started
            assert first=={p.relative_to(call).as_posix():digest(p.read_bytes()) for p in call.rglob('*') if p.is_file()}
            assert review['included_block_ids']==[] and not review['unsettled_block_ids']
            assert review['original_execution_mode']=='LIVE' and review['original_counts']==[1,1,0]
            assert review['usage']['input_tokens']==963 and review['usage']['output_tokens']==13
            assert not review['complete_company_result'] and not review['run_created']
            review.pop('call_root')  # Temporary input location is not a persistent package.
    assert before=={str(p):digest(p.read_bytes()) for p in protected}
    receipt={'code_root':str(Path.cwd()),'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'working_tree_test':True,'source_root':str(args.source_root),'original_git_commit':OLD,
        'original_archive_path':ARCHIVE,'original_archive_sha256':digest(archive),'members':members,
        'source_document_id':document['text_document_id'],'request_id':request['request_id'],
        'input_blocks':len(request['blocks']),'must_decide':request['must_decide'],
        'full_source_candidate_count':len(proposal['D02']['candidates']),
        'prepare_seconds':prepare_seconds,'read_seconds':read_seconds,
        'protected_source_hashes':before,'original_call_bytes_preserved':True,'review':review,
        'new_calls':[0,0,0],'verification':'ONE_ACTUAL_ITEM8_SUBREVIEW_NOT_COMPANY_RESULT'}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('request_id','input_blocks','full_source_candidate_count','prepare_seconds','read_seconds','new_calls','verification')}))


if __name__=='__main__':run()
