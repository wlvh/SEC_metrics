"""Read complete original/amended visible blocks; no admission or calculation."""
import argparse,difflib,hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_governance_input import _Sources
from vnext.normal_period_selection import resolve_period_selection
from vnext.fiscal_year_labels import _DefinitionBlocks
from vnext.annual_amendment_scope_v2 import _note


def inspect(source):
    start=time.monotonic()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
        selection=resolve_period_selection(repo_root=source,company_id='marriott_international',fiscal_year=2021)
        filings=[selection['prior_filing'],*selection['prior_amendments']]
        assert len(filings)==2
        reader=_Sources(source,'marriott_international','1048286');documents=[]
        for filing in filings:
            items=reader.auditor_filing(filing)
            primary=next(s for s in items if s['raw_blob']['media_type']=='text/html')
            raw=primary['raw_bytes'];blocks=_DefinitionBlocks(raw.decode('utf-8-sig'))
            blocks.feed(raw.decode('utf-8-sig'));blocks.close();blocks._flush()
            texts=[b['text'] for b in blocks.blocks]
            headings=[{'index':i,'text':b['text'],'linked':b['linked'],'start':b['start'],'end':b['end']}
                for i,b in enumerate(blocks.blocks) if 'REPORT OF INDEPENDENT REGISTERED PUBLIC ACCOUNTING FIRM' in b['text'].upper()
                or b['text'].upper() in {'PART II','ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA','EXPLANATORY NOTE','SIGNATURES'}]
            documents.append({'filing':filing,'primary_sha256':hashlib.sha256(raw).hexdigest(),
                'source_reference':primary['source_reference'],'visible_blocks':blocks.blocks,
                'headings':headings,'read_only':True})
        return {'record_type':'AUDIT_AMENDMENT_SOURCE_READING','selection':selection,'documents':documents,
            'elapsed_seconds':time.monotonic()-start,'scope_admission_granted':False,
            'metric_executed':False,'new_business_calls':{'provider':0,'paid':0,'sec':0}}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    result=inspect(a.source_root.resolve())
    with a.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'elapsed_seconds':result['elapsed_seconds'],'documents':[
        {k:d[k] for k in ['filing','primary_sha256','headings']} for d in result['documents']]},ensure_ascii=False,indent=2))
