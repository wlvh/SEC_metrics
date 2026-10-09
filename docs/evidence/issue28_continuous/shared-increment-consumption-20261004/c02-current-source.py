"""Limited current-source check: peer leads are not imported result credit."""
import hashlib
import json
import socket
import subprocess
import time
from pathlib import Path

from vnext.normal_text_input_v2 import prepare_normal_business_text_input
from vnext.text_results_v2 import prepare_business_text_sources
from vnext.c02_board_composition_28_v3 import board_composition_facts as v3
from vnext.c02_board_composition_28_v4 import board_composition_facts as v4

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent

def blocked(*a,**k): raise AssertionError('NETWORK_BUSINESS_FORBIDDEN')
socket.socket=blocked; socket.create_connection=blocked
start=time.monotonic()
p=prepare_normal_business_text_input(repo_root=ROOT,company_id='jpmorgan_chase',metric_id='C02')
args=p['text_arguments']
prepared=prepare_business_text_sources(metric_id='C02',**args)
doc=next(d for d in prepared['documents'].values() if d['record_type']=='GOVERNANCE_SOURCE_TEXT_DOCUMENT')
reads=[]
for i in [764,765,766,767,768,1242,1243,1244,1245,1246]:
 b=doc['blocks'][i];raw=args['raw_bytes_by_id'][doc['raw_asset_id']]
 span=raw[b['raw_start_byte']:b['raw_end_byte']]
 assert hashlib.sha256(span).hexdigest()==b['raw_span_sha256']
 reads.append({k:b[k] for k in ['block_index','text','raw_start_byte','raw_end_byte','raw_span_sha256']})
proposals={}
for label,fn in [('ordinary_v3',v3),('suspended_v4',v4)]:
 q=fn(document=doc,period_start=args['target']['period_start'])
 selected=[x['block_index'] for x in q['candidates']]
 proposals[label]={'selected_named_boundary_blocks':[i for i in [766,767,1244,1245] if i in selected],
   'selector_sha256':hashlib.sha256((ROOT/('scripts/vnext/c02_board_composition_28_'+('v3' if label=='ordinary_v3' else 'v4')+'.py')).read_bytes()).hexdigest(),
   'whole_content_accepted':False}
result={'own_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'peer_head':subprocess.check_output(['git','rev-parse','origin/task/sec-history-five-year'],text=True).strip(),
 'source_id':doc['text_document_id'],'raw_asset_id':doc['raw_asset_id'],
 'source_filing':doc['source_filing'],'company_id':doc['company_id'],'target':args['target'],
 'readings':reads,'proposals':proposals,'seconds':round(time.monotonic()-start,3),
 'scope_limit':'Only the named owner/committee boundaries; neither whole-result semantic acceptance nor a full omission scan.',
 'new_result_created':False,'business_calls':[0,0,0]}
(HERE/'c02-current-source.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['readings','target','source_filing']},ensure_ascii=False))
