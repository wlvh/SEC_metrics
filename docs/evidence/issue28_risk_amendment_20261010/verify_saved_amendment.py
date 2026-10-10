"""One original/amendment saved pair, exact source frames; no result or acquisition."""
import argparse,json,socket,subprocess,time
from pathlib import Path
from unittest.mock import patch
from vnext.annual_update import saved_source
from vnext.risk_heading_amendment_input_v1 import inspect_risk_heading_amendment,PROCESSING_FILES
from vnext.sources import raw_blob_record,source_reference_record
from vnext.saved_source_checks import verify_saved_inputs
from vnext.canonical import sha256_file

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);a=p.parse_args();root=a.source_root.resolve()
company='paramount_skydance_paramount_global';cik='2041610'
filings=[{'form':'10-K','reportDate':'2025-12-31','filingDate':'2026-02-25',
          'accessionNumber':'0002041610-26-000011','primaryDocument':'psky-20251231.htm'},
         {'form':'10-K/A','reportDate':'2025-12-31','filingDate':'2026-04-24',
          'accessionNumber':'0001140361-26-016758','primaryDocument':'ef20071103_10ka.htm'}]
t=time.monotonic();frames=[];proofs=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
    for filing in filings:
        url='https://www.sec.gov/Archives/edgar/data/'+cik+'/'+filing['accessionNumber'].replace('-','')+'/'+filing['primaryDocument']
        source=saved_source(repo_root=root,url=url,accession=filing['accessionNumber']);assert source is not None,url
        proof=source['proof'];proofs.append(proof)
        blob=raw_blob_record(repo_root=root,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
        ref=source_reference_record(raw_blob=blob,company_id=company,source_url=url,
            accession=filing['accessionNumber'],document_name=filing['primaryDocument'],source_role='target_primary',
            request_attempt_id=proof['request_attempt_id'])
        frames.append({'raw':source['raw'],'blob':blob,'reference':ref,'filing':filing})
    admission=verify_saved_inputs(data_root=root,proofs=proofs)
    result=inspect_risk_heading_amendment(original=frames[0],amendment=frames[1],company_id=company,cik=cik)
program=Path.cwd()
record={'program_root':str(program),'source_root':str(root),'git_base':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'tested_tree':'UNCOMMITTED_NEW_SOURCE_API','seconds':time.monotonic()-t,
        'api_source_summaries':{'original':result['original'],'amendment':result['amendment']},
        'source_hashes':[{ 'filing':f['filing'],'raw_sha256':r['content_sha256'],'source_reference':f['reference'],
                          'source_path':r['request_repo_relative_path']} for f,r in zip(frames,proofs)],
        'source_admission':admission,'scope_id':result['scope_id'],'classification':result['classification'],
        'decision':result['decision'],'input_class':result['input_class'],'issues':result['issues'],
        'fiscal_window_unchanged':result['fiscal_window_unchanged'],'details':result['details'],
        'policy_hash':result['source_scope']['policy_hash'],'full_scope_contains_both_documents':True,
        'source_scope_original_id':result['source_scope']['scope_id'],
        'source_item_headers':result['source_scope']['details'].get('items'),
        'not_covered_original_policy':result['source_scope']['not_covered_metric_ids'],
        'tested_processing_files':{f:sha256_file(path=program/f) for f in PROCESSING_FILES},
        'reference_headings_used_as_input':False,'metric_result_created':False,
        'source_acquisition_credit':False,'calls':[0,0,0]}
output=program/'docs/evidence/issue28_risk_amendment_20261010/final-actual-saved-source.json'
output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print('decision',result['decision'],'classification',result['classification'],'seconds',record['seconds'])
print('issues',result['issues']);print('note declared',result['details'].get('note_identity',{}).get('declared_identity'))
print('original section',result['details'].get('original_item_1a_section',{}).get('status'))
print('risk refs',[(r['block_indices'],r['status']) for r in result['details'].get('risk_section_references',[])])
assert result['decision']=='INPUT_PROPERTY_PROVEN',result['issues']
