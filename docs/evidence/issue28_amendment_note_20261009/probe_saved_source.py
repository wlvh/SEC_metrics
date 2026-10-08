"""Read-only shared original counterexample; not acquisition or result credit."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import types
from unittest.mock import patch

from vnext.annual_update import saved_source
from vnext.annual_amendment_scope import AmendmentScopeError, _source, _note
from vnext.amendment_note_layout import paragraph_blocks
from vnext.instant_balance_amendment import inspect_instant_balance_amendment
from vnext.sources import raw_blob_record, source_reference_record

parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--case',choices=('2024','2025'),default='2024')
parser.add_argument('--compare-legacy',action='store_true')
args=parser.parse_args();root=args.source_root.resolve();company='paramount_skydance_paramount_global'
filings=[{'form':'10-K','reportDate':'2024-12-31','filingDate':'2025-02-26','accessionNumber':'0000813828-25-000005','primaryDocument':'para-20241231.htm'},
         {'form':'10-K/A','reportDate':'2024-12-31','filingDate':'2025-04-25','accessionNumber':'0001193125-25-096776','primaryDocument':'d886907d10ka.htm'}]
cik='813828'
if args.case=='2025':
    cik='2041610'
    filings=[{'form':'10-K','reportDate':'2025-12-31','filingDate':'2026-02-25','accessionNumber':'0002041610-26-000011','primaryDocument':'psky-20251231.htm'},
             {'form':'10-K/A','reportDate':'2025-12-31','filingDate':'2026-04-24','accessionNumber':'0001140361-26-016758','primaryDocument':'ef20071103_10ka.htm'}]
start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
    sources=[]
    for filing in filings:
        url='https://www.sec.gov/Archives/edgar/data/'+cik+'/'+filing['accessionNumber'].replace('-','')+'/'+filing['primaryDocument']
        saved=saved_source(repo_root=root,url=url,accession=filing['accessionNumber']);assert saved is not None
        blob=raw_blob_record(repo_root=root,repo_relative_path=saved['proof']['request_repo_relative_path'],media_type='text/html')
        ref=source_reference_record(raw_blob=blob,company_id=company,source_url=url,accession=filing['accessionNumber'],document_name=filing['primaryDocument'],source_role='target_primary',request_attempt_id=saved['proof']['request_attempt_id'])
        sources.append({'raw':saved['raw'],'blob':blob,'reference':ref,'filing':filing})
    kwargs=dict(original=sources[0],amendment=sources[1],company_id=company,cik=cik)
    try:
        old=inspect_instant_balance_amendment(**kwargs)
        old_result={'decision':old['decision'],'issues':old['issues']}
    except AmendmentScopeError as error:
        old_result={'error_type':type(error).__name__,'reason':str(error)}
    current=inspect_instant_balance_amendment(**kwargs,note_layout='inline-paragraphs-v2')
    source=_source(**sources[1],company_id=company,cik=cik,period_end=filings[0]['reportDate'])
    note=_note(source['document'],raw=sources[1]['raw'])
    result={'old_default':old_result,'explicit_successor':current,'note_original_block_count':len(note['blocks']),
        'note_body_paragraph_count':len(paragraph_blocks(note['blocks'][1:],sources[1]['raw'])),
        'all_original_block_ranges_preserved':all(hashlib.sha256(sources[1]['raw'][b['raw_start_byte']:b['raw_end_byte']]).hexdigest()==b['raw_span_sha256'] for b in note['blocks']),
        'note_block_indices':[b['block_index'] for b in note['blocks']],
        'raw_sources':[{'filing':s['filing'],'sha256':hashlib.sha256(s['raw']).hexdigest(),'bytes':len(s['raw']),'reference_id':s['reference']['source_reference_id']} for s in sources],
        'seconds':time.perf_counter()-start,'source_root':str(root),'program_root':str(Path(__file__).resolve().parents[3]),
        'acquisition_credit':False,'business_result_created':False,'new_calls':[0,0,0]}
    if args.compare_legacy:
        baseline='8588ccbbb1c91d81e0fb1a89dff3575214282549'
        def load(name,path):
            module=types.ModuleType(name);module.__package__='vnext';module.__file__='git:'+baseline+':'+path
            code=subprocess.check_output(['git','show',baseline+':'+path],text=True)
            exec(compile(code,module.__file__,'exec'),module.__dict__);return module
        saved=sys.modules['vnext.annual_amendment_scope']
        try:
            sys.modules['vnext.annual_amendment_scope']=load('vnext.annual_amendment_scope','scripts/vnext/annual_amendment_scope.py')
            legacy=load('vnext.instant_balance_amendment_saved','scripts/vnext/instant_balance_amendment.py')
            prior=legacy.inspect_instant_balance_amendment(**kwargs)
        finally:sys.modules['vnext.annual_amendment_scope']=saved
        result['legacy_comparison']={'baseline':baseline,'default_result_exactly_equal':prior==old,'legacy_decision':prior['decision'],'legacy_instant_scope_id':prior['instant_scope_id'],'current_default_instant_scope_id':old['instant_scope_id'],'same_config_bytes':True}
        assert prior==old
        result['seconds']=time.perf_counter()-start
print(json.dumps(result,ensure_ascii=False,indent=2))
