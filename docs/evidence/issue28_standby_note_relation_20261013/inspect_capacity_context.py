"""Read full-original capacity context; keyword hits are locations, not conclusions."""
import argparse,hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext.fiscal_year_labels import _DefinitionBlocks
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    prep=prepare_selected_debt_sources(repo_root=a.source_root,company_id='macys',fiscal_year=2024)['preparation']
    raw=prep['primary']['raw_bytes'];text=raw.decode('utf-8-sig');parser=_DefinitionBlocks(text)
    parser.feed(text);parser.close();parser._flush();blocks=parser.blocks
    hits=[i for i,b in enumerate(blocks) if any(t in b['text'].casefold() for t in
        ('capital resources','available borrowing','2,856','2,459','397 million','other standby letters'))]
    selected=sorted({j for i in hits for j in range(max(0,i-2),min(len(blocks),i+3))})
    locations=[]
    for i in selected:
        b=blocks[i];offset=len(text[:b['start']].encode('utf-8'));end=len(text[:b['end']].encode('utf-8'))
        locations.append({'index':i,'text':b['text'],'linked':b['linked'],
            'raw_start_byte':offset,'raw_end_byte':end,'raw_span_sha256':hashlib.sha256(raw[offset:end]).hexdigest()})
    result={'filing':prep['input_binding']['prepared_annual_input']['filing'],
        'primary_sha256':hashlib.sha256(raw).hexdigest(),'source_reference':prep['primary']['source_reference'],
        'elapsed_seconds':time.monotonic()-start,'locations':locations,'complete_scope_credit':False,'calls':[0,0,0]}
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
